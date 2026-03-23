#include "toppanel.h"
#include "styles.h"

TopPanelWidget::TopPanelWidget(QWidget *parent)
    : QWidget(parent)
{
    auto *layout = new QHBoxLayout(this);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(15);

    // CPU gauge (fixed width)
    m_cpuGauge = new ModernGaugeWidget("CPU");
    m_cpuGauge->setFixedWidth(200);
    layout->addWidget(m_cpuGauge, 0);

    // GPU gauge (fixed width)
    m_gpuGauge = new ModernGaugeWidget("GPU");
    m_gpuGauge->setFixedWidth(200);
    layout->addWidget(m_gpuGauge, 0);

    // Fan graph (stretches to fill)
    m_fanWidget = new FanGraphWidget();
    layout->addWidget(m_fanWidget, 1);
}

void TopPanelWidget::updateCpu(const CpuStats &stats) {
    if (!stats.valid) return;
    m_cpuGauge->setSimplePercent(stats.overallPercent);
}

void TopPanelWidget::updateGpu(const GpuStats &stats) {
    if (!stats.valid) return;
    m_gpuGauge->setSimplePercent(stats.usagePercent);
}

void TopPanelWidget::updateFans(const FanStats &stats) {
    m_fanWidget->updateData(stats);
}

void TopPanelWidget::setFanDuration(int seconds, int interval) {
    m_fanWidget->setDuration(seconds, interval);
}

void TopPanelWidget::refreshTheme() {
    m_cpuGauge->refreshTheme();
    m_gpuGauge->refreshTheme();
    m_fanWidget->refreshTheme();
}
