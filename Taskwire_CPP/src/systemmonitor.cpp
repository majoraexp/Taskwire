#include "systemmonitor.h"

#include <QTimer>
#include <QDir>
#include <QFile>
#include <QProcess>
#include <QElapsedTimer>
#include <QStandardPaths>

#include <sys/statvfs.h>
#include <unistd.h>
#include <pwd.h>
#include <dirent.h>
#include <cmath>
#include <algorithm>
#include <QDateTime>

// ── Helper: read entire small file into QString ─────────────

static QString readFileContents(const QString &path) {
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly | QIODevice::Text))
        return {};
    return QString::fromUtf8(f.readAll());
}

static long long readFileLongLong(const QString &path) {
    QString s = readFileContents(path).trimmed();
    bool ok = false;
    long long v = s.toLongLong(&ok);
    return ok ? v : -1;
}

// ── Constructor ─────────────────────────────────────────────

SystemMonitorWorker::SystemMonitorWorker(QObject *parent)
    : QObject(parent)
{
    // One-time discovery
    discoverCpuCores();
    discoverAmdGpuPaths();
    discoverHwmonSensors();

    // Check for nvidia-smi
    m_nvidiaSmiPath = QStandardPaths::findExecutable(QStringLiteral("nvidia-smi"));
    m_hasNvidiaSmi = !m_nvidiaSmiPath.isEmpty();

    // Check for lsblk
    m_lsblkPath = QStandardPaths::findExecutable(QStringLiteral("lsblk"));

    // Check for pkexec + bash (GPU escalation)
    m_pkexecPath = QStandardPaths::findExecutable(QStringLiteral("pkexec"));
    m_bashPath = QStandardPaths::findExecutable(QStringLiteral("bash"));
    m_gpuEscalationAvailable = !m_pkexecPath.isEmpty() && !m_bashPath.isEmpty();

    // Process monitoring init
    m_pageSize = sysconf(_SC_PAGESIZE);
    if (m_pageSize <= 0) m_pageSize = 4096;
    m_numCores = static_cast<int>(sysconf(_SC_NPROCESSORS_ONLN));
    if (m_numCores <= 0) m_numCores = 1;

    // Cache total memory
    {
        QString content = readFileContents(QStringLiteral("/proc/meminfo"));
        for (const auto &line : content.split(QLatin1Char('\n'), Qt::SkipEmptyParts)) {
            if (line.startsWith(QLatin1String("MemTotal:"))) {
                QStringList parts = line.split(QLatin1Char(' '), Qt::SkipEmptyParts);
                if (parts.size() >= 2) m_totalMemBytes = parts[1].toLongLong() * 1024;
                break;
            }
        }
    }
}

// ── Polling lifecycle ───────────────────────────────────────

void SystemMonitorWorker::startPolling() {
    m_fastTimer = new QTimer(this);
    m_fastTimer->setInterval(500);
    connect(m_fastTimer, &QTimer::timeout, this, &SystemMonitorWorker::pollFast);

    m_slowTimer = new QTimer(this);
    m_slowTimer->setInterval(5000); // Disk usage only — 5s (lsblk subprocess is heavy)
    connect(m_slowTimer, &QTimer::timeout, this, &SystemMonitorWorker::pollSlow);

    m_mediumTimer = new QTimer(this);
    m_mediumTimer->setInterval(1000); // Process list — 1s
    connect(m_mediumTimer, &QTimer::timeout, this, &SystemMonitorWorker::pollMedium);

    // Initialize elapsed timers for accurate rate deltas
    m_fastElapsed.start();
    m_procPollElapsed.start();

    // First poll immediately
    pollFast();
    pollSlow();
    pollMedium();

    m_fastTimer->start();
    m_slowTimer->start();
    m_mediumTimer->start();
}

void SystemMonitorWorker::stopPolling() {
    if (m_fastTimer) m_fastTimer->stop();
    if (m_slowTimer) m_slowTimer->stop();
    if (m_mediumTimer) m_mediumTimer->stop();
    stopEscalatedHelper();
}

// ── Fast poll (500ms): CPU, memory, GPU, disk IO, network, temps, fans ──

void SystemMonitorWorker::pollFast() {
    double deltaSec = m_fastElapsed.restart() / 1000.0;
    if (deltaSec <= 0.0) deltaSec = 0.5; // fallback

    emit cpuUpdate(readCpu());
    emit memoryUpdate(readMemory());
    emit gpuUpdate(readGpu());
    emit diskIoUpdate(readDiskIo(deltaSec));
    emit networkUpdate(readNetwork(deltaSec));
    emit tempUpdate(readTemps());
    emit fanUpdate(readFans());
}

// ── Slow poll (5s): disk usage ──────────────────────────────

void SystemMonitorWorker::pollSlow() {
    emit diskUpdate(readDiskUsage());
}

// ── CPU ─────────────────────────────────────────────────────
// Parse /proc/stat for jiffies, compute delta from previous read.
// Format: cpu  user nice system idle iowait irq softirq steal ...

static CpuJiffies parseCpuLine(const QString &line) {
    CpuJiffies j;
    // Split on whitespace, skip the label (cpu / cpu0 / etc.)
    QStringList parts = line.split(QLatin1Char(' '), Qt::SkipEmptyParts);
    if (parts.size() < 9) return j; // label + 8 fields minimum
    j.user    = parts[1].toLongLong();
    j.nice    = parts[2].toLongLong();
    j.system  = parts[3].toLongLong();
    j.idle    = parts[4].toLongLong();
    j.iowait  = parts[5].toLongLong();
    j.irq     = parts[6].toLongLong();
    j.softirq = parts[7].toLongLong();
    j.steal   = parts[8].toLongLong();
    return j;
}

static double jiffiesToPercent(const CpuJiffies &prev, const CpuJiffies &cur) {
    long long totalDelta = cur.totalTicks() - prev.totalTicks();
    long long idleDelta  = cur.idleTicks()  - prev.idleTicks();
    if (totalDelta <= 0) return 0.0;
    return std::clamp((double)(totalDelta - idleDelta) / totalDelta * 100.0, 0.0, 100.0);
}

CpuStats SystemMonitorWorker::readCpu() {
    CpuStats stats;

    QString content = readFileContents(QStringLiteral("/proc/stat"));
    if (content.isEmpty()) return stats;

    QStringList lines = content.split(QLatin1Char('\n'), Qt::SkipEmptyParts);
    if (lines.isEmpty()) return stats;

    // Overall CPU (first line: "cpu  ...")
    CpuJiffies overall = parseCpuLine(lines[0]);

    // Per-core lines: "cpu0 ...", "cpu1 ...", etc.
    QVector<CpuJiffies> perCore;
    for (int i = 1; i < lines.size(); ++i) {
        if (!lines[i].startsWith(QLatin1String("cpu")))
            break;
        perCore.append(parseCpuLine(lines[i]));
    }

    if (m_cpuFirstPoll) {
        // No previous data — store current and return zeros
        m_prevOverall = overall;
        m_prevPerCore = perCore;
        m_cpuFirstPoll = false;

        stats.overallPercent = 0.0;
        stats.corePercents.fill(0.0, perCore.size());
        stats.valid = true;
    } else {
        stats.overallPercent = jiffiesToPercent(m_prevOverall, overall);

        stats.corePercents.resize(perCore.size());
        for (int i = 0; i < perCore.size(); ++i) {
            if (i < m_prevPerCore.size())
                stats.corePercents[i] = jiffiesToPercent(m_prevPerCore[i], perCore[i]);
            else
                stats.corePercents[i] = 0.0;
        }

        m_prevOverall = overall;
        m_prevPerCore = perCore;
        stats.valid = true;
    }

    // CPU frequencies from cached sysfs paths
    stats.coreFreqsMHz.resize(m_freqPaths.size());
    for (int i = 0; i < m_freqPaths.size(); ++i) {
        long long khz = readFileLongLong(m_freqPaths[i]);
        stats.coreFreqsMHz[i] = (khz > 0) ? khz / 1000.0 : 0.0;
    }

    return stats;
}

// ── Memory ──────────────────────────────────────────────────
// Parse /proc/meminfo for key fields

MemoryStats SystemMonitorWorker::readMemory() {
    MemoryStats stats;

    QString content = readFileContents(QStringLiteral("/proc/meminfo"));
    if (content.isEmpty()) return stats;

    long long memTotal = 0, memAvailable = 0, memFree = 0;
    long long buffers = 0, cached = 0;
    long long swapTotal = 0, swapFree = 0;

    const QStringList lines = content.split(QLatin1Char('\n'), Qt::SkipEmptyParts);
    for (const QString &line : lines) {
        // Lines are "FieldName:     12345 kB"
        QStringList parts = line.split(QLatin1Char(' '), Qt::SkipEmptyParts);
        if (parts.size() < 2) continue;

        if (parts[0] == QLatin1String("MemTotal:"))
            memTotal = parts[1].toLongLong();
        else if (parts[0] == QLatin1String("MemAvailable:"))
            memAvailable = parts[1].toLongLong();
        else if (parts[0] == QLatin1String("MemFree:"))
            memFree = parts[1].toLongLong();
        else if (parts[0] == QLatin1String("Buffers:"))
            buffers = parts[1].toLongLong();
        else if (parts[0] == QLatin1String("Cached:"))
            cached = parts[1].toLongLong();
        else if (parts[0] == QLatin1String("SwapTotal:"))
            swapTotal = parts[1].toLongLong();
        else if (parts[0] == QLatin1String("SwapFree:"))
            swapFree = parts[1].toLongLong();
    }

    // /proc/meminfo values are in kB
    stats.totalBytes     = memTotal * 1024LL;
    stats.availableBytes = memAvailable * 1024LL;
    stats.freeBytes      = memFree * 1024LL;
    stats.buffersBytes   = buffers * 1024LL;
    stats.cachedBytes    = cached * 1024LL;
    stats.usedBytes      = stats.totalBytes - stats.availableBytes;
    stats.percent        = (stats.totalBytes > 0)
                             ? (double)stats.usedBytes / stats.totalBytes * 100.0
                             : 0.0;
    stats.swapTotal      = swapTotal * 1024LL;
    stats.swapUsed       = (swapTotal - swapFree) * 1024LL;
    stats.swapPercent    = (swapTotal > 0)
                             ? (double)stats.swapUsed / stats.swapTotal * 100.0
                             : 0.0;
    stats.valid = true;
    return stats;
}

// ── GPU ─────────────────────────────────────────────────────

GpuStats SystemMonitorWorker::readGpu() {
    GpuStats stats;
    double maxUsage = 0.0;

    // AMD: read sysfs
    int failures = 0;
    for (const QString &path : m_amdGpuPaths) {
        long long val = readFileLongLong(path);
        if (val >= 0) {
            maxUsage = std::max(maxUsage, std::clamp((double)val, 0.0, 100.0));
        } else {
            ++failures;
        }
    }
    // Re-discover if all cached paths failed
    if (!m_amdGpuPaths.isEmpty() && failures == m_amdGpuPaths.size()) {
        discoverAmdGpuPaths();
    }

    // NVIDIA: nvidia-smi (synchronous in worker thread, runs on the 500ms fast poll)
    if (m_hasNvidiaSmi) {
        QProcess proc;
        proc.start(m_nvidiaSmiPath,
                    {QStringLiteral("--query-gpu=utilization.gpu"),
                     QStringLiteral("--format=csv,noheader,nounits")});
        if (proc.waitForFinished(5000)) {
            QString out = QString::fromUtf8(proc.readAllStandardOutput()).trimmed();
            const QStringList lines = out.split(QLatin1Char('\n'), Qt::SkipEmptyParts);
            for (const QString &line : lines) {
                bool ok = false;
                double v = line.trimmed().toDouble(&ok);
                if (ok)
                    maxUsage = std::max(maxUsage, std::clamp(v, 0.0, 100.0));
            }
        }
    }

    stats.usagePercent = maxUsage;
    stats.valid = true;
    return stats;
}

// ── Disk IO ─────────────────────────────────────────────────
// Parse /proc/diskstats — fields: major minor name rd_ios rd_merges
//   rd_sectors rd_ticks wr_ios wr_merges wr_sectors wr_ticks ...
// Sector size is 512 bytes. We sum all devices.

DiskIoStats SystemMonitorWorker::readDiskIo(double deltaSec) {
    DiskIoStats stats;

    QString content = readFileContents(QStringLiteral("/proc/diskstats"));
    if (content.isEmpty()) return stats;

    long long totalReadSectors = 0, totalWriteSectors = 0;
    const QStringList lines = content.split(QLatin1Char('\n'), Qt::SkipEmptyParts);

    for (const QString &line : lines) {
        QStringList parts = line.split(QLatin1Char(' '), Qt::SkipEmptyParts);
        if (parts.size() < 14) continue;

        const QString &devName = parts[2];
        // Skip virtual devices
        if (devName.startsWith(QLatin1String("loop")) ||
            devName.startsWith(QLatin1String("ram")) ||
            devName.startsWith(QLatin1String("dm-")) ||
            devName.startsWith(QLatin1String("zram")))
            continue;

        // Whole-disk filter: device name must NOT end in a digit (partitions do)
        // e.g. "sda" OK, "sda1" skip, "sdaa" OK, "nvme0n1" OK, "nvme0n1p1" skip
        bool isWholeDisk = false;
        if (devName.startsWith(QLatin1String("sd")) || devName.startsWith(QLatin1String("vd"))) {
            isWholeDisk = !devName.back().isDigit();
        } else if (devName.startsWith(QLatin1String("nvme"))) {
            // "nvme0n1" is whole disk, "nvme0n1p1" is partition
            // Partition names contain 'p' after the namespace number
            int nIdx = devName.lastIndexOf(QLatin1Char('n'));
            if (nIdx > 0)
                isWholeDisk = !devName.mid(nIdx + 2).contains(QLatin1Char('p'));
        }

        if (!isWholeDisk) continue;

        totalReadSectors  += parts[5].toLongLong();  // rd_sectors
        totalWriteSectors += parts[9].toLongLong();   // wr_sectors
    }

    long long curReadBytes  = totalReadSectors * 512LL;
    long long curWriteBytes = totalWriteSectors * 512LL;

    if (m_diskIoFirstPoll) {
        m_prevDiskReadBytes  = curReadBytes;
        m_prevDiskWriteBytes = curWriteBytes;
        m_diskIoFirstPoll = false;
        stats.valid = true;
        return stats;
    }

    long long deltaRead  = curReadBytes - m_prevDiskReadBytes;
    long long deltaWrite = curWriteBytes - m_prevDiskWriteBytes;

    stats.readBytesPerSec  = (deltaSec > 0) ? deltaRead / deltaSec : 0.0;
    stats.writeBytesPerSec = (deltaSec > 0) ? deltaWrite / deltaSec : 0.0;

    m_prevDiskReadBytes  = curReadBytes;
    m_prevDiskWriteBytes = curWriteBytes;
    stats.valid = true;
    return stats;
}

// ── Network ─────────────────────────────────────────────────
// Parse /proc/net/dev — skip header lines, sum rx_bytes and tx_bytes
// Format:  iface: rx_bytes rx_packets ... tx_bytes tx_packets ...

NetworkStats SystemMonitorWorker::readNetwork(double deltaSec) {
    NetworkStats stats;

    QString content = readFileContents(QStringLiteral("/proc/net/dev"));
    if (content.isEmpty()) return stats;

    long long totalRx = 0, totalTx = 0;
    const QStringList lines = content.split(QLatin1Char('\n'), Qt::SkipEmptyParts);

    for (int i = 0; i < lines.size(); ++i) {
        if (i < 2) continue; // skip 2 header lines

        const QString &line = lines[i];
        int colonIdx = line.indexOf(QLatin1Char(':'));
        if (colonIdx < 0) continue;

        QString iface = line.left(colonIdx).trimmed();
        if (iface == QLatin1String("lo")) continue;

        QString data = line.mid(colonIdx + 1);
        QStringList parts = data.split(QLatin1Char(' '), Qt::SkipEmptyParts);
        if (parts.size() < 9) continue;

        totalRx += parts[0].toLongLong(); // rx_bytes
        totalTx += parts[8].toLongLong(); // tx_bytes
    }

    if (m_netFirstPoll) {
        m_prevNetRxBytes = totalRx;
        m_prevNetTxBytes = totalTx;
        m_netFirstPoll = false;
        stats.valid = true;
        return stats;
    }
    stats.downloadBytesPerSec = (totalRx - m_prevNetRxBytes) / deltaSec;
    stats.uploadBytesPerSec   = (totalTx - m_prevNetTxBytes) / deltaSec;

    m_prevNetRxBytes = totalRx;
    m_prevNetTxBytes = totalTx;
    stats.valid = true;
    return stats;
}

// ── Temperatures ────────────────────────────────────────────

TempStats SystemMonitorWorker::readTemps() {
    TempStats stats;

    for (const HwmonSensor &sensor : m_hwmonSensors) {
        if (sensor.type != HwmonSensor::Temperature)
            continue;

        long long millideg = readFileLongLong(sensor.inputPath);
        if (millideg < 0) continue;

        TempReading r;
        r.label = sensor.label;
        r.celsius = millideg / 1000.0;

        // Sanity: skip bogus readings
        if (r.celsius < -40.0 || r.celsius > 150.0)
            continue;

        stats.temps.append(r);
    }

    stats.valid = !stats.temps.isEmpty();
    return stats;
}

// ── Fans ────────────────────────────────────────────────────

FanStats SystemMonitorWorker::readFans() {
    FanStats stats;

    for (const HwmonSensor &sensor : m_hwmonSensors) {
        if (sensor.type != HwmonSensor::Fan)
            continue;

        long long rpm = readFileLongLong(sensor.inputPath);
        if (rpm < 0) continue;

        FanReading r;
        r.label = sensor.label;
        r.rpm = static_cast<int>(rpm);
        stats.fans.append(r);
    }

    stats.valid = !stats.fans.isEmpty();
    return stats;
}

// ── Disk Usage ──────────────────────────────────────────────

DiskUsageStats SystemMonitorWorker::readDiskUsage() {
    DiskUsageStats stats;

    if (m_lsblkPath.isEmpty()) return stats;

    // Get physical disks via lsblk
    QProcess proc;
    proc.start(m_lsblkPath,
               {QStringLiteral("-d"), QStringLiteral("-n"),
                QStringLiteral("-o"), QStringLiteral("NAME,MODEL,SIZE"),
                QStringLiteral("-b")});

    if (!proc.waitForFinished(5000)) return stats;

    QString out = QString::fromUtf8(proc.readAllStandardOutput());
    const QStringList lines = out.split(QLatin1Char('\n'), Qt::SkipEmptyParts);

    for (const QString &line : lines) {
        QStringList parts = line.split(QLatin1Char(' '), Qt::SkipEmptyParts);
        if (parts.size() < 2) continue;

        const QString &name = parts[0];
        if (name.contains(QLatin1String("zram")) || name.contains(QLatin1String("loop")))
            continue;

        bool ok = false;
        long long size = parts.last().toLongLong(&ok);
        if (!ok || size <= 0) continue;

        QString model;
        if (parts.size() > 2) {
            // Model is everything between name and size
            QStringList modelParts = parts.mid(1, parts.size() - 2);
            model = modelParts.join(QLatin1Char(' '));
        } else {
            model = name;
        }

        DiskInfo info;
        info.model = model;
        info.sizeBytes = size;
        info.usedBytes = 0;
        info.percent = 0.0;

        stats.disks.insert(QStringLiteral("/dev/") + name, info);
    }

    // Read mount points from /proc/mounts and aggregate usage via statvfs
    QFile mounts(QStringLiteral("/proc/mounts"));
    if (!mounts.open(QIODevice::ReadOnly | QIODevice::Text)) {
        stats.valid = !stats.disks.isEmpty();
        return stats;
    }

    QSet<QString> seenDevices;
    // Use readAll() instead of QTextStream — QTextStream fails on procfs
    const QString mountData = QString::fromUtf8(mounts.readAll());
    mounts.close();
    const QStringList mountLines = mountData.split(QLatin1Char('\n'), Qt::SkipEmptyParts);
    for (const QString &line : mountLines) {
        QStringList parts = line.split(QLatin1Char(' '), Qt::SkipEmptyParts);
        if (parts.size() < 3) continue;

        const QString &device = parts[0];
        const QString &mountpoint = parts[1];
        const QString &fstype = parts[2];

        // Skip pseudo-filesystems
        if (!device.startsWith(QLatin1Char('/'))) continue;
        if (device.contains(QLatin1String("loop"))) continue;

        static const QStringList pseudoFs = {
            QStringLiteral("squashfs"), QStringLiteral("overlay"),
            QStringLiteral("tmpfs"), QStringLiteral("devtmpfs"),
            QStringLiteral("ramfs"), QStringLiteral("iso9660")
        };
        if (pseudoFs.contains(fstype)) continue;

        // Deduplicate by device path (handles Btrfs subvolumes)
        if (seenDevices.contains(device)) continue;
        seenDevices.insert(device);

        // Decode octal escapes from /proc/mounts (e.g. \040 → space)
        QString decodedMp = mountpoint;
        decodedMp.replace(QLatin1String("\\040"), QLatin1String(" "));
        decodedMp.replace(QLatin1String("\\011"), QLatin1String("\t"));
        decodedMp.replace(QLatin1String("\\012"), QLatin1String("\n"));
        decodedMp.replace(QLatin1String("\\134"), QLatin1String("\\"));

        // statvfs for usage
        struct statvfs sv;
        QByteArray mp = decodedMp.toUtf8();
        if (::statvfs(mp.constData(), &sv) != 0) continue;

        long long totalBytes = (long long)sv.f_blocks * sv.f_frsize;
        long long freeBytes  = (long long)sv.f_bfree * sv.f_frsize;
        long long usedBytes  = totalBytes - freeBytes;

        // Find parent physical disk
        for (auto it = stats.disks.begin(); it != stats.disks.end(); ++it) {
            if (device.startsWith(it.key())) {
                it->usedBytes += usedBytes;
                if (it->usedBytes > it->sizeBytes)
                    it->usedBytes = it->sizeBytes;
                break;
            }
        }
    }

    // Calculate percentages
    for (auto it = stats.disks.begin(); it != stats.disks.end(); ++it) {
        if (it->sizeBytes > 0)
            it->percent = (double)it->usedBytes / it->sizeBytes * 100.0;
    }

    stats.valid = !stats.disks.isEmpty();
    return stats;
}

// ── Medium poll (1s): process list ───────────────────────────

void SystemMonitorWorker::pollMedium() {
    emit processUpdate(readProcesses());
}

// ── Process state helper ────────────────────────────────────

static QString stateToString(QChar c) {
    switch (c.toLatin1()) {
        case 'R': return QStringLiteral("running");
        case 'S': return QStringLiteral("sleeping");
        case 'D': return QStringLiteral("disk sleep");
        case 'Z': return QStringLiteral("zombie");
        case 'T': return QStringLiteral("stopped");
        case 't': return QStringLiteral("tracing stop");
        case 'X': case 'x': return QStringLiteral("dead");
        case 'I': return QStringLiteral("idle");
        default:  return QStringLiteral("unknown");
    }
}

// ── GPU fdinfo ns parser ────────────────────────────────────
// Accepts "123456", "123456 ns", "  123456  ns "

static bool parseEngineNs(QStringView v, quint64 &out) {
    auto trimmed = v.trimmed();
    if (trimmed.isEmpty()) return false;
    int spaceIdx = -1;
    for (int i = 0; i < trimmed.size(); ++i) {
        if (!trimmed[i].isDigit()) { spaceIdx = i; break; }
    }
    QStringView numStr = (spaceIdx < 0) ? trimmed : trimmed.left(spaceIdx);
    if (numStr.isEmpty()) return false;
    bool ok = false;
    quint64 v64 = numStr.toULongLong(&ok);
    if (!ok) return false;
    if (spaceIdx >= 0) {
        QStringView unit = trimmed.mid(spaceIdx).trimmed();
        if (!unit.isEmpty() && unit != QLatin1String("ns")) return false;
    }
    out = v64;
    return true;
}

// ── readProcesses ───────────────────────────────────────────

ProcessStats SystemMonitorWorker::readProcesses() {
    ProcessStats stats;

    // 0. GPU wall-clock elapsed for this poll cycle
    qint64 nowNs = m_procPollElapsed.nsecsElapsed();
    quint64 elapsedNs = 0;
    if (!m_gpuProcFirstPoll) {
        elapsedNs = static_cast<quint64>(nowNs - m_prevProcPollNs);
    }
    m_prevProcPollNs = nowNs;

    QSet<ProcGpuKey> gpuSeenThisPoll;
    QSet<ProcKey> gpuScannedThisPoll;
    QHash<int, ProcKey> gpuDeniedPids;

    // 1. Read current total CPU jiffies (for per-process CPU% delta)
    CpuJiffies totalJiffies;
    {
        QString content = readFileContents(QStringLiteral("/proc/stat"));
        if (!content.isEmpty()) {
            int newline = content.indexOf(QLatin1Char('\n'));
            QString firstLine = (newline > 0) ? content.left(newline) : content;
            totalJiffies = parseCpuLine(firstLine);
        }
    }

    // 2. Read available memory (for normalization)
    long long availableBytes = 0;
    {
        QString content = readFileContents(QStringLiteral("/proc/meminfo"));
        for (const auto &line : content.split(QLatin1Char('\n'), Qt::SkipEmptyParts)) {
            if (line.startsWith(QLatin1String("MemAvailable:"))) {
                QStringList parts = line.split(QLatin1Char(' '), Qt::SkipEmptyParts);
                if (parts.size() >= 2) availableBytes = parts[1].toLongLong() * 1024;
                break;
            }
        }
    }

    // 3. Iterate /proc/[pid] directories
    QDir procDir(QStringLiteral("/proc"));
    const QStringList entries = procDir.entryList(QDir::Dirs | QDir::NoDotAndDotDot);

    QSet<ProcKey> seenKeys;
    long long totalRss = 0;

    for (const QString &entry : entries) {
        bool ok = false;
        int pid = entry.toInt(&ok);
        if (!ok || pid <= 0) continue;

        QString pidPath = QStringLiteral("/proc/%1").arg(pid);

        // ── /proc/[pid]/stat ────────────────────────────
        QString statContent = readFileContents(pidPath + QStringLiteral("/stat"));
        if (statContent.isEmpty()) continue;

        // Parse comm carefully: find first '(' and last ')'
        int openParen = statContent.indexOf(QLatin1Char('('));
        int closeParen = statContent.lastIndexOf(QLatin1Char(')'));
        if (openParen < 0 || closeParen < 0 || closeParen <= openParen) continue;

        QString comm = statContent.mid(openParen + 1, closeParen - openParen - 1);
        QString rest = statContent.mid(closeParen + 2);
        QStringList fields = rest.split(QLatin1Char(' '), Qt::SkipEmptyParts);
        if (fields.size() < 20) continue;

        QChar stateChar = fields[0].isEmpty() ? QChar('?') : fields[0][0];
        int ppid = fields[1].toInt();
        unsigned long long utime = fields[11].toULongLong();
        unsigned long long stime = fields[12].toULongLong();
        int numThreads = fields[17].toInt();
        unsigned long long starttime = fields[19].toULongLong();

        ProcKey key{pid, starttime};
        seenKeys.insert(key);

        // ── /proc/[pid]/statm — RSS and shared pages ────
        long long rssBytes = 0;
        long long sharedBytes = 0;
        {
            QString statm = readFileContents(pidPath + QStringLiteral("/statm"));
            QStringList sf = statm.split(QLatin1Char(' '), Qt::SkipEmptyParts);
            if (sf.size() >= 3) {
                rssBytes = sf[1].toLongLong() * m_pageSize;
                sharedBytes = sf[2].toLongLong() * m_pageSize;
            }
        }

        // ── /proc/[pid]/status — VmSwap, Uid ────────────
        long long swapBytes = 0;
        int uid = -1;
        {
            QString status = readFileContents(pidPath + QStringLiteral("/status"));
            for (const auto &line : status.split(QLatin1Char('\n'), Qt::SkipEmptyParts)) {
                if (line.startsWith(QLatin1String("VmSwap:"))) {
                    QStringList parts = line.split(QLatin1Char(' '), Qt::SkipEmptyParts);
                    if (parts.size() >= 2) swapBytes = parts[1].toLongLong() * 1024;
                } else if (line.startsWith(QLatin1String("Uid:"))) {
                    QStringList parts = line.split(QLatin1Char(' '), Qt::SkipEmptyParts);
                    if (parts.size() >= 2) uid = parts[1].toInt();
                }
            }
        }

        // ── /proc/[pid]/io — read/write bytes (optional) ─
        long long readB = 0, writeB = 0;
        {
            QString ioContent = readFileContents(pidPath + QStringLiteral("/io"));
            if (!ioContent.isEmpty()) {
                for (const auto &line : ioContent.split(QLatin1Char('\n'), Qt::SkipEmptyParts)) {
                    if (line.startsWith(QLatin1String("read_bytes:")))
                        readB = line.mid(12).trimmed().toLongLong();
                    else if (line.startsWith(QLatin1String("write_bytes:")))
                        writeB = line.mid(13).trimmed().toLongLong();
                }
            }
        }

        // ── CPU% delta ──────────────────────────────────
        double cpuPercent = 0.0;
        if (!m_procFirstPoll) {
            auto prevIt = m_prevProcCpu.find(key);
            if (prevIt != m_prevProcCpu.end()) {
                unsigned long long deltaProc = (utime + stime) - (prevIt->utime + prevIt->stime);
                long long deltaTotal = totalJiffies.totalTicks() - m_prevProcJiffies.totalTicks();
                if (deltaTotal > 0) {
                    cpuPercent = std::clamp(
                        static_cast<double>(deltaProc) / deltaTotal * 100.0, 0.0, 100.0);
                }
            }
        }

        // Store current jiffies for next delta
        m_prevProcCpu[key] = ProcCpuState{utime, stime};

        // ── Memory% ─────────────────────────────────────
        double memPercent = (m_totalMemBytes > 0)
            ? static_cast<double>(rssBytes) / m_totalMemBytes * 100.0 : 0.0;

        // ── UID → username (cached) ─────────────────────
        QString username;
        if (uid >= 0) {
            auto it = m_uidCache.find(uid);
            if (it != m_uidCache.end()) {
                username = *it;
            } else {
                struct passwd pwd;
                struct passwd *result = nullptr;
                char buf[1024];
                if (getpwuid_r(uid, &pwd, buf, sizeof(buf), &result) == 0 && result)
                    username = QString::fromLocal8Bit(pwd.pw_name);
                else
                    username = QString::number(uid);
                m_uidCache.insert(uid, username);
            }
        }

        totalRss += rssBytes;

        // ── GPU% via DRM fdinfo ─────────────────────────────
        double gpuPercent = 0.0;
        QVector<ProcGpuClientDelta> gpuClientDeltas;

        if (pid > 0) {
            QString fdinfoPath = pidPath + QStringLiteral("/fdinfo");
            DIR *fdinfoDir = opendir(fdinfoPath.toUtf8().constData());

            if (!fdinfoDir) {
                if (errno == EACCES) {
                    gpuDeniedPids[pid] = key;
                }
            } else {
                gpuScannedThisPoll.insert(key);

                // Also open fd dir for readlink prefilter
                QString fdDirPath = pidPath + QStringLiteral("/fd");

                QSet<DrmClientKey> seenClientsInPid;
                QHash<DrmClientKey, quint64> perClientDeltaNs;

                struct dirent *dentry;
                while ((dentry = readdir(fdinfoDir)) != nullptr) {
                    if (dentry->d_name[0] == '.') continue;

                    // Readlink prefilter: skip non-DRM fds
                    QString fdNum = QString::fromLatin1(dentry->d_name);
                    QString fdLink = fdDirPath + QLatin1Char('/') + fdNum;
                    char linkBuf[256];
                    ssize_t linkLen = readlink(fdLink.toUtf8().constData(), linkBuf, sizeof(linkBuf) - 1);
                    if (linkLen > 0) {
                        linkBuf[linkLen] = '\0';
                        QByteArray target(linkBuf, linkLen);
                        if (!target.startsWith("/dev/dri/renderD") &&
                            !target.startsWith("/dev/dri/card") &&
                            !target.startsWith("/dev/dri/controlD")) {
                            continue;
                        }
                    }
                    // readlink failure → fall through and try fdinfo (race tolerance)

                    // Parse fdinfo file
                    QString fdinfoFile = fdinfoPath + QLatin1Char('/') + fdNum;
                    QFile f(fdinfoFile);
                    if (!f.open(QIODevice::ReadOnly | QIODevice::Text)) continue;

                    QByteArray content = f.readAll();
                    f.close();

                    QString driver;
                    QString pdev;
                    bool hasClientId = false;
                    quint64 clientId = 0;

                    // First pass: find driver, pdev, client-id
                    const auto lines = content.split('\n');
                    for (const QByteArray &lineRaw : lines) {
                        QString line = QString::fromUtf8(lineRaw);
                        if (line.startsWith(QLatin1String("drm-driver:"))) {
                            driver = line.mid(11).trimmed();
                        } else if (line.startsWith(QLatin1String("drm-pdev:"))) {
                            pdev = line.mid(9).trimmed();
                        } else if (line.startsWith(QLatin1String("drm-client-id:"))) {
                            bool ok = false;
                            quint64 cid = line.mid(14).trimmed().toULongLong(&ok);
                            if (ok) { clientId = cid; hasClientId = true; }
                        }
                    }

                    if (driver.isEmpty() || !hasClientId) continue;

                    DrmClientKey clientKey{driver, pdev, clientId};
                    if (seenClientsInPid.contains(clientKey)) continue;
                    seenClientsInPid.insert(clientKey);

                    // Second pass: parse drm-engine-* counters
                    for (const QByteArray &lineRaw : lines) {
                        QString line = QString::fromUtf8(lineRaw);
                        if (!line.startsWith(QLatin1String("drm-engine-"))) continue;
                        if (line.startsWith(QLatin1String("drm-engine-capacity-"))) continue;

                        int colonIdx = line.indexOf(QLatin1Char(':'));
                        if (colonIdx < 0) continue;

                        QString engineName = line.mid(11, colonIdx - 11);
                        QStringView valueStr = QStringView(line).mid(colonIdx + 1);

                        quint64 ns = 0;
                        if (!parseEngineNs(valueStr, ns)) continue;

                        ProcGpuKey gpuKey{key, clientKey, engineName};
                        gpuSeenThisPoll.insert(gpuKey);

                        quint64 delta = 0;
                        auto prevIt = m_prevProcGpuEngine.find(gpuKey);
                        if (prevIt == m_prevProcGpuEngine.end()) {
                            m_prevProcGpuEngine[gpuKey] = ns;
                        } else if (ns >= *prevIt) {
                            delta = ns - *prevIt;
                            *prevIt = ns;
                        }
                        // else: rollback — keep previous, delta stays 0

                        perClientDeltaNs[clientKey] += delta;
                    }
                }
                closedir(fdinfoDir);

                // Compute per-pid GPU% and build client deltas
                quint64 pidTotalNs = 0;
                for (auto it = perClientDeltaNs.cbegin(); it != perClientDeltaNs.cend(); ++it) {
                    pidTotalNs += it.value();
                    if (it.value() > 0) {
                        ProcGpuClientDelta cd;
                        cd.driver = it.key().driver;
                        cd.pdev = it.key().pdev;
                        cd.clientId = it.key().clientId;
                        cd.deltaNs = it.value();
                        gpuClientDeltas.append(cd);
                    }
                }

                if (elapsedNs > 0) {
                    gpuPercent = std::clamp(
                        static_cast<double>(pidTotalNs) / static_cast<double>(elapsedNs) * 100.0,
                        0.0, 100.0);
                }
            }
        }

        ProcessInfo info;
        info.pid = pid;
        info.ppid = ppid;
        info.name = comm;
        info.user = username;
        info.status = stateToString(stateChar);
        info.cpuPercent = cpuPercent;
        info.memoryPercent = memPercent;
        info.gpuPercent = gpuPercent;
        info.rssBytes = rssBytes;
        info.sharedBytes = sharedBytes;
        info.swapBytes = swapBytes;
        info.readBytes = readB;
        info.writeBytes = writeB;
        info.numThreads = numThreads;
        info.gpuClientDeltas = gpuClientDeltas;

        stats.processes.append(info);
    }

    // 3b. Escalated GPU for denied PIDs (non-dumpable / other-user processes).
    // Asynchronous — never blocks the worker waiting on the pkexec helper.
    pumpEscalatedGpu(gpuDeniedPids, seenKeys, gpuSeenThisPoll,
                     gpuScannedThisPoll, elapsedNs, stats);

    // 4. Memory normalization (Python parity)
    long long totalUsed = m_totalMemBytes - availableBytes;
    double sysMemPercent = 0.0;
    long long sysMemBytes = 0;
    if (totalRss > totalUsed && totalUsed > 0) {
        double ratio = static_cast<double>(totalUsed) / totalRss;
        for (auto &p : stats.processes) {
            p.memoryPercent *= ratio;
            p.rssBytes = static_cast<long long>(p.rssBytes * ratio);
            p.sharedBytes = static_cast<long long>(p.sharedBytes * ratio);
        }
    } else {
        sysMemBytes = std::max(0LL, totalUsed - totalRss);
        if (sysMemBytes > 0 && m_totalMemBytes > 0)
            sysMemPercent = static_cast<double>(sysMemBytes) / m_totalMemBytes * 100.0;
    }

    // 4b. CPU gap: overall CPU% minus sum of per-process CPU%
    double sysCpuPercent = 0.0;
    if (!m_procFirstPoll) {
        long long totalDelta = totalJiffies.totalTicks() - m_prevProcJiffies.totalTicks();
        long long idleDelta = totalJiffies.idleTicks() - m_prevProcJiffies.idleTicks();
        if (totalDelta > 0) {
            double overallCpu = static_cast<double>(totalDelta - idleDelta) / totalDelta * 100.0;
            double sumProcCpu = 0.0;
            for (const auto &p : stats.processes)
                sumProcCpu += p.cpuPercent;
            sysCpuPercent = std::max(0.0, overallCpu - sumProcCpu);
        }
    }

    // 4c. Create synthetic entry if there's any unattributed memory or CPU
    if (sysMemBytes > 0 || sysCpuPercent > 0.05) {
        ProcessInfo sysEntry;
        sysEntry.pid = -1;
        sysEntry.name = QStringLiteral("System / Kernel / Other");
        sysEntry.memoryPercent = sysMemPercent;
        sysEntry.rssBytes = sysMemBytes;
        sysEntry.cpuPercent = sysCpuPercent;
        sysEntry.user = QStringLiteral("root");
        sysEntry.status = QStringLiteral("running");
        stats.processes.append(sysEntry);
    }

    // 5. Clean up stale entries from jiffies cache
    auto it = m_prevProcCpu.begin();
    while (it != m_prevProcCpu.end()) {
        if (!seenKeys.contains(it.key()))
            it = m_prevProcCpu.erase(it);
        else
            ++it;
    }

    // 6. Prune GPU engine state — stale engines of PIDs scanned this poll,
    //    plus all state for PIDs that no longer exist
    {
        auto git = m_prevProcGpuEngine.begin();
        while (git != m_prevProcGpuEngine.end()) {
            bool procGone = !seenKeys.contains(git.key().proc);
            bool staleEngine = gpuScannedThisPoll.contains(git.key().proc) &&
                               !gpuSeenThisPoll.contains(git.key());
            if (procGone || staleEngine) {
                git = m_prevProcGpuEngine.erase(git);
            } else {
                ++git;
            }
        }
    }

    // 7. Update state for next poll
    m_prevProcJiffies = totalJiffies;
    m_procFirstPoll = false;
    m_gpuProcFirstPoll = false;

    stats.gpuPollElapsedNs = elapsedNs;
    stats.valid = true;
    return stats;
}

// ── Persistent escalated GPU helper via pkexec ──────────────

// One find(1) sweep per request instead of a readlink fork per fd —
// with hundreds of denied pids the fork-per-fd loop took seconds per
// scan (and pegged a core); a single find does the same in ~200ms.
static const char *s_helperScript =
    "while IFS= read -r line; do "
    "  case \"$line\" in "
    "    QUIT) exit 0 ;; "
    "    PIDS:*) "
    "      pids=\"${line#PIDS:}\"; "
    "      if [ -n \"${pids// /}\" ]; then "
    "        dirs=''; "
    "        for pid in $pids; do dirs=\"$dirs /proc/$pid/fd\"; done; "
    "        for link in $(find $dirs -maxdepth 1 -lname '/dev/dri/*' 2>/dev/null); do "
    "          fd=\"${link##*/}\"; rest=\"${link%/fd/*}\"; pid=\"${rest##*/}\"; "
    "          echo \"===PID:${pid}:FD:${fd}===\"; "
    "          cat \"/proc/$pid/fdinfo/$fd\" 2>/dev/null; "
    "        done; "
    "      fi; "
    "      echo '===DONE==='; "
    "      ;; "
    "  esac; "
    "done";

bool SystemMonitorWorker::ensureEscalatedHelper() {
    if (m_escalatedHelper && m_escalatedHelper->state() == QProcess::Running)
        return true;

    if (!m_gpuEscalationAvailable || m_gpuEscalationAttempted)
        return false;

    m_gpuEscalationAttempted = true;

    delete m_escalatedHelper;
    m_escalatedHelper = new QProcess(this);

    QStringList args;
    args << m_bashPath << QStringLiteral("-c") << QString::fromLatin1(s_helperScript);
    m_escalatedHelper->start(m_pkexecPath, args);

    if (!m_escalatedHelper->waitForStarted(15000)) {
        delete m_escalatedHelper;
        m_escalatedHelper = nullptr;
        m_gpuEscalationAvailable = false;
        return false;
    }

    // Send a test request and wait for the full DONE marker to confirm auth
    // succeeded (a single waitForReadyRead can deliver a partial response)
    m_escalatedHelper->write("PIDS:\n");
    QByteArray testResponse;
    QElapsedTimer testTimer;
    testTimer.start();
    while (!testResponse.contains("===DONE===")) {
        if (testTimer.elapsed() > 20000 ||
            !m_escalatedHelper->waitForReadyRead(15000)) {
            int exitCode = m_escalatedHelper->exitCode();
            if (exitCode == 126 || exitCode == 127)
                m_gpuEscalationAvailable = false;
            delete m_escalatedHelper;
            m_escalatedHelper = nullptr;
            return false;
        }
        testResponse.append(m_escalatedHelper->readAllStandardOutput());
    }

    // Helper validated — reset async request state
    m_escalatedBuffer.clear();
    m_escalatedPending = false;
    m_escalatedElapsed.start();
    return true;
}

void SystemMonitorWorker::stopEscalatedHelper() {
    if (!m_escalatedHelper) return;
    if (m_escalatedHelper->state() == QProcess::Running) {
        m_escalatedHelper->write("QUIT\n");
        m_escalatedHelper->waitForFinished(2000);
    }
    delete m_escalatedHelper;
    m_escalatedHelper = nullptr;
    m_escalatedBuffer.clear();
    m_escalatedPending = false;
}

// ── Async escalated GPU pump ────────────────────────────────
// Called every process poll. Never blocks on the helper: drains any
// completed response, re-applies cached per-pid GPU rates to the
// current stats, and sends the next request only when the previous
// one has finished. (The old synchronous wait stalled the whole
// worker thread — including the 500ms dashboard timer — for up to
// 5s whenever the helper fell behind.)

void SystemMonitorWorker::pumpEscalatedGpu(
    const QHash<int, ProcKey> &deniedPids,
    const QSet<ProcKey> &seenKeys,
    QSet<ProcGpuKey> &gpuSeenThisPoll,
    QSet<ProcKey> &gpuScannedThisPoll,
    quint64 pollElapsedNs,
    ProcessStats &stats)
{
    if (!m_gpuEscalationAvailable) return;
    if (!m_escalatedHelper && deniedPids.isEmpty()) return;
    if (!ensureEscalatedHelper()) return;

    qint64 now = QDateTime::currentMSecsSinceEpoch();

    // 1. Drain helper output; parse once a full response has arrived
    m_escalatedBuffer.append(m_escalatedHelper->readAllStandardOutput());
    int doneIdx = m_escalatedBuffer.indexOf("===DONE===");
    if (doneIdx >= 0) {
        QByteArray response = m_escalatedBuffer.left(doneIdx);
        m_escalatedBuffer.remove(0, doneIdx + 10); // strlen("===DONE===")
        double responseSec = m_escalatedElapsed.restart() / 1000.0;
        parseEscalatedResponse(response, responseSec,
                               gpuSeenThisPoll, gpuScannedThisPoll);
        m_escalatedPending = false;
    }

    // Wedge guard: helper unresponsive for far too long — give up
    if (m_escalatedPending && now - m_escalatedRequestMs > 20000) {
        stopEscalatedHelper();
        m_gpuEscalationAvailable = false;
        return;
    }

    // 2. Drop cached rates for processes that no longer exist
    {
        auto it = m_escalatedRates.begin();
        while (it != m_escalatedRates.end()) {
            if (!seenKeys.contains(it.key()))
                it = m_escalatedRates.erase(it);
            else
                ++it;
        }
    }

    // 3. Apply cached rates to this poll's process entries
    for (auto it = deniedPids.cbegin(); it != deniedPids.cend(); ++it) {
        auto rit = m_escalatedRates.constFind(it.value());
        if (rit == m_escalatedRates.constEnd()) continue;

        for (auto &p : stats.processes) {
            if (p.pid != it.key()) continue;
            p.gpuPercent = rit->ratePercent;
            // Rates are ns-per-second — scale to this poll's window so the
            // grouped view (which divides by gpuPollElapsedNs) stays correct
            p.gpuClientDeltas = rit->clientRates;
            for (auto &cd : p.gpuClientDeltas)
                cd.deltaNs = static_cast<quint64>(
                    cd.deltaNs * (static_cast<double>(pollElapsedNs) / 1e9));
            break;
        }
    }

    // 4. Send the next request once the previous one completed
    if (!m_escalatedPending && !deniedPids.isEmpty() &&
        now - m_lastEscalatedReadMs >= 2000) {
        m_lastEscalatedReadMs = now;
        m_escalatedRequestMs = now;
        m_escalatedSentKeys = deniedPids;

        QStringList pidStrs;
        for (auto it = deniedPids.cbegin(); it != deniedPids.cend(); ++it)
            pidStrs.append(QString::number(it.key()));
        QString request = QStringLiteral("PIDS:") + pidStrs.join(QLatin1Char(' '))
                          + QLatin1Char('\n');
        m_escalatedHelper->write(request.toUtf8());
        m_escalatedPending = true;
    }
}

// Parse one complete helper response. Engine deltas are divided by the
// time between responses (not the 1s poll interval — responses arrive
// every ~2s) and cached as per-second rates in m_escalatedRates.

void SystemMonitorWorker::parseEscalatedResponse(
    const QByteArray &response, double responseSec,
    QSet<ProcGpuKey> &gpuSeenThisPoll,
    QSet<ProcKey> &gpuScannedThisPoll)
{
    const QList<QByteArray> lines = response.split('\n');

    int currentPid = 0;
    ProcKey currentKey;
    bool skipPid = true;

    // Per-fd identity state
    QString driver;
    QString pdev;
    bool hasClientId = false;
    quint64 clientId = 0;
    bool fdCommitted = false;  // first engine line commits the client
    bool fdDuplicate = false;  // fd belongs to an already-counted client

    QSet<DrmClientKey> seenClientsInPid;
    QHash<DrmClientKey, quint64> perClientDeltaNs;

    auto flushPid = [&]() {
        if (currentPid <= 0 || skipPid) return;

        gpuScannedThisPoll.insert(currentKey);

        quint64 pidTotalNs = 0;
        EscalatedGpuRate rate;
        for (auto cit = perClientDeltaNs.cbegin(); cit != perClientDeltaNs.cend(); ++cit) {
            pidTotalNs += cit.value();
            if (cit.value() > 0 && responseSec > 0) {
                ProcGpuClientDelta cd;
                cd.driver = cit.key().driver;
                cd.pdev = cit.key().pdev;
                cd.clientId = cit.key().clientId;
                cd.deltaNs = static_cast<quint64>(cit.value() / responseSec);
                rate.clientRates.append(cd);
            }
        }
        rate.ratePercent = (responseSec > 0)
            ? std::clamp(static_cast<double>(pidTotalNs)
                         / (responseSec * 1e9) * 100.0, 0.0, 100.0)
            : 0.0;
        m_escalatedRates[currentKey] = rate;
    };

    for (const QByteArray &rawLine : lines) {
        QString line = QString::fromUtf8(rawLine);

        if (line.startsWith(QLatin1String("===PID:"))) {
            QStringList parts = line.mid(7).split(QLatin1Char(':'));
            int markerPid = (parts.size() >= 3) ? parts[0].toInt() : 0;

            if (markerPid != currentPid) {
                flushPid();
                currentPid = markerPid;
                seenClientsInPid.clear();
                perClientDeltaNs.clear();
                auto keyIt = m_escalatedSentKeys.constFind(currentPid);
                if (keyIt != m_escalatedSentKeys.constEnd()) {
                    currentKey = *keyIt;
                    skipPid = false;
                } else {
                    skipPid = true; // pid we never asked about
                }
            }

            // New fd block — reset identity state
            driver.clear();
            pdev.clear();
            hasClientId = false;
            clientId = 0;
            fdCommitted = false;
            fdDuplicate = false;
            continue;
        }

        if (currentPid <= 0 || skipPid) continue;

        if (line.startsWith(QLatin1String("drm-driver:"))) {
            driver = line.mid(11).trimmed();
        } else if (line.startsWith(QLatin1String("drm-pdev:"))) {
            pdev = line.mid(9).trimmed();
        } else if (line.startsWith(QLatin1String("drm-client-id:"))) {
            bool ok = false;
            quint64 cid = line.mid(14).trimmed().toULongLong(&ok);
            if (ok) { clientId = cid; hasClientId = true; }
        } else if (line.startsWith(QLatin1String("drm-engine-")) &&
                   !line.startsWith(QLatin1String("drm-engine-capacity-"))) {
            if (driver.isEmpty() || !hasClientId) continue;

            DrmClientKey ck{driver, pdev, clientId};
            if (!fdCommitted) {
                fdCommitted = true;
                fdDuplicate = seenClientsInPid.contains(ck);
                if (!fdDuplicate)
                    seenClientsInPid.insert(ck);
            }
            if (fdDuplicate) continue;

            int colonIdx = line.indexOf(QLatin1Char(':'));
            if (colonIdx < 0) continue;

            QString engineName = line.mid(11, colonIdx - 11);
            QStringView valueStr = QStringView(line).mid(colonIdx + 1);

            quint64 ns = 0;
            if (!parseEngineNs(valueStr, ns)) continue;

            ProcGpuKey gpuKey{currentKey, ck, engineName};
            gpuSeenThisPoll.insert(gpuKey);

            quint64 delta = 0;
            auto prevIt = m_prevProcGpuEngine.find(gpuKey);
            if (prevIt == m_prevProcGpuEngine.end()) {
                m_prevProcGpuEngine[gpuKey] = ns;
            } else if (ns >= *prevIt) {
                delta = ns - *prevIt;
                *prevIt = ns;
            }
            // else: rollback — keep previous, delta stays 0

            perClientDeltaNs[ck] += delta;
        }
    }

    flushPid();
}

// ── One-time discovery: CPU frequency paths ─────────────────

void SystemMonitorWorker::discoverCpuCores() {
    m_freqPaths.clear();
    int i = 0;
    while (true) {
        QString path = QStringLiteral("/sys/devices/system/cpu/cpu%1/cpufreq/scaling_cur_freq").arg(i);
        if (!QFile::exists(path)) break;
        m_freqPaths.append(path);
        ++i;
    }
}

// ── One-time discovery: AMD GPU sysfs paths ─────────────────

void SystemMonitorWorker::discoverAmdGpuPaths() {
    m_amdGpuPaths.clear();
    QDir drm(QStringLiteral("/sys/class/drm"));
    if (!drm.exists()) return;

    const QStringList cards = drm.entryList({QStringLiteral("card*")}, QDir::Dirs);
    for (const QString &card : cards) {
        QString path = drm.absoluteFilePath(card) +
                        QStringLiteral("/device/gpu_busy_percent");
        if (QFile::exists(path))
            m_amdGpuPaths.append(path);
    }
}

// ── One-time discovery: hwmon sensors ───────────────────────

// Map kernel driver names to human-readable chip names
static QString friendlyChipName(const QString &chipName, const QString &hwPath) {
    // NVMe: use the drive model name if available
    if (chipName == QLatin1String("nvme")) {
        QString model = readFileContents(hwPath + QStringLiteral("/device/model")).trimmed();
        if (!model.isEmpty()) return model;
    }

    // Known chip name mappings
    static const QHash<QString, QString> chipMap = {
        {QStringLiteral("acpitz"),       QStringLiteral("ACPI")},
        {QStringLiteral("k10temp"),      QStringLiteral("CPU")},
        {QStringLiteral("coretemp"),     QStringLiteral("CPU")},
        {QStringLiteral("amdgpu"),       QStringLiteral("GPU")},
        {QStringLiteral("nouveau"),      QStringLiteral("GPU")},
        {QStringLiteral("radeon"),       QStringLiteral("GPU")},
        {QStringLiteral("gigabyte_wmi"), QStringLiteral("Motherboard")},
        {QStringLiteral("asus_wmi"),     QStringLiteral("Motherboard")},
        {QStringLiteral("nct6775"),      QStringLiteral("Motherboard")},
        {QStringLiteral("nct6776"),      QStringLiteral("Motherboard")},
        {QStringLiteral("nct6779"),      QStringLiteral("Motherboard")},
        {QStringLiteral("nct6791"),      QStringLiteral("Motherboard")},
        {QStringLiteral("nct6792"),      QStringLiteral("Motherboard")},
        {QStringLiteral("nct6795"),      QStringLiteral("Motherboard")},
        {QStringLiteral("nct6796"),      QStringLiteral("Motherboard")},
        {QStringLiteral("nct6797"),      QStringLiteral("Motherboard")},
        {QStringLiteral("nct6798"),      QStringLiteral("Motherboard")},
        {QStringLiteral("it8688"),       QStringLiteral("Motherboard")},
        {QStringLiteral("it8689"),       QStringLiteral("Motherboard")},
        {QStringLiteral("it8686"),       QStringLiteral("Motherboard")},
        {QStringLiteral("it87"),         QStringLiteral("Motherboard")},
        {QStringLiteral("iwlwifi"),      QStringLiteral("WiFi")},
        {QStringLiteral("mt7921"),       QStringLiteral("WiFi")},
        {QStringLiteral("ath10k"),       QStringLiteral("WiFi")},
        {QStringLiteral("ath11k"),       QStringLiteral("WiFi")},
        {QStringLiteral("kraken2023"),   QStringLiteral("AIO Cooler")},
        {QStringLiteral("kraken3"),      QStringLiteral("AIO Cooler")},
        {QStringLiteral("corsaircpro"),  QStringLiteral("AIO Cooler")},
    };

    auto it = chipMap.constFind(chipName);
    if (it != chipMap.constEnd())
        return it.value();

    // Network cards: r8169, igb, e1000e, etc.
    if (chipName.startsWith(QLatin1String("r8169")) ||
        chipName.startsWith(QLatin1String("igb")) ||
        chipName.startsWith(QLatin1String("e1000")) ||
        chipName.startsWith(QLatin1String("igc")) ||
        chipName.startsWith(QLatin1String("mlx")))
        return QStringLiteral("Network");

    return chipName; // Unknown — use raw name
}

// Map known cryptic sensor labels to friendly names
static QString friendlyLabel(const QString &rawLabel, const QString &friendlyChip,
                              const QString &chipName) {
    static const QHash<QString, QString> labelMap = {
        {QStringLiteral("Tctl"),  QStringLiteral("CPU Package")},
        {QStringLiteral("Tdie"),  QStringLiteral("CPU Die")},
        {QStringLiteral("Tccd1"), QStringLiteral("CPU CCD1")},
        {QStringLiteral("Tccd2"), QStringLiteral("CPU CCD2")},
        {QStringLiteral("Tccd3"), QStringLiteral("CPU CCD3")},
        {QStringLiteral("Tccd4"), QStringLiteral("CPU CCD4")},
        {QStringLiteral("edge"),  QStringLiteral("GPU Edge")},
        {QStringLiteral("junction"), QStringLiteral("GPU Junction")},
        {QStringLiteral("mem"),   QStringLiteral("GPU Memory")},
    };

    auto it = labelMap.constFind(rawLabel);
    if (it != labelMap.constEnd())
        return it.value();

    // NVMe: prefix generic labels with the drive model name
    if (chipName == QLatin1String("nvme") && !friendlyChip.isEmpty())
        return QStringLiteral("%1: %2").arg(friendlyChip, rawLabel);

    return rawLabel; // Keep as-is if not mapped
}

void SystemMonitorWorker::discoverHwmonSensors() {
    m_hwmonSensors.clear();

    QDir hwmonRoot(QStringLiteral("/sys/class/hwmon"));
    if (!hwmonRoot.exists()) return;

    const QStringList hwmonDirs = hwmonRoot.entryList(QDir::Dirs | QDir::NoDotAndDotDot);

    // Track label counts for deduplication
    QHash<QString, int> labelCounts;

    for (const QString &hwDir : hwmonDirs) {
        QString hwPath = hwmonRoot.absoluteFilePath(hwDir);

        // Read chip name (e.g., "coretemp", "nct6775", "amdgpu")
        QString chipName = readFileContents(hwPath + QStringLiteral("/name")).trimmed();
        QString friendly = friendlyChipName(chipName, hwPath);

        // Discover temperature sensors: temp*_input
        QDir dir(hwPath);
        QStringList tempInputs = dir.entryList({QStringLiteral("temp*_input")}, QDir::Files);
        for (const QString &inputFile : tempInputs) {
            // Extract index: temp1_input → "1"
            QString idx = inputFile.mid(4, inputFile.indexOf(QLatin1Char('_')) - 4);

            // Try to read label
            QString labelPath = hwPath + QStringLiteral("/temp%1_label").arg(idx);
            QString rawLabel = readFileContents(labelPath).trimmed();

            QString label;
            if (!rawLabel.isEmpty()) {
                label = friendlyLabel(rawLabel, friendly, chipName);
            } else {
                // No label file — use friendly chip name + index
                label = friendly.isEmpty()
                    ? QStringLiteral("Temp %1").arg(idx)
                    : QStringLiteral("%1 Temp %2").arg(friendly, idx);
            }

            HwmonSensor sensor;
            sensor.label = label;
            sensor.inputPath = hwPath + QLatin1Char('/') + inputFile;
            sensor.type = HwmonSensor::Temperature;
            m_hwmonSensors.append(sensor);
            labelCounts[label]++;
        }

        // Discover fan sensors: fan*_input
        QStringList fanInputs = dir.entryList({QStringLiteral("fan*_input")}, QDir::Files);
        for (const QString &inputFile : fanInputs) {
            QString idx = inputFile.mid(3, inputFile.indexOf(QLatin1Char('_')) - 3);

            QString labelPath = hwPath + QStringLiteral("/fan%1_label").arg(idx);
            QString rawLabel = readFileContents(labelPath).trimmed();

            QString label;
            if (!rawLabel.isEmpty()) {
                label = friendlyLabel(rawLabel, friendly, chipName);
            } else {
                label = friendly.isEmpty()
                    ? QStringLiteral("Fan %1").arg(idx)
                    : QStringLiteral("%1 Fan %2").arg(friendly, idx);
            }

            HwmonSensor sensor;
            sensor.label = label;
            sensor.inputPath = hwPath + QLatin1Char('/') + inputFile;
            sensor.type = HwmonSensor::Fan;
            m_hwmonSensors.append(sensor);
            labelCounts[label]++;
        }
    }

    // Deduplicate: if any label appears more than once, append a suffix
    QHash<QString, int> suffixCounter;
    for (HwmonSensor &sensor : m_hwmonSensors) {
        if (labelCounts.value(sensor.label) > 1) {
            int n = ++suffixCounter[sensor.label];
            sensor.label = QStringLiteral("%1 #%2").arg(sensor.label).arg(n);
        }
    }
}
