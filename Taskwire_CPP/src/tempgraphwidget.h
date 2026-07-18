#pragma once

#include "base.h"
#include "systemmonitor.h"

#include <QWidget>
#include <QGridLayout>
#include <QLabel>
#include <QCheckBox>
#include <QScrollArea>
#include <QVector>
#include <QHash>
#include <QColor>
#include <optional>

class TempGraphWidget : public Card {
    Q_OBJECT

public:
    explicit TempGraphWidget(QWidget *parent = nullptr);

    void setDuration(int seconds, int interval = 0);
    void updateData(const TempStats &stats);
    void refreshTheme() override;

protected:
    bool eventFilter(QObject *watched, QEvent *event) override;

private:
    void paintGraph(QPaintEvent *event);
    QColor sensorColor(int index) const;

    int m_maxlen = 90;
    int m_updateInterval = 0;
    qint64 m_lastUpdateTime = 0;

    // Insertion-ordered sensor data
    QVector<QString> m_sensorOrder;
    QHash<QString, QVector<std::optional<double>>> m_history;

    // Theme colors (refreshed on theme change)
    QVector<QColor> m_colors;

    // Visibility
    QHash<QString, bool> m_sensorVisible;

    QWidget *m_graphArea;
    QScrollArea *m_legendScroll;
    QWidget *m_legendContainer;
    QGridLayout *m_legendLayout;
    QHash<QString, QCheckBox *> m_legendCheckBoxes;
    QHash<QString, QLabel *> m_legendLabels;

    GameTooltip *m_tooltip;
    int m_hoverIndex = -1;
};
