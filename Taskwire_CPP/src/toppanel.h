#pragma once

#include "gaugewidget.h"
#include "fangraphwidget.h"
#include "systemmonitor.h"

#include <QWidget>
#include <QHBoxLayout>

class TopPanelWidget : public QWidget {
    Q_OBJECT

public:
    explicit TopPanelWidget(QWidget *parent = nullptr);

    void updateCpu(const CpuStats &stats);
    void updateGpu(const GpuStats &stats);
    void updateFans(const FanStats &stats);

    void refreshTheme();

    ModernGaugeWidget *cpuGauge() const { return m_cpuGauge; }
    ModernGaugeWidget *gpuGauge() const { return m_gpuGauge; }
    FanGraphWidget *fanWidget() const { return m_fanWidget; }

private:
    ModernGaugeWidget *m_cpuGauge;
    ModernGaugeWidget *m_gpuGauge;
    FanGraphWidget *m_fanWidget;
};
