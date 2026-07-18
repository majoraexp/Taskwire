#include "networkwidget.h"
#include "graphutils.h"
#include "styles.h"

#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QBrush>
#include <QFont>
#include <QHBoxLayout>
#include <QMouseEvent>
#include <QEvent>
#include <QDateTime>
#include <algorithm>

NetworkWidget::NetworkWidget(QWidget *parent)
    : Card("Network Speed", parent)
{
    m_upHistory.fill(std::nullopt, m_maxlen);
    m_downHistory.fill(std::nullopt, m_maxlen);

    // Labels
    auto *labelsLayout = new QHBoxLayout();
    labelsLayout->setAlignment(Qt::AlignLeft);
    labelsLayout->setSpacing(20);

    m_upLabel = new QLabel("Upload: 0 KB/s");
    m_downLabel = new QLabel("Download: 0 KB/s");
    m_upLabel->setFixedWidth(160);
    m_downLabel->setFixedWidth(160);

    QFont labelFont;
    labelFont.setPointSize(12);
    labelFont.setBold(true);
    m_upLabel->setFont(labelFont);
    m_downLabel->setFont(labelFont);

    m_upLabel->setStyleSheet(QStringLiteral("color: %1;").arg(ModernTheme::accentGreen));
    m_downLabel->setStyleSheet(QStringLiteral("color: %1;").arg(ModernTheme::accentRed));

    labelsLayout->addWidget(m_upLabel);
    labelsLayout->addWidget(m_downLabel);
    cardLayout()->addLayout(labelsLayout);

    // Graph area
    m_graphArea = new QWidget(this);
    m_graphArea->setMinimumHeight(75);
    m_graphArea->setMouseTracking(true);
    m_graphArea->installEventFilter(this);
    cardLayout()->addWidget(m_graphArea, 1);

    m_tooltip = new GameTooltip(m_graphArea);
}

void NetworkWidget::refreshTheme() {
    Card::refreshTheme();
    m_upLabel->setStyleSheet(QStringLiteral("color: %1;").arg(ModernTheme::accentGreen));
    m_downLabel->setStyleSheet(QStringLiteral("color: %1;").arg(ModernTheme::accentRed));
    m_graphArea->update();
}

void NetworkWidget::setDuration(int seconds, int interval) {
    m_maxlen = seconds;
    m_updateInterval = interval;
    m_upHistory.clear();
    m_upHistory.fill(std::nullopt, m_maxlen);
    m_downHistory.clear();
    m_downHistory.fill(std::nullopt, m_maxlen);
    m_graphArea->update();
}

void NetworkWidget::updateData(const NetworkStats &stats) {
    if (!stats.valid) return;

    double upSpeed = stats.uploadBytesPerSec;
    double downSpeed = stats.downloadBytesPerSec;

    m_upLabel->setText(QStringLiteral("Upload: %1").arg(GraphUtils::formatSpeed(upSpeed)));
    m_downLabel->setText(QStringLiteral("Download: %1").arg(GraphUtils::formatSpeed(downSpeed)));

    // Throttle
    qint64 now = QDateTime::currentMSecsSinceEpoch();
    if (m_updateInterval > 0 &&
        (now - m_lastUpdateTime) < m_updateInterval * 1000LL)
        return;
    m_lastUpdateTime = now;

    if (m_upHistory.size() >= m_maxlen) m_upHistory.removeFirst();
    m_upHistory.append(upSpeed);
    if (m_downHistory.size() >= m_maxlen) m_downHistory.removeFirst();
    m_downHistory.append(downSpeed);

    m_graphArea->update();

    // Update tooltip if visible
    if (m_tooltip->isVisible() && m_hoverIndex >= 0) {
        int screenIdx = m_hoverIndex;
        int offset = (m_maxlen - 1) - screenIdx;
        int dataIdx = (m_upHistory.size() - 1) - offset;

        int interval = qMax(1, m_updateInterval);
        int secondsAgo = (m_maxlen - 1 - m_hoverIndex) * interval;
        QString timeStr = formatTimeOffset(secondsAgo);

        if (dataIdx >= 0 && dataIdx < m_upHistory.size()) {
            auto uVal = m_upHistory[dataIdx];
            auto dVal = m_downHistory[dataIdx];
            QString uStr = uVal.has_value() ? GraphUtils::formatSpeed(*uVal) : "NA";
            QString dStr = dVal.has_value() ? GraphUtils::formatSpeed(*dVal) : "NA";
            m_tooltip->updateInfo(QStringLiteral("Time: -%1\nUp: %2\nDown: %3")
                .arg(timeStr, uStr, dStr));
        } else {
            m_tooltip->updateInfo(QStringLiteral("Time: -%1\nUp: NA\nDown: NA").arg(timeStr));
        }
    }
}

bool NetworkWidget::eventFilter(QObject *watched, QEvent *event) {
    if (watched == m_graphArea) {
        if (event->type() == QEvent::Paint) {
            paintGraph(static_cast<QPaintEvent *>(event));
            return true;
        }

        if (event->type() == QEvent::MouseMove) {
            auto *me = static_cast<QMouseEvent *>(event);
            if (m_upHistory.isEmpty()) return false;

            int w = m_graphArea->width();
            int index = GraphUtils::hoverIndexFromX(me->pos().x(), w, m_maxlen);

            m_hoverIndex = index;

            int screenIdx = m_hoverIndex;
            int offset = (m_maxlen - 1) - screenIdx;
            int dataIdx = (m_upHistory.size() - 1) - offset;

            int interval = qMax(1, m_updateInterval);
            int secondsAgo = (m_maxlen - 1 - index) * interval;
            QString timeStr = formatTimeOffset(secondsAgo);

            if (dataIdx >= 0 && dataIdx < m_upHistory.size()) {
                auto uVal = m_upHistory[dataIdx];
                auto dVal = m_downHistory[dataIdx];
                QString uStr = uVal.has_value() ? GraphUtils::formatSpeed(*uVal) : "NA";
                QString dStr = dVal.has_value() ? GraphUtils::formatSpeed(*dVal) : "NA";
                m_tooltip->updateInfo(QStringLiteral("Time: -%1\nUp: %2\nDown: %3")
                    .arg(timeStr, uStr, dStr));
            } else {
                m_tooltip->updateInfo(QStringLiteral("Time: -%1\nUp: NA\nDown: NA").arg(timeStr));
            }

            QPoint globalPos = m_graphArea->mapToGlobal(me->pos());
            m_tooltip->move(globalPos + QPoint(15, 15));
            m_tooltip->show();
            m_graphArea->update();
            return false;
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

void NetworkWidget::drawLine(QPainter &painter,
                              const QVector<std::optional<double>> &data,
                              const QString &colorHex, double maxVal,
                              int w, int topMargin, int graphH, int h) {
    if (data.size() < 2) return;

    QPainterPath path;
    double stepX = (m_maxlen > 1) ? (double)w / (m_maxlen - 1) : 1.0;
    int numPoints = data.size();
    double startX = w - (numPoints - 1) * stepX;

    double startVal = data[0].value_or(0.0);
    double startY = topMargin + graphH - ((startVal / maxVal) * graphH);
    path.moveTo(startX, startY);

    for (int i = 0; i < numPoints; ++i) {
        double drawVal = data[i].value_or(0.0);
        double x = startX + i * stepX;
        double y = topMargin + graphH - ((drawVal / maxVal) * graphH);
        path.lineTo(x, y);
    }

    painter.setPen(QPen(QColor(colorHex), 2));
    painter.setBrush(Qt::NoBrush);
    painter.drawPath(path);
}

void NetworkWidget::paintGraph(QPaintEvent *) {
    QPainter painter(m_graphArea);
    painter.setRenderHint(QPainter::Antialiasing);

    int w = m_graphArea->width();
    int h = m_graphArea->height();
    int bottomMargin = 20;
    int topMargin = 10;
    int graphH = h - bottomMargin - topMargin;

    // Dynamic Y scale
    double maxU = 0.0, maxD = 0.0;
    for (const auto &v : m_upHistory) if (v.has_value()) maxU = qMax(maxU, *v);
    for (const auto &v : m_downHistory) if (v.has_value()) maxD = qMax(maxD, *v);
    double maxVal = qMax(maxU, maxD);
    if (maxVal == 0.0) maxVal = 1024.0 * 10.0; // 10 KB/s min
    maxVal *= 1.2;

    // Grid (3 lines)
    QPen gridPen(QColor(ModernTheme::borderColor));
    gridPen.setStyle(Qt::DotLine);

    QFont gridFont;
    gridFont.setPointSize(8);
    painter.setFont(gridFont);

    for (int i = 1; i < 4; ++i) {
        int y = topMargin + graphH - (i * graphH / 4);
        painter.setPen(gridPen);
        painter.drawLine(0, y, w, y);
        double valAtLine = maxVal * i / 4.0;
        painter.setPen(QColor(ModernTheme::textSecondary));
        painter.drawText(2, y - 2, GraphUtils::formatSpeed(valAtLine));
    }

    // Time axis
    GraphUtils::drawTimeAxis(painter, w, h, bottomMargin, m_maxlen, m_updateInterval);

    // Upload (green) then Download (red)
    drawLine(painter, m_upHistory, ModernTheme::accentGreen, maxVal, w, topMargin, graphH, h);
    drawLine(painter, m_downHistory, ModernTheme::accentRed, maxVal, w, topMargin, graphH, h);

    // Draw hover line once, then dots on top
    if (m_hoverIndex >= 0) {
        double stepX = (m_maxlen > 1) ? (double)w / (m_maxlen - 1) : 1.0;
        double hx = m_hoverIndex * stepX;
        GraphUtils::drawHoverLine(painter, hx, 0, h - bottomMargin);

        int screenIdx = m_hoverIndex;
        int offset = (m_maxlen - 1) - screenIdx;
        int numUp = m_upHistory.size();
        int numDown = m_downHistory.size();
        int dataIdxUp = (numUp - 1) - offset;
        int dataIdxDown = (numDown - 1) - offset;

        if (dataIdxUp >= 0 && dataIdxUp < numUp) {
            double drawVal = m_upHistory[dataIdxUp].value_or(0.0);
            double hy = topMargin + graphH - ((drawVal / maxVal) * graphH);
            GraphUtils::drawHoverDot(painter, hx, hy, QColor(ModernTheme::accentGreen));
        }
        if (dataIdxDown >= 0 && dataIdxDown < numDown) {
            double drawVal = m_downHistory[dataIdxDown].value_or(0.0);
            double hy = topMargin + graphH - ((drawVal / maxVal) * graphH);
            GraphUtils::drawHoverDot(painter, hx, hy, QColor(ModernTheme::accentRed));
        }
    }
}
