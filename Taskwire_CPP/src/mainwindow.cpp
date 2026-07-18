#include "mainwindow.h"
#include "styles.h"

#include <QTabWidget>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QMenuBar>
#include <QThread>
#include <QApplication>
#include <QScrollArea>
#include <QActionGroup>
#include <QSettings>
#include <QScreen>
#include <QTimer>

// ── Constructor / Destructor ────────────────────────────────

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent)
{
    setWindowTitle("Taskwire");
    setMinimumSize(800, 500);

    createMenu();

    auto *central = new QWidget(this);
    setCentralWidget(central);
    auto *mainLayout = new QVBoxLayout(central);
    mainLayout->setContentsMargins(10, 10, 10, 10);

    m_tabs = new QTabWidget(this);
    mainLayout->addWidget(m_tabs);

    // Dashboard tab (scrollable when window is small)
    auto *dashScroll = new QScrollArea(this);
    dashScroll->setWidgetResizable(true);
    dashScroll->setFrameShape(QFrame::NoFrame);
    dashScroll->setWidget(createDashboardTab());
    m_tabs->addTab(dashScroll, "Dashboard");

    // Processes tab
    m_processWidget = new ProcessListWidget(this);
    m_tabs->addTab(m_processWidget, "Processes");

    // Services tab
    m_servicesWidget = new ServicesWidget(this);
    m_tabs->addTab(m_servicesWidget, "Services");

    // Connections tab
    m_connectionsWidget = new ConnectionsWidget(this);
    m_tabs->addTab(m_connectionsWidget, "Connections");

    // Logs tab
    m_journalWidget = new JournalLogWidget(this);
    m_tabs->addTab(m_journalWidget, "Logs");

    // Tools tab
    m_toolsWidget = new ToolsWidget(this);
    m_tabs->addTab(m_toolsWidget, "Tools");

    // Default size: whatever the dashboard needs to show without its outer
    // scrollbar, clamped to the screen's available area. QMainWindow's own
    // sizeHint() caches early and never tracks the scroll area content, so
    // measure the dashboard widget directly. Shrinking the window below
    // this still scrolls as before.
    const QRect avail = QGuiApplication::primaryScreen()->availableGeometry();
    const QSize maxSize(avail.width() - 20, avail.height() - 60);
    const auto margins = mainLayout->contentsMargins();
    const int chromeH = menuBar()->sizeHint().height()
                        + m_tabs->tabBar()->sizeHint().height()
                        + margins.top() + margins.bottom();
    const QSize dashHint = dashScroll->widget()->sizeHint();
    resize(QSize(qMax(1125, dashHint.width() + margins.left() + margins.right() + 4),
                 dashHint.height() + chromeH + 4)
               .boundedTo(maxSize));
    m_autoSize = size();

    // The dashboard hint grows once the first sensor data populates the
    // temp/fan legends and disk icons, so re-measure shortly after startup
    // and correct the size — unless the user already resized the window.
    QTimer::singleShot(1500, this, [this, dashScroll, maxSize]() {
        // Row hints have grown (legends, disk icons) — rebalance the
        // proportional stretch factors even if we skip the resize below.
        updateDashboardStretch();
        if (size() != m_autoSize || !dashScroll->isVisible())
            return;
        const QSize hint = dashScroll->widget()->sizeHint();
        const int extraW = width() - dashScroll->viewport()->width();
        const int extraH = height() - dashScroll->viewport()->height();
        resize(QSize(qMax(1125, hint.width() + extraW),
                     hint.height() + extraH + 2)
                   .boundedTo(maxSize));
    });

    // ── Start worker thread ─────────────────────────────────
    m_workerThread = new QThread(this);
    m_worker = new SystemMonitorWorker();
    m_worker->moveToThread(m_workerThread);

    connect(m_worker, &SystemMonitorWorker::cpuUpdate,     this, &MainWindow::onCpuUpdate);
    connect(m_worker, &SystemMonitorWorker::memoryUpdate,  this, &MainWindow::onMemoryUpdate);
    connect(m_worker, &SystemMonitorWorker::gpuUpdate,     this, &MainWindow::onGpuUpdate);
    connect(m_worker, &SystemMonitorWorker::diskUpdate,    this, &MainWindow::onDiskUpdate);
    connect(m_worker, &SystemMonitorWorker::diskIoUpdate,  this, &MainWindow::onDiskIoUpdate);
    connect(m_worker, &SystemMonitorWorker::networkUpdate,  this, &MainWindow::onNetworkUpdate);
    connect(m_worker, &SystemMonitorWorker::tempUpdate,    this, &MainWindow::onTempUpdate);
    connect(m_worker, &SystemMonitorWorker::fanUpdate,     this, &MainWindow::onFanUpdate);
    connect(m_worker, &SystemMonitorWorker::processUpdate, this, &MainWindow::onProcessUpdate);

    connect(m_workerThread, &QThread::started, m_worker, &SystemMonitorWorker::startPolling);
    connect(m_workerThread, &QThread::finished, m_worker, &QObject::deleteLater);

    m_workerThread->start();
}

MainWindow::~MainWindow() {
    m_journalWidget->stop();
    QMetaObject::invokeMethod(m_worker, "stopPolling", Qt::BlockingQueuedConnection);
    m_workerThread->quit();
    m_workerThread->wait();
}

// ── Menu ────────────────────────────────────────────────────

void MainWindow::createMenu() {
    auto *settingsMenu = menuBar()->addMenu("Settings");

    // Graph Duration submenu with radio-style selection
    auto *durationMenu = settingsMenu->addMenu("Graph Duration");
    m_durationGroup = new QActionGroup(this);

    auto *dur60 = durationMenu->addAction("60 Seconds");
    dur60->setCheckable(true);
    dur60->setData(60);
    m_durationGroup->addAction(dur60);

    auto *dur90 = durationMenu->addAction("90 Seconds");
    dur90->setCheckable(true);
    dur90->setChecked(true);  // Default
    dur90->setData(90);
    m_durationGroup->addAction(dur90);

    auto *dur30m = durationMenu->addAction("30 Minutes");
    dur30m->setCheckable(true);
    dur30m->setData(1800);
    m_durationGroup->addAction(dur30m);

    connect(m_durationGroup, &QActionGroup::triggered,
            this, &MainWindow::onDurationChanged);

    settingsMenu->addSeparator();

    // Theme submenu
    auto *themeMenu = settingsMenu->addMenu("Theme");
    QString savedTheme = QSettings().value(QStringLiteral("theme"), QStringLiteral("dark")).toString();

    m_darkAction = themeMenu->addAction("Dark Mode");
    m_darkAction->setCheckable(true);
    m_darkAction->setChecked(savedTheme == "dark");
    connect(m_darkAction, &QAction::triggered, this, [this]() { switchTheme("dark"); });

    m_lightAction = themeMenu->addAction("Light Mode");
    m_lightAction->setCheckable(true);
    m_lightAction->setChecked(savedTheme == "light");
    connect(m_lightAction, &QAction::triggered, this, [this]() { switchTheme("light"); });
}

void MainWindow::switchTheme(const QString &mode) {
    m_darkAction->setChecked(mode == "dark");
    m_lightAction->setChecked(mode == "light");
    ModernTheme::setTheme(mode);
    qApp->setStyleSheet(ModernTheme::getStylesheet());

    QSettings settings;
    settings.setValue(QStringLiteral("theme"), mode);

    m_topPanel->refreshTheme();
    m_cpuWidget->refreshTheme();
    m_memWidget->refreshTheme();
    m_cpuHistory->refreshTheme();
    m_gpuHistory->refreshTheme();
    m_tempGraph->refreshTheme();
    m_diskWidget->refreshTheme();
    m_diskIoWidget->refreshTheme();
    m_networkWidget->refreshTheme();
    m_processWidget->refreshTheme();
    m_servicesWidget->refreshTheme();
    m_connectionsWidget->refreshTheme();
    m_journalWidget->refreshTheme();
    m_toolsWidget->refreshTheme();

    update();
}

// ── Dashboard tab ───────────────────────────────────────────

QWidget* MainWindow::createDashboardTab() {
    auto *tab = new QWidget();
    auto *layout = new QVBoxLayout(tab);
    layout->setSpacing(10);
    m_dashLayout = layout;

    // ── Row 1: Top Panel (CPU gauge | GPU gauge | Fan graph) ─
    m_topPanel = new TopPanelWidget();
    m_topPanel->fanWidget()->setDuration(91, 1);
    layout->addWidget(m_topPanel);

    // ── Row 2: CPU History | GPU History ────────────────────
    auto *row2 = new QHBoxLayout();
    row2->setSpacing(10);
    m_cpuHistory = new CpuHistoryWidget(91, "CPU History",
                                         {}, "CPU");
    m_cpuHistory->setDuration(91, 1);
    row2->addWidget(m_cpuHistory, 1);

    m_gpuHistory = new CpuHistoryWidget(91, "GPU History",
                                         {}, "GPU");
    m_gpuHistory->setDuration(91, 1);
    row2->addWidget(m_gpuHistory, 1);

    layout->addLayout(row2);

    // ── Row 3: Memory | Temperatures | Disk IO ──────────────
    auto *row3 = new QHBoxLayout();
    row3->setSpacing(10);

    m_memWidget = new MemoryWidget();
    row3->addWidget(m_memWidget, 0);

    m_tempGraph = new TempGraphWidget();
    m_tempGraph->setDuration(91, 1);
    row3->addWidget(m_tempGraph, 1);

    m_diskIoWidget = new DiskIOWidget();
    m_diskIoWidget->setDuration(91, 1);
    row3->addWidget(m_diskIoWidget, 1);

    layout->addLayout(row3);

    // ── Row 4: Network | Disk Usage ─────────────────────────
    auto *row4 = new QHBoxLayout();
    row4->setSpacing(10);

    m_networkWidget = new NetworkWidget();
    m_networkWidget->setDuration(91, 1);
    row4->addWidget(m_networkWidget, 1);

    m_diskWidget = new DiskWidget();
    row4->addWidget(m_diskWidget, 1);

    layout->addLayout(row4);

    // ── Row 5: CPU Cores (Per Thread) ───────────────────────
    m_cpuWidget = new CpuWidget();
    layout->addWidget(m_cpuWidget);

    updateDashboardStretch();
    return tab;
}

// Stretch factors proportional to each row's natural height: surplus
// vertical space scales every row by the same factor, so the dashboard
// keeps its landscape proportions on any display shape (e.g. a maximized
// window on a portrait monitor).
void MainWindow::updateDashboardStretch() {
    for (int i = 0; i < m_dashLayout->count(); ++i)
        m_dashLayout->setStretch(i, qMax(1, m_dashLayout->itemAt(i)->sizeHint().height()));
}

// ── Data update slots ───────────────────────────────────────

void MainWindow::onCpuUpdate(const CpuStats &stats) {
    if (!stats.valid) return;
    m_topPanel->updateCpu(stats);
    m_cpuWidget->updateData(stats);
    m_cpuHistory->updateData(stats.overallPercent);
}

void MainWindow::onMemoryUpdate(const MemoryStats &stats) {
    if (!stats.valid) return;
    m_memWidget->updateData(stats);
}

void MainWindow::onGpuUpdate(const GpuStats &stats) {
    if (!stats.valid) return;
    m_topPanel->updateGpu(stats);
    m_gpuHistory->updateData(stats.usagePercent);
}

void MainWindow::onDiskUpdate(const DiskUsageStats &stats) {
    if (!stats.valid) return;
    m_diskWidget->updateData(stats);
}

void MainWindow::onDiskIoUpdate(const DiskIoStats &stats) {
    if (!stats.valid) return;
    m_diskIoWidget->updateData(stats);
}

void MainWindow::onNetworkUpdate(const NetworkStats &stats) {
    if (!stats.valid) return;
    m_networkWidget->updateData(stats);
}

void MainWindow::onTempUpdate(const TempStats &stats) {
    if (!stats.valid) return;
    m_tempGraph->updateData(stats);
}

void MainWindow::onFanUpdate(const FanStats &stats) {
    m_topPanel->updateFans(stats);
}

void MainWindow::onProcessUpdate(const ProcessStats &stats) {
    if (!stats.valid) return;
    m_processWidget->updateData(stats);
}

// ── Graph Duration ─────────────────────────────────────────

void MainWindow::onDurationChanged(QAction *action) {
    int totalSeconds = action->data().toInt();
    int interval = (totalSeconds >= 1800) ? 10 : 1;
    int maxlen = totalSeconds / interval + 1;

    // Apply to all graph widgets
    m_cpuHistory->setDuration(maxlen, interval);
    m_gpuHistory->setDuration(maxlen, interval);
    m_tempGraph->setDuration(maxlen, interval);
    m_diskIoWidget->setDuration(maxlen, interval);
    m_networkWidget->setDuration(maxlen, interval);
    m_topPanel->fanWidget()->setDuration(maxlen, interval);
}
