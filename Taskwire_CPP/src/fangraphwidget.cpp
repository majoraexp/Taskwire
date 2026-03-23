#include "fangraphwidget.h"
#include "graphutils.h"
#include "styles.h"

#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QBrush>
#include <QFont>
#include <QMouseEvent>
#include <QEvent>
#include <QDateTime>
#include <QSettings>
#include <algorithm>

FanGraphWidget::FanGraphWidget(QWidget *parent)
    : Card("Fan Speeds", parent)
{
    m_colors = {
        QColor(ModernTheme::accentRed),
        QColor(ModernTheme::accentCyan),
        QColor(ModernTheme::accentOrange),
        QColor(ModernTheme::accentPurple)
    };

    m_graphArea = new QWidget(this);
    m_graphArea->setMinimumHeight(100);
    m_graphArea->setMouseTracking(true);
    m_graphArea->installEventFilter(this);
    cardLayout()->addWidget(m_graphArea);

    // "No Fans Detected" overlay
    m_noDataLabel = new QLabel("No Fans Detected");
    m_noDataLabel->setAlignment(Qt::AlignCenter);
    m_noDataLabel->setStyleSheet(
        QStringLiteral("color: %1; font-style: italic;").arg(ModernTheme::textSecondary));
    m_noDataLabel->hide();

    auto *overlay = new QVBoxLayout(m_graphArea);
    overlay->addWidget(m_noDataLabel);
    overlay->setAlignment(Qt::AlignCenter);

    // Spacer pushes legend to bottom of card
    cardLayout()->addStretch(1);

    // Legend
    m_legendContainer = new QWidget();
    m_legendLayout = new QGridLayout(m_legendContainer);
    m_legendLayout->setContentsMargins(0, 0, 0, 0);
    m_legendLayout->setVerticalSpacing(0);
    m_legendLayout->setHorizontalSpacing(4);
    // Spacer column (col 4) absorbs extra width so legend items stay left-aligned
    m_legendLayout->setColumnStretch(4, 1);

    m_legendScroll = new QScrollArea();
    m_legendScroll->setWidget(m_legendContainer);
    m_legendScroll->setWidgetResizable(true);
    m_legendScroll->setFixedHeight(30);
    m_legendScroll->setFrameShape(QFrame::NoFrame);
    m_legendScroll->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    m_legendScroll->setVerticalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    m_legendScroll->setStyleSheet(QStringLiteral("background: transparent;"));
    cardLayout()->addWidget(m_legendScroll);

    m_tooltip = new GameTooltip(m_graphArea);
}

void FanGraphWidget::refreshTheme() {
    Card::refreshTheme();
    m_colors = {
        QColor(ModernTheme::accentRed),
        QColor(ModernTheme::accentCyan),
        QColor(ModernTheme::accentOrange),
        QColor(ModernTheme::accentPurple)
    };

    while (m_legendLayout->count()) {
        QLayoutItem *item = m_legendLayout->takeAt(0);
        if (item->widget())
            item->widget()->deleteLater();
        delete item;
    }
    m_legendCheckBoxes.clear();
    m_legendLabels.clear();
    m_graphArea->update();
}

void FanGraphWidget::setDuration(int seconds, int interval) {
    m_maxlen = seconds;
    m_updateInterval = interval;
    m_history.clear();
    m_sensorOrder.clear();
    m_graphArea->update();
}

void FanGraphWidget::updateData(const FanStats &stats) {
    if (!stats.valid || stats.fans.isEmpty()) {
        m_noDataLabel->show();
        return;
    }
    m_noDataLabel->hide();

    // Update legend
    for (int i = 0; i < stats.fans.size(); ++i) {
        const FanReading &f = stats.fans[i];

        // Track insertion order
        if (!m_sensorOrder.contains(f.label))
            m_sensorOrder.append(f.label);

        // Default visibility: load from settings, default to hide if RPM is 0
        if (!m_sensorVisible.contains(f.label)) {
            QSettings settings;
            QString key = QStringLiteral("FanSensorVisible/%1").arg(f.label);
            if (settings.contains(key))
                m_sensorVisible[f.label] = settings.value(key).toBool();
            else
                m_sensorVisible[f.label] = (f.rpm > 0);
        } else if (f.rpm > 0 && !m_sensorVisible[f.label]) {
            m_sensorVisible[f.label] = true; // auto-show on first nonzero
            if (m_legendCheckBoxes.contains(f.label)) {
                m_legendCheckBoxes[f.label]->blockSignals(true);
                m_legendCheckBoxes[f.label]->setChecked(true);
                m_legendCheckBoxes[f.label]->blockSignals(false);
            }
        }

        int colorIdx = m_sensorOrder.indexOf(f.label);
        QColor color = m_colors[colorIdx % m_colors.size()];
        QString colorHex = color.name();

        QString displayText = QStringLiteral(
            "<span style='color: %1; font-weight: bold;'>|</span> %2: "
            "<span style='color: %3; font-weight: bold;'>%4 RPM</span>")
            .arg(colorHex, f.label, ModernTheme::textPrimary)
            .arg(f.rpm);

        if (!m_legendLabels.contains(f.label)) {
            auto *cb = new QCheckBox();
            cb->setChecked(m_sensorVisible[f.label]);
            connect(cb, &QCheckBox::toggled, this, [this, name = f.label](bool checked) {
                m_sensorVisible[name] = checked;
                QSettings settings;
                settings.setValue(QStringLiteral("FanSensorVisible/%1").arg(name), checked);
                m_graphArea->update();
            });

            auto *lbl = new QLabel(displayText);
            lbl->setTextFormat(Qt::RichText);
            lbl->setAlignment(Qt::AlignLeft);

            int row = colorIdx / 2;
            int col = (colorIdx % 2) * 2;
            m_legendLayout->addWidget(cb, row, col);
            m_legendLayout->addWidget(lbl, row, col + 1);
            m_legendCheckBoxes[f.label] = cb;
            m_legendLabels[f.label] = lbl;
        } else {
            m_legendLabels[f.label]->setText(displayText);
        }
    }

    // Throttle history
    qint64 now = QDateTime::currentMSecsSinceEpoch();
    if (m_updateInterval > 0 &&
        (now - m_lastUpdateTime) < m_updateInterval * 1000LL)
        return;
    m_lastUpdateTime = now;

    // Update history — append nullopt to ALL tracked sensors first,
    // then overwrite with real values. Keeps timelines aligned
    // even when a sensor temporarily disappears from a poll.
    for (const QString &name : m_sensorOrder) {
        if (!m_history.contains(name)) continue;
        auto &hist = m_history[name];
        if (hist.size() >= m_maxlen) hist.removeFirst();
        hist.append(std::nullopt);
    }
    for (const FanReading &f : stats.fans) {
        if (!m_history.contains(f.label)) {
            QVector<std::optional<double>> vec;
            vec.fill(std::nullopt, m_maxlen);
            m_history[f.label] = vec;
        }
        auto &hist = m_history[f.label];
        if (!hist.isEmpty())
            hist[hist.size() - 1] = static_cast<double>(f.rpm);
    }

    m_graphArea->update();

    // Update tooltip if visible
    if (m_tooltip->isVisible() && m_hoverIndex >= 0) {
        int w = m_graphArea->width();
        int x = m_hoverPos.x();
        if (x < 40) {
            m_tooltip->hide();
        } else {
            int index = GraphUtils::hoverIndexFromX(x, w, m_maxlen, 40);
            int interval = qMax(1, m_updateInterval);
            int secondsAgo = (m_maxlen - 1 - index) * interval;
            QString timeStr = formatTimeOffset(secondsAgo);

            QStringList lines;
            lines.append(QStringLiteral("Time: -%1").arg(timeStr));

            for (const QString &name : m_sensorOrder) {
                if (!m_sensorVisible.value(name, false)) continue;
                if (!m_history.contains(name)) continue;
                const auto &pts = m_history[name];
                if (index < pts.size()) {
                    auto val = pts[index];
                    if (val.has_value())
                        lines.append(QStringLiteral("%1: %2 RPM").arg(name).arg(static_cast<int>(*val)));
                    else
                        lines.append(QStringLiteral("%1: NA").arg(name));
                }
            }
            m_tooltip->updateInfo(lines.join('\n'));
        }
    }
}

bool FanGraphWidget::eventFilter(QObject *watched, QEvent *event) {
    if (watched == m_graphArea) {
        if (event->type() == QEvent::Paint) {
            paintGraph(static_cast<QPaintEvent *>(event));
            return true;
        }

        if (event->type() == QEvent::MouseMove) {
            auto *me = static_cast<QMouseEvent *>(event);
            if (m_history.isEmpty()) return false;

            int w = m_graphArea->width();
            int x = me->pos().x();

            if (x < 40) {
                m_hoverIndex = -1;
                m_tooltip->hide();
                m_graphArea->update();
                return false;
            }

            int index = GraphUtils::hoverIndexFromX(x, w, m_maxlen, 40);

            m_hoverIndex = index;
            m_hoverPos = me->pos();

            int interval = qMax(1, m_updateInterval);
            int secondsAgo = (m_maxlen - 1 - index) * interval;
            QString timeStr = formatTimeOffset(secondsAgo);

            QStringList lines;
            lines.append(QStringLiteral("Time: -%1").arg(timeStr));

            for (const QString &name : m_sensorOrder) {
                if (!m_sensorVisible.value(name, false)) continue;
                if (!m_history.contains(name)) continue;
                const auto &pts = m_history[name];
                if (index < pts.size()) {
                    auto val = pts[index];
                    if (val.has_value())
                        lines.append(QStringLiteral("%1: %2 RPM").arg(name).arg(static_cast<int>(*val)));
                    else
                        lines.append(QStringLiteral("%1: NA").arg(name));
                }
            }

            m_tooltip->updateInfo(lines.join('\n'));
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

void FanGraphWidget::paintGraph(QPaintEvent *) {
    QPainter painter(m_graphArea);
    painter.setRenderHint(QPainter::Antialiasing);

    int w = m_graphArea->width();
    int h = m_graphArea->height();
    int bottomMargin = 20;
    int graphH = h - bottomMargin;
    int leftMargin = 40;

    // Dynamic Y scale
    double maxRpm = 2000.0;
    for (const QString &name : m_sensorOrder) {
        if (!m_history.contains(name)) continue;
        for (const auto &v : m_history[name]) {
            if (v.has_value() && *v > maxRpm) maxRpm = *v;
        }
    }
    maxRpm = static_cast<int>(maxRpm * 1.1);

    // Grid lines + Y-axis labels
    QPen gridPen(QColor(ModernTheme::borderColor));
    gridPen.setStyle(Qt::DotLine);

    QFont gridFont;
    gridFont.setPointSize(8);
    painter.setFont(gridFont);

    int steps = 4;
    for (int i = 0; i <= steps; ++i) {
        double val = i * (maxRpm / steps);
        int y = static_cast<int>(graphH - (val / maxRpm * graphH));

        painter.setPen(gridPen);
        painter.drawLine(leftMargin, y, w, y);

        painter.setPen(QColor(ModernTheme::textSecondary));
        painter.drawText(0, y + 4, 35, 10, Qt::AlignRight,
                         QString::number(static_cast<int>(val)));
    }

    // Time axis
    GraphUtils::drawTimeAxis(painter, w, h, bottomMargin, m_maxlen, m_updateInterval, leftMargin);

    // Draw sensor lines
    double stepX = (m_maxlen > 1) ? (double)(w - leftMargin) / (m_maxlen - 1) : 1.0;

    for (const QString &name : m_sensorOrder) {
        if (!m_sensorVisible.value(name, false)) continue;
        if (!m_history.contains(name)) continue;

        const auto &pts = m_history[name];
        if (pts.size() < 2) continue;

        int colorIdx = m_sensorOrder.indexOf(name);
        QColor color = m_colors[colorIdx % m_colors.size()];

        int numPoints = pts.size();
        double startX = w - (numPoints - 1) * stepX;

        QPainterPath path;
        double startVal = pts[0].value_or(0.0);
        double startY = graphH - (startVal / maxRpm * graphH);
        path.moveTo(startX, startY);

        for (int j = 0; j < numPoints; ++j) {
            double drawVal = pts[j].value_or(0.0);
            double x = startX + j * stepX;
            double y = graphH - (drawVal / maxRpm * graphH);
            path.lineTo(x, y);
        }

        painter.setPen(QPen(color, 2));
        painter.setBrush(Qt::NoBrush);
        painter.drawPath(path);
    }

    // Draw hover line once, then dots on top
    if (m_hoverIndex >= 0) {
        double hx = leftMargin + m_hoverIndex * stepX;
        GraphUtils::drawHoverLine(painter, hx, 0, graphH);

        for (const QString &name : m_sensorOrder) {
            if (!m_sensorVisible.value(name, false)) continue;
            if (!m_history.contains(name)) continue;
            const auto &pts = m_history[name];
            int numPoints = pts.size();
            int screenIdx = m_hoverIndex;
            int offset = (m_maxlen - 1) - screenIdx;
            int dataIdx = (numPoints - 1) - offset;

            if (dataIdx >= 0 && dataIdx < numPoints) {
                int colorIdx = m_sensorOrder.indexOf(name);
                QColor color = m_colors[colorIdx % m_colors.size()];
                double drawVal = pts[dataIdx].value_or(0.0);
                double hy = graphH - (drawVal / maxRpm * graphH);
                GraphUtils::drawHoverDot(painter, hx, hy, color);
            }
        }
    }
}
