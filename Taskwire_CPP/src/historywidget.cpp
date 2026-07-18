#include "historywidget.h"
#include "styles.h"

#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QFont>
#include <QFontMetrics>
#include <QMouseEvent>
#include <QEvent>
#include <QDateTime>
#include <cmath>

CpuHistoryWidget::CpuHistoryWidget(int historyDuration,
                                     const QString &title,
                                     const QString &accentColor,
                                     const QString &label,
                                     QWidget *parent)
    : Card(title, parent),
      m_accentColor(accentColor),
      m_label(label),
      m_maxlen(historyDuration)
{
    // Initialize data with nullopt (unfilled)
    m_dataPoints.fill(std::nullopt, m_maxlen);

    m_graphArea = new QWidget(this);
    m_graphArea->setMinimumHeight(150);
    m_graphArea->setMouseTracking(true);
    m_graphArea->installEventFilter(this);
    cardLayout()->addWidget(m_graphArea, 1);

    m_tooltip = new GameTooltip(m_graphArea);
}

void CpuHistoryWidget::setDuration(int seconds, int interval) {
    m_maxlen = seconds;
    m_updateInterval = interval;
    m_dataPoints.clear();
    m_dataPoints.fill(std::nullopt, m_maxlen);
    m_graphArea->update();
}

void CpuHistoryWidget::updateData(double percent) {
    // Throttle
    qint64 now = QDateTime::currentMSecsSinceEpoch();
    if (m_updateInterval > 0 &&
        (now - m_lastUpdateTime) < m_updateInterval * 1000LL)
        return;

    m_lastUpdateTime = now;

    // Shift left, append new value (deque-like behavior)
    if (m_dataPoints.size() >= m_maxlen)
        m_dataPoints.removeFirst();
    m_dataPoints.append(percent);

    m_graphArea->update();

    // Update tooltip if visible
    if (m_tooltip->isVisible() && m_hoverIndex >= 0 &&
        m_hoverIndex < m_dataPoints.size()) {
        int interval = qMax(1, m_updateInterval);
        int secondsAgo = (m_maxlen - 1 - m_hoverIndex) * interval;
        QString timeStr = formatTimeOffset(secondsAgo);

        auto val = m_dataPoints[m_hoverIndex];
        if (val.has_value())
            m_tooltip->updateInfo(QStringLiteral("Time: -%1\n%2: %3%")
                                      .arg(timeStr, m_label)
                                      .arg(*val, 0, 'f', 1));
        else
            m_tooltip->updateInfo(QStringLiteral("Time: -%1\n%2: NA")
                                      .arg(timeStr, m_label));
    }
}

void CpuHistoryWidget::refreshTheme() {
    Card::refreshTheme();
    m_graphArea->update();
}

bool CpuHistoryWidget::eventFilter(QObject *watched, QEvent *event) {
    if (watched == m_graphArea) {
        if (event->type() == QEvent::Paint) {
            paintGraph(static_cast<QPaintEvent *>(event));
            return true;
        }

        if (event->type() == QEvent::MouseMove) {
            auto *me = static_cast<QMouseEvent *>(event);
            if (m_dataPoints.size() < 2) return false;

            int width = m_graphArea->width();
            int x = me->pos().x();

            double stepX = (m_maxlen > 1) ? (double)width / (m_maxlen - 1) : 1.0;
            int index = qRound(x / stepX);
            index = qBound(0, index, m_dataPoints.size() - 1);

            m_hoverIndex = index;

            int interval = qMax(1, m_updateInterval);
            int secondsAgo = (m_maxlen - 1 - index) * interval;
            QString timeStr = formatTimeOffset(secondsAgo);

            auto val = m_dataPoints[index];
            if (val.has_value())
                m_tooltip->updateInfo(QStringLiteral("Time: -%1\n%2: %3%")
                                          .arg(timeStr, m_label)
                                          .arg(*val, 0, 'f', 1));
            else
                m_tooltip->updateInfo(QStringLiteral("Time: -%1\n%2: NA")
                                          .arg(timeStr, m_label));

            QPoint globalPos = m_graphArea->mapToGlobal(me->pos());
            m_tooltip->move(globalPos + QPoint(15, 15));
            m_tooltip->show();

            m_graphArea->update();
            return false; // don't consume
        }

        if (event->type() == QEvent::Leave) {
            m_hoverIndex = -1;
            m_tooltip->hide();
            m_graphArea->update();
            return false;
        }
    }
    return Card::eventFilter(watched, event);
}

void CpuHistoryWidget::paintGraph(QPaintEvent *) {
    QPainter painter(m_graphArea);
    painter.setRenderHint(QPainter::Antialiasing);

    int width = m_graphArea->width();
    int height = m_graphArea->height();
    int bottomMargin = 20;
    int graphH = height - bottomMargin;

    // ── Background grid (subtle dotted lines) ───────────────
    QPen gridPen(QColor(ModernTheme::borderColor));
    gridPen.setStyle(Qt::DotLine);
    painter.setPen(gridPen);
    for (int i = 1; i < 5; ++i) {
        int y = i * graphH / 5;
        painter.drawLine(0, y, width, y);
    }

    // ── Time axis (X-axis labels) ───────────────────────────
    int totalSeconds = (m_maxlen - 1) * qMax(1, m_updateInterval);
    int numTicks = 6;

    QPen tickPen(QColor(ModernTheme::textSecondary));
    painter.setPen(tickPen);
    QFont axisFont;
    axisFont.setPointSize(8);
    painter.setFont(axisFont);

    for (int i = 0; i < numTicks; ++i) {
        double ratio = (double)i / (numTicks - 1);
        double x = ratio * width;
        int secondsAgo = static_cast<int>(totalSeconds * (1.0 - ratio));
        QString timeStr = formatTimeOffset(secondsAgo);

        Qt::Alignment flags = Qt::AlignCenter;
        QRectF textRect(x - 25, height - bottomMargin + 2, 50, 15);

        if (i == 0) {
            flags = Qt::AlignLeft;
            textRect = QRectF(0, height - bottomMargin + 2, 50, 15);
        } else if (i == numTicks - 1) {
            flags = Qt::AlignRight;
            textRect = QRectF(width - 50, height - bottomMargin + 2, 50, 15);
        }

        painter.drawText(textRect, flags, timeStr);
    }

    // ── Graph area ──────────────────────────────────────────
    if (m_dataPoints.size() < 2) return;

    // Read accent color dynamically so it follows the current theme
    QString color = m_accentColor.isEmpty()
        ? (QColor(ModernTheme::appBackground).lightness() > 128
            ? ModernTheme::accentBlue : ModernTheme::accentCyan)
        : m_accentColor;

    QPainterPath path;
    path.moveTo(0, graphH); // bottom-left

    double stepX = (m_maxlen > 1) ? (double)width / (m_maxlen - 1) : 1.0;

    for (int i = 0; i < m_dataPoints.size(); ++i) {
        double x = i * stepX;
        double v = m_dataPoints[i].value_or(0.0);
        double y = graphH - (v / 100.0 * graphH);
        path.lineTo(x, y);
    }

    path.lineTo((m_dataPoints.size() - 1) * stepX, graphH); // bottom-right
    path.closeSubpath();

    // Fill
    QColor fillColor(color);
    fillColor.setAlpha(50);
    painter.fillPath(path, fillColor);

    // Stroke
    painter.setPen(QPen(QColor(color), 2));
    painter.drawPath(path);

    // ── Hover indicator ─────────────────────────────────────
    if (m_hoverIndex >= 0 && m_hoverIndex < m_dataPoints.size()) {
        double v = m_dataPoints[m_hoverIndex].value_or(0.0);
        double hx = m_hoverIndex * stepX;
        double hy = graphH - (v / 100.0 * graphH);

        // Vertical dashed line
        painter.setPen(QPen(QColor(ModernTheme::borderColor), 1, Qt::DashLine));
        painter.drawLine(static_cast<int>(hx), 0, static_cast<int>(hx), graphH);

        // Dot
        painter.setBrush(QColor(color));
        painter.setPen(Qt::NoPen);
        painter.drawEllipse(QPointF(hx, hy), 4, 4);
    }

    // ── Current value overlay (bottom-right) ────────────────
    auto current = m_dataPoints.last();
    QString text = current.has_value()
        ? QStringLiteral("%1%").arg(*current, 0, 'f', 1)
        : QStringLiteral("NA");

    QFont bigFont;
    bigFont.setPointSize(24);
    bigFont.setBold(true);
    painter.setFont(bigFont);
    painter.setPen(QColor(ModernTheme::textPrimary));

    QRectF textRect(width - 150, graphH - 40, 140, 40);
    painter.drawText(textRect, Qt::AlignRight | Qt::AlignBottom, text);
}
