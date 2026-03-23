#pragma once

#include "base.h"
#include "systemmonitor.h"

#include <QWidget>
#include <QLabel>
#include <QFont>
#include <QVector>
#include <QPoint>
#include <optional>

class NetworkWidget : public Card {
    Q_OBJECT

public:
    explicit NetworkWidget(QWidget *parent = nullptr);

    void setDuration(int seconds, int interval = 0);
    void updateData(const NetworkStats &stats);
    void refreshTheme() override;

protected:
    bool eventFilter(QObject *watched, QEvent *event) override;

private:
    void paintGraph(QPaintEvent *event);
    void drawLine(QPainter &painter, const QVector<std::optional<double>> &data,
                  const QString &colorHex, double maxVal,
                  int w, int topMargin, int graphH, int h);

    int m_maxlen = 90;
    int m_updateInterval = 0;
    qint64 m_lastUpdateTime = 0;

    QVector<std::optional<double>> m_upHistory;
    QVector<std::optional<double>> m_downHistory;

    QLabel *m_upLabel;
    QLabel *m_downLabel;

    QWidget *m_graphArea;
    GameTooltip *m_tooltip;
    int m_hoverIndex = -1;
    QPoint m_hoverPos;
};
