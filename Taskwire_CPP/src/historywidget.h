#pragma once

#include "base.h"
#include <QWidget>
#include <QVector>
#include <QColor>
#include <optional>

// ── CpuHistoryWidget ────────────────────────────────────────
// Generic time-series graph for 0-100% utilization data.
// Used for CPU history, GPU history, or any percentage metric.

class CpuHistoryWidget : public Card {
    Q_OBJECT

public:
    explicit CpuHistoryWidget(int historyDuration = 90,
                               const QString &title = QStringLiteral("CPU History"),
                               const QString &accentColor = {},
                               const QString &label = QStringLiteral("CPU"),
                               QWidget *parent = nullptr);

    void setDuration(int seconds, int interval = 0);
    void updateData(double percent);
    void refreshTheme() override;

protected:
    bool eventFilter(QObject *watched, QEvent *event) override;

private:
    void paintGraph(QPaintEvent *event);

    QString m_accentColor;
    QString m_label;
    int m_maxlen;
    int m_updateInterval = 0;
    qint64 m_lastUpdateTime = 0;

    // Data: std::nullopt = unfilled slot, double = value
    QVector<std::optional<double>> m_dataPoints;

    QWidget *m_graphArea;
    GameTooltip *m_tooltip;
    int m_hoverIndex = -1;
};
