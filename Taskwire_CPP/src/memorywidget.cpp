#include "memorywidget.h"
#include "styles.h"

#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QBrush>
#include <QFontMetrics>
#include <QMouseEvent>
#include <QSizePolicy>

// ── MemoryAllocationBar ─────────────────────────────────────

QColor MemoryAllocationBar::segmentColor(int index) {
    switch (index) {
    case 0: return QColor(ModernTheme::accentRed);    // App Memory
    case 1: return QColor(ModernTheme::accentPurple);  // Buffers
    case 2: return QColor(ModernTheme::accentBlue);    // Cache
    case 3: return QColor(ModernTheme::accentGreen);   // Free
    default: return QColor(ModernTheme::accentCyan);
    }
}

MemoryAllocationBar::MemoryAllocationBar(QWidget *parent)
    : QWidget(parent)
{
    setMouseTracking(true);
    m_tooltip = new GameTooltip(this);

    m_segments[0] = {"App Memory", 0};
    m_segments[1] = {"Buffers", 0};
    m_segments[2] = {"Cache", 0};
    m_segments[3] = {"Free", 0};

    m_legendFont.setPointSize(8);
    setMinimumWidth(190);
    int totalH = BAR_H + LEGEND_H;
    setMinimumHeight(totalH);
    setMaximumHeight(totalH);
}

void MemoryAllocationBar::setData(long long total, long long used,
                                   long long buffers, long long cached,
                                   long long free) {
    m_total = qMax(total, 1LL);
    m_segments[0].value = used;
    m_segments[1].value = buffers;
    m_segments[2].value = cached;
    m_segments[3].value = free;
    update();
}

QVector<double> MemoryAllocationBar::segmentWidths() const {
    double w = qMax(width(), 1);
    QVector<double> result;
    for (int i = 0; i < 4; ++i)
        result.append((m_segments[i].value / (double)m_total) * w);
    return result;
}

void MemoryAllocationBar::mouseMoveEvent(QMouseEvent *event) {
    int px = event->pos().x();
    int py = event->pos().y();
    double x = 0.0;
    int newHover = -1;
    auto ws = segmentWidths();

    // Only trigger hover on the bar itself, not the legend area below
    if (py <= BAR_H) {
        for (int i = 0; i < 4; ++i) {
            if (px >= x && px < x + ws[i]) {
                newHover = i;
                double pct = (m_segments[i].value / (double)m_total) * 100.0;
                double gib = m_segments[i].value / (1024.0 * 1024.0 * 1024.0);
                m_tooltip->updateInfo(QStringLiteral("%1: %2% (%3 GiB)")
                    .arg(m_segments[i].label)
                    .arg(pct, 0, 'f', 1)
                    .arg(gib, 0, 'f', 2));
                QPoint gp = event->globalPosition().toPoint();
                m_tooltip->move(gp + QPoint(20, 20));
                m_tooltip->show();
                break;
            }
            x += ws[i];
        }
    }

    if (newHover < 0)
        m_tooltip->hide();
    if (newHover != m_hover) {
        m_hover = newHover;
        update();
    }
    QWidget::mouseMoveEvent(event);
}

void MemoryAllocationBar::leaveEvent(QEvent *event) {
    if (m_hover >= 0) {
        m_hover = -1;
        update();
    }
    m_tooltip->hide();
    QWidget::leaveEvent(event);
}

void MemoryAllocationBar::paintEvent(QPaintEvent *) {
    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing);
    QRect r = rect();
    auto ws = segmentWidths();

    // Clip to rounded bar shape
    QPainterPath clip;
    clip.addRoundedRect(QRectF(0, 0, r.width(), BAR_H), 4, 4);
    painter.save();
    painter.setClipPath(clip);

    // Background
    painter.setPen(Qt::NoPen);
    painter.setBrush(QColor(ModernTheme::alternateTableBg));
    painter.drawRect(QRectF(0, 0, r.width(), BAR_H));

    // Segments
    double x = 0.0;
    for (int i = 0; i < 4; ++i) {
        if (ws[i] < 0.5) { x += ws[i]; continue; }

        QColor color = segmentColor(i);
        if (m_hover >= 0)
            color = (m_hover == i) ? color.lighter(120) : color.darker(200);

        painter.setPen(Qt::NoPen);
        painter.setBrush(color);
        painter.drawRect(QRectF(x, 0, ws[i], BAR_H));
        x += ws[i];
    }

    painter.restore(); // remove clip

    // 2x2 legend below the bar
    painter.setFont(m_legendFont);
    QFontMetrics fm(m_legendFont);
    int top = BAR_H + 5;

    for (int i = 0; i < 4; ++i) {
        double pct = (m_segments[i].value / (double)m_total) * 100.0;
        QString text = QStringLiteral("%1: %2%")
            .arg(m_segments[i].label)
            .arg(pct, 0, 'f', 0);

        int col = i % 2;
        int row = i / 2;

        // Left-align col 0, right-align col 1
        int lx;
        if (col == 0) {
            lx = 0;
        } else {
            int textWidth = fm.horizontalAdvance(text);
            lx = r.width() - (9 + textWidth);
        }

        int ly = top + row * (fm.height() + 2);
        QColor color = segmentColor(i);

        // Color dot
        painter.setPen(Qt::NoPen);
        painter.setBrush(color);
        double dotY = ly + (fm.height() - 6) / 2.0;
        painter.drawEllipse(QRectF(lx, dotY, 6, 6));

        // Label text
        painter.setPen(QColor(ModernTheme::textPrimary));
        painter.drawText(lx + 9, ly + fm.ascent(), text);
    }
}

// ── MemoryWidget ────────────────────────────────────────────

MemoryWidget::MemoryWidget(QWidget *parent)
    : Card("Memory Usage", parent)
{
    setSizePolicy(QSizePolicy::Maximum, QSizePolicy::Preferred);

    m_usedLabelTop = new QLabel("Used Physical Memory");
    m_usedLabelTop->setAlignment(Qt::AlignCenter);
    m_usedLabelTop->setStyleSheet(
        QStringLiteral("color: %1; font-size: 11px;").arg(ModernTheme::textPrimary));
    cardLayout()->addWidget(m_usedLabelTop);

    m_gauge = new CircularGauge();
    cardLayout()->addWidget(m_gauge, 0, Qt::AlignHCenter);

    m_totalLabelBottom = new QLabel("");
    m_totalLabelBottom->setAlignment(Qt::AlignCenter);
    m_totalLabelBottom->setStyleSheet(
        QStringLiteral("color: %1; font-size: 11px;").arg(ModernTheme::textPrimary));
    cardLayout()->addWidget(m_totalLabelBottom);

    m_allocLabel = new QLabel("Memory Allocation");
    m_allocLabel->setAlignment(Qt::AlignCenter);
    m_allocLabel->setStyleSheet(
        QStringLiteral("color: %1; font-size: 10px; margin-top: 6px;").arg(ModernTheme::textSecondary));
    cardLayout()->addWidget(m_allocLabel);

    m_allocBar = new MemoryAllocationBar();
    cardLayout()->addWidget(m_allocBar);
}

void MemoryWidget::refreshTheme() {
    Card::refreshTheme();
    m_usedLabelTop->setStyleSheet(
        QStringLiteral("color: %1; font-size: 11px;").arg(ModernTheme::textPrimary));
    m_totalLabelBottom->setStyleSheet(
        QStringLiteral("color: %1; font-size: 11px;").arg(ModernTheme::textPrimary));
    m_allocLabel->setStyleSheet(
        QStringLiteral("color: %1; font-size: 10px; margin-top: 6px;").arg(ModernTheme::textSecondary));
    m_gauge->update();
    m_allocBar->update();
}

void MemoryWidget::updateData(const MemoryStats &stats) {
    if (!stats.valid) return;

    double usedGb = stats.usedBytes / (1024.0 * 1024.0 * 1024.0);
    double totalGb = stats.totalBytes / (1024.0 * 1024.0 * 1024.0);
    m_gauge->setData(stats.percent, usedGb, totalGb);

    m_usedLabelTop->setText("Used Physical Memory");
    m_totalLabelBottom->setText(
        QStringLiteral("%1 GiB Total Physical Memory").arg(totalGb, 0, 'f', 1));

    // Allocation bar: segments must sum to total, so use
    // appUsed = total - free - buffers - cached (matches psutil.used)
    // NOT usedBytes which is total - available (larger, doesn't sum correctly)
    long long appUsed = stats.totalBytes - stats.freeBytes
                        - stats.buffersBytes - stats.cachedBytes;
    if (appUsed < 0) appUsed = 0;
    m_allocBar->setData(stats.totalBytes, appUsed,
                         stats.buffersBytes, stats.cachedBytes,
                         stats.freeBytes);
}
