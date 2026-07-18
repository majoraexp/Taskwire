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

Q_DECLARE_METATYPE(CpuStats)
Q_DECLARE_METATYPE(MemoryStats)
Q_DECLARE_METATYPE(GpuStats)
Q_DECLARE_METATYPE(DiskUsageStats)
Q_DECLARE_METATYPE(DiskIoStats)
Q_DECLARE_METATYPE(NetworkStats)
Q_DECLARE_METATYPE(TempStats)
Q_DECLARE_METATYPE(FanStats)

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

// ── DRM GPU per-process tracking ───────────────────────────

struct DrmClientKey {
    QString driver;
    QString pdev;
    quint64 clientId = 0;

    bool operator==(const DrmClientKey &o) const {
        return clientId == o.clientId && pdev == o.pdev && driver == o.driver;
    }
};

inline size_t qHash(const DrmClientKey &k, size_t seed = 0) {
    return qHashMulti(seed, k.driver, k.pdev, k.clientId);
}

struct ProcGpuKey {
    ProcKey proc;
    DrmClientKey client;
    QString engineName;

    bool operator==(const ProcGpuKey &o) const {
        return proc == o.proc && client == o.client && engineName == o.engineName;
    }
};

inline size_t qHash(const ProcGpuKey &k, size_t seed = 0) {
    return qHashMulti(seed, k.proc.pid, k.proc.starttime,
                      k.client.driver, k.client.pdev, k.client.clientId,
                      k.engineName);
}

struct ProcGpuClientDelta {
    QString  driver;
    QString  pdev;
    quint64  clientId = 0;
    quint64  deltaNs  = 0;
};

// ── Process structs (after DRM types for ProcGpuClientDelta) ─

struct ProcessInfo {
    int pid = 0;
    int ppid = 0;
    QString name;
    QString user;
    QString status;   // "running", "sleeping", etc.
    double cpuPercent = 0.0;
    double memoryPercent = 0.0;
    double gpuPercent = 0.0;
    long long rssBytes = 0;
    long long sharedBytes = 0;
    long long swapBytes = 0;
    long long readBytes = 0;
    long long writeBytes = 0;
    int numThreads = 0;
    QVector<ProcGpuClientDelta> gpuClientDeltas;
};

struct ProcessStats {
    QVector<ProcessInfo> processes;
    quint64 gpuPollElapsedNs = 0;
    bool valid = false;
};

Q_DECLARE_METATYPE(ProcessStats)

// ── Worker (lives in a dedicated QThread) ───────────────────

class QTimer;
class QProcess;

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

    // GPU per-process state (DRM fdinfo)
    QHash<ProcGpuKey, quint64> m_prevProcGpuEngine;
    QElapsedTimer m_procPollElapsed;
    qint64 m_prevProcPollNs = 0;
    bool m_gpuProcFirstPoll = true;

    // GPU escalated read (persistent pkexec helper for non-dumpable processes).
    // Fully asynchronous: requests are sent without waiting, responses are
    // drained and parsed on later polls, and the resulting per-process GPU
    // rates are cached and re-applied every poll until the next response.
    struct EscalatedGpuRate {
        double ratePercent = 0.0;
        QVector<ProcGpuClientDelta> clientRates; // deltaNs holds ns-per-second
    };
    void pumpEscalatedGpu(const QHash<int, ProcKey> &deniedPids,
                          const QSet<ProcKey> &seenKeys,
                          QSet<ProcGpuKey> &gpuSeenThisPoll,
                          QSet<ProcKey> &gpuScannedThisPoll,
                          quint64 pollElapsedNs,
                          ProcessStats &stats);
    void parseEscalatedResponse(const QByteArray &response, double responseSec,
                                QSet<ProcGpuKey> &gpuSeenThisPoll,
                                QSet<ProcKey> &gpuScannedThisPoll);
    bool ensureEscalatedHelper();
    void stopEscalatedHelper();
    QProcess *m_escalatedHelper = nullptr;
    QString m_pkexecPath;
    QString m_bashPath;
    bool m_gpuEscalationAvailable = true;
    bool m_gpuEscalationAttempted = false;
    qint64 m_lastEscalatedReadMs = 0;
    QByteArray m_escalatedBuffer;            // partial helper stdout
    bool m_escalatedPending = false;         // a request is in flight
    qint64 m_escalatedRequestMs = 0;         // when it was sent
    QHash<int, ProcKey> m_escalatedSentKeys; // pid → key of in-flight request
    QElapsedTimer m_escalatedElapsed;        // time between parsed responses
    QHash<ProcKey, EscalatedGpuRate> m_escalatedRates; // cached results
};
