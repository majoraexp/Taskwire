#pragma once
#include <QMainWindow>
#include "systemmonitor.h"
#include "toppanel.h"
#include "cpuwidget.h"
#include "memorywidget.h"
#include "historywidget.h"
#include "tempgraphwidget.h"
#include "diskwidget.h"
#include "networkwidget.h"
#include "processlistwidget.h"
#include "serviceswidget.h"
#include "connectionswidget.h"
#include "journalwidget.h"
#include "toolswidget.h"

class QTabWidget;
class QThread;
class QActionGroup;
class QLabel;

class MainWindow : public QMainWindow {
    Q_OBJECT

public:
    explicit MainWindow(QWidget *parent = nullptr);
    ~MainWindow() override;

private slots:
    void switchTheme(const QString &mode);
    void onDurationChanged(QAction *action);

    // Data update slots
    void onCpuUpdate(const CpuStats &stats);
    void onMemoryUpdate(const MemoryStats &stats);
    void onGpuUpdate(const GpuStats &stats);
    void onDiskUpdate(const DiskUsageStats &stats);
    void onDiskIoUpdate(const DiskIoStats &stats);
    void onNetworkUpdate(const NetworkStats &stats);
    void onTempUpdate(const TempStats &stats);
    void onFanUpdate(const FanStats &stats);
    void onProcessUpdate(const ProcessStats &stats);

private:
    void createMenu();
    QWidget* createDashboardTab();

    QTabWidget *m_tabs;

    // Process tab
    ProcessListWidget *m_processWidget;

    // Services tab
    ServicesWidget *m_servicesWidget;

    // Connections tab
    ConnectionsWidget *m_connectionsWidget;

    // Journal tab
    JournalLogWidget *m_journalWidget;

    // Tools tab
    ToolsWidget *m_toolsWidget;

    // Dashboard widgets
    TopPanelWidget *m_topPanel;
    CpuWidget *m_cpuWidget;
    MemoryWidget *m_memWidget;
    CpuHistoryWidget *m_cpuHistory;
    CpuHistoryWidget *m_gpuHistory;
    TempGraphWidget *m_tempGraph;
    DiskWidget *m_diskWidget;
    DiskIOWidget *m_diskIoWidget;
    NetworkWidget *m_networkWidget;

    // Theme
    QAction *m_darkAction;
    QAction *m_lightAction;

    // Graph duration
    QActionGroup *m_durationGroup;

    // Worker thread
    QThread *m_workerThread;
    SystemMonitorWorker *m_worker;
};
