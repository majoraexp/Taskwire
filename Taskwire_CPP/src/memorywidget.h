#pragma once

#include "base.h"
#include "circulargauge.h"
#include "systemmonitor.h"

#include <QWidget>
#include <QLabel>
#include <QFont>
#include <QVector>

// ── MemoryAllocationBar ─────────────────────────────────────
// Segmented horizontal bar: App Memory / Buffers / Cache / Free

class MemoryAllocationBar : public QWidget {
    Q_OBJECT

public:
    explicit MemoryAllocationBar(QWidget *parent = nullptr);

    void setData(long long total, long long used, long long buffers,
                 long long cached, long long free);
    void setUiScale(double scale);
    int naturalHeight() const { return BAR_H + LEGEND_H; }

protected:
    void paintEvent(QPaintEvent *event) override;
    void mouseMoveEvent(QMouseEvent *event) override;
    void leaveEvent(QEvent *event) override;

private:
    static constexpr int BAR_H = 16;
    static constexpr int LEGEND_H = 38;

    int barH() const { return qRound(BAR_H * m_scale); }

    static QColor segmentColor(int index);

    struct Segment {
        QString label;
        long long value = 0;
    };

    QVector<double> segmentWidths() const;

    Segment m_segments[4];
    long long m_total = 1;
    int m_hover = -1;
    double m_scale = 1.0;
    GameTooltip *m_tooltip;
    QFont m_legendFont;
};

// ── MemoryWidget ────────────────────────────────────────────

class MemoryWidget : public Card {
    Q_OBJECT

public:
    explicit MemoryWidget(QWidget *parent = nullptr);

    void updateData(const MemoryStats &stats);
    void refreshTheme() override;

protected:
    void resizeEvent(QResizeEvent *event) override;

private:
    void applyLabelStyles();

    int m_gaugeSide = 160;
    int m_naturalHint = 0;
    double m_uiScale = 1.0;
    QLabel *m_usedLabelTop;
    CircularGauge *m_gauge;
    QLabel *m_totalLabelBottom;
    QLabel *m_allocLabel;
    MemoryAllocationBar *m_allocBar;
};
