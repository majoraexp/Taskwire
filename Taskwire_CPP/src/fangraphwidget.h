#pragma once

#include "base.h"
#include "systemmonitor.h"

#include <QWidget>
#include <QLabel>
#include <QCheckBox>
#include <QScrollArea>
#include <QGridLayout>
#include <QVBoxLayout>
#include <QVector>
#include <QHash>
#include <QColor>
#include <QPoint>
#include <optional>

class FanGraphWidget : public Card {
    Q_OBJECT

public:
    explicit FanGraphWidget(QWidget *parent = nullptr);

    void setDuration(int seconds, int interval = 0);
    void updateData(const FanStats &stats);
    void refreshTheme() override;

protected:
    bool eventFilter(QObject *watched, QEvent *event) override;

private:
    void paintGraph(QPaintEvent *event);

    int m_maxlen = 90;
    int m_updateInterval = 0;
    qint64 m_lastUpdateTime = 0;

    // Insertion-ordered sensor data
    QVector<QString> m_sensorOrder;
    QHash<QString, QVector<std::optional<double>>> m_history;
    QHash<QString, bool> m_sensorVisible;

    QVector<QColor> m_colors;

    QWidget *m_graphArea;
    QLabel *m_noDataLabel;
    QScrollArea *m_legendScroll;
    QWidget *m_legendContainer;
    QGridLayout *m_legendLayout;
    QHash<QString, QCheckBox *> m_legendCheckBoxes;
    QHash<QString, QLabel *> m_legendLabels;

    GameTooltip *m_tooltip;
    int m_hoverIndex = -1;
    QPoint m_hoverPos;
};
