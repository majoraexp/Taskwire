#pragma once

#include <QObject>
#include <QString>
#include <QVector>
#include <QHash>
#include <QSet>
#include <QMap>
#include <QPair>
#include <QMetaType>
#include <QElapsedTimer>

// ── Data structs ─────────────────────────────────────────────

struct CpuStats {
    double overallPercent = 0.0;
    QVector<double> corePercents;
    QVector<double> coreFreqsMHz;
    bool valid = false;
};

struct MemoryStats {
    long long totalBytes = 0;
    long long availableBytes = 0;
    long long usedBytes = 0;
    long long freeBytes = 0;
    long long buffersBytes = 0;
    long long cachedBytes = 0;
    double percent = 0.0;
    long long swapTotal = 0;
    long long swapUsed = 0;
    double swapPercent = 0.0;
    bool valid = false;
};

struct GpuStats {
    double usagePercent = 0.0;
    bool valid = false;
};

struct DiskInfo {
    QString model;
    long long sizeBytes = 0;
    long long usedBytes = 0;
    double percent = 0.0;
};

struct DiskUsageStats {
    QMap<QString, DiskInfo> disks; // key: "/dev/sda" etc.
    bool valid = false;
};

struct DiskIoStats {
    double readBytesPerSec = 0.0;
    double writeBytesPerSec = 0.0;
    bool valid = false;
};

struct NetworkStats {
    double uploadBytesPerSec = 0.0;
    double downloadBytesPerSec = 0.0;
    bool valid = false;
};

struct TempReading {
    QString label;
    double celsius = 0.0;
};

struct FanReading {
    QString label;
    int rpm = 0;
};

struct TempStats {
    QVector<TempReading> temps;
    bool valid = false;
};

struct FanStats {
    QVector<FanReading> fans;
    bool valid = false;
};

struct ProcessInfo {
    int pid = 0;
    int ppid = 0;
    QString name;
    QString user;
    QString status;   // "running", "sleeping", etc.
    double cpuPercent = 0.0;
    double memoryPercent = 0.0;
    long long rssBytes = 0;
    long long sharedBytes = 0;
    long long swapBytes = 0;
    long long readBytes = 0;
    long long writeBytes = 0;
    int numThreads = 0;
};

struct ProcessStats {
    QVector<ProcessInfo> processes;
    bool valid = false;
};

Q_DECLARE_METATYPE(CpuStats)
Q_DECLARE_METATYPE(MemoryStats)
Q_DECLARE_METATYPE(GpuStats)
Q_DECLARE_METATYPE(DiskUsageStats)
Q_DECLARE_METATYPE(DiskIoStats)
Q_DECLARE_METATYPE(NetworkStats)
Q_DECLARE_METATYPE(TempStats)
Q_DECLARE_METATYPE(FanStats)
Q_DECLARE_METATYPE(ProcessStats)

// ── Cached hwmon sensor path ────────────────────────────────

struct HwmonSensor {
    QString label;
    QString inputPath; // absolute path to *_input file
    enum Type { Temperature, Fan } type;
};

// ── Cached CPU jiffies for delta computation ────────────────

struct CpuJiffies {
    long long user = 0, nice = 0, system = 0, idle = 0;
    long long iowait = 0, irq = 0, softirq = 0, steal = 0;

    long long totalTicks() const {
        return user + nice + system + idle + iowait + irq + softirq + steal;
    }
    long long idleTicks() const {
        return idle + iowait;
    }
};

// ── PID-reuse-safe key for per-process CPU tracking ─────────

struct ProcKey {
    int pid = 0;
    unsigned long long starttime = 0;

    bool operator==(const ProcKey &other) const {
        return pid == other.pid && starttime == other.starttime;
    }
};

inline size_t qHash(const ProcKey &key, size_t seed = 0) {
    return qHashMulti(seed, key.pid, key.starttime);
}

struct ProcCpuState {
    unsigned long long utime = 0;
    unsigned long long stime = 0;
};

// ── Worker (lives in a dedicated QThread) ───────────────────

class QTimer;

class SystemMonitorWorker : public QObject {
    Q_OBJECT

public:
    explicit SystemMonitorWorker(QObject *parent = nullptr);

signals:
    void cpuUpdate(const CpuStats &stats);
    void memoryUpdate(const MemoryStats &stats);
    void gpuUpdate(const GpuStats &stats);
    void diskUpdate(const DiskUsageStats &stats);
    void diskIoUpdate(const DiskIoStats &stats);
    void networkUpdate(const NetworkStats &stats);
    void tempUpdate(const TempStats &stats);
    void fanUpdate(const FanStats &stats);
    void processUpdate(const ProcessStats &stats);

public slots:
    void startPolling();
    void stopPolling();

private slots:
    void pollFast();   // 500ms — CPU, memory, GPU, disk IO, network, temps, fans
    void pollSlow();   // 5s   — disk usage (lsblk subprocess)
    void pollMedium(); // 1s   — process list

private:
    // Parsers
    CpuStats readCpu();
    MemoryStats readMemory();
    GpuStats readGpu();
    DiskIoStats readDiskIo(double deltaSec);
    NetworkStats readNetwork(double deltaSec);
    TempStats readTemps();
    FanStats readFans();
    DiskUsageStats readDiskUsage();
    ProcessStats readProcesses();

    // One-time discovery
    void discoverHwmonSensors();
    void discoverCpuCores();
    void discoverAmdGpuPaths();

    // Timers
    QTimer *m_fastTimer = nullptr;
    QTimer *m_slowTimer = nullptr;
    QTimer *m_mediumTimer = nullptr;

    // CPU state
    CpuJiffies m_prevOverall;
    QVector<CpuJiffies> m_prevPerCore;
    QVector<QString> m_freqPaths; // /sys/devices/system/cpu/cpuN/cpufreq/scaling_cur_freq
    bool m_cpuFirstPoll = true;

    // GPU state
    QStringList m_amdGpuPaths;
    bool m_hasNvidiaSmi = false;
    QString m_nvidiaSmiPath;

    // Disk IO state
    long long m_prevDiskReadBytes = 0;
    long long m_prevDiskWriteBytes = 0;
    bool m_diskIoFirstPoll = true;

    // Network state
    long long m_prevNetRxBytes = 0;
    long long m_prevNetTxBytes = 0;
    bool m_netFirstPoll = true;

    // Timing — QElapsedTimer for accurate rate deltas
    QElapsedTimer m_fastElapsed;

    // Hwmon cache
    QVector<HwmonSensor> m_hwmonSensors;

    // Disk usage (polled slowly)
    QString m_lsblkPath;

    // Process state tracking
    QHash<ProcKey, ProcCpuState> m_prevProcCpu;
    QHash<int, QString> m_uidCache;  // uid -> username
    long long m_totalMemBytes = 0;
    int m_numCores = 0;
    long m_pageSize = 4096;
    CpuJiffies m_prevProcJiffies;    // total CPU jiffies for process CPU% delta
    bool m_procFirstPoll = true;
};
