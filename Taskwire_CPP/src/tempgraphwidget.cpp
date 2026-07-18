#include "tempgraphwidget.h"
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

TempGraphWidget::TempGraphWidget(QWidget *parent)
    : Card("Temperatures", parent)
{
    m_colors = {
        QColor(ModernTheme::accentPurple),
        QColor(ModernTheme::accentBlue),
        QColor(ModernTheme::accentRed),
        QColor(ModernTheme::accentGreen),
        QColor(ModernTheme::accentOrange)
    };

    m_graphArea = new QWidget(this);
    m_graphArea->setMinimumHeight(150);
    m_graphArea->setMouseTracking(true);
    m_graphArea->installEventFilter(this);
    cardLayout()->addWidget(m_graphArea, 1);

    m_legendContainer = new QWidget();
    m_legendLayout = new QGridLayout(m_legendContainer);
    m_legendLayout->setContentsMargins(0, 0, 0, 0);
    m_legendLayout->setVerticalSpacing(0);
    m_legendLayout->setHorizontalSpacing(4);
    // Spacer column (col 2) absorbs extra width so legend items stay left-aligned
    m_legendLayout->setColumnStretch(2, 1);

    m_legendScroll = new QScrollArea();
    m_legendScroll->setWidget(m_legendContainer);
    m_legendScroll->setWidgetResizable(true);
    m_legendScroll->setFrameShape(QFrame::NoFrame);
    m_legendScroll->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    m_legendScroll->setStyleSheet(QStringLiteral("background: transparent;"));
    cardLayout()->addWidget(m_legendScroll, 1);

    m_tooltip = new GameTooltip(m_graphArea);
}

QColor TempGraphWidget::sensorColor(int index) const {
    return m_colors[index % m_colors.size()];
}

void TempGraphWidget::refreshTheme() {
    Card::refreshTheme();
    m_colors = {
        QColor(ModernTheme::accentPurple),
        QColor(ModernTheme::accentBlue),
        QColor(ModernTheme::accentRed),
        QColor(ModernTheme::accentGreen),
        QColor(ModernTheme::accentOrange)
    };
    // Clear legend so it rebuilds with new colors
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

void TempGraphWidget::setDuration(int seconds, int interval) {
    m_maxlen = seconds;
    m_updateInterval = interval;
    m_history.clear();
    m_sensorOrder.clear();
    m_graphArea->update();
}

void TempGraphWidget::updateData(const TempStats &stats) {
    if (!stats.valid) return;

    // Update legend
    for (int i = 0; i < stats.temps.size(); ++i) {
        const TempReading &t = stats.temps[i];

        // Track insertion order
        if (!m_sensorOrder.contains(t.label))
            m_sensorOrder.append(t.label);

        // Default visibility: load from settings, default to visible
        if (!m_sensorVisible.contains(t.label)) {
            QSettings settings;
            m_sensorVisible[t.label] = settings.value(
                QStringLiteral("TempSensorVisible/%1").arg(t.label), true).toBool();
        }

        int colorIdx = m_sensorOrder.indexOf(t.label);
        QColor color = sensorColor(colorIdx);
        QString colorHex = color.name();

        QString displayText = QStringLiteral(
            "<span style='color: %1; font-weight: bold;'>%2:</span> "
            "<span style='color: %3;'>%4\u00b0C</span>")
            .arg(colorHex, t.label, ModernTheme::textPrimary)
            .arg(t.celsius, 0, 'f', 1);

        if (!m_legendLabels.contains(t.label)) {
            auto *cb = new QCheckBox();
            cb->setChecked(m_sensorVisible[t.label]);
            connect(cb, &QCheckBox::toggled, this, [this, name = t.label](bool checked) {
                m_sensorVisible[name] = checked;
                QSettings settings;
                settings.setValue(QStringLiteral("TempSensorVisible/%1").arg(name), checked);
                m_graphArea->update();
            });

            auto *lbl = new QLabel(displayText);
            lbl->setTextFormat(Qt::RichText);
            lbl->setAlignment(Qt::AlignLeft);

            int row = colorIdx;
            m_legendLayout->addWidget(cb, row, 0);
            m_legendLayout->addWidget(lbl, row, 1);
            m_legendCheckBoxes[t.label] = cb;
            m_legendLabels[t.label] = lbl;
        } else {
            m_legendLabels[t.label]->setText(displayText);
        }
    }

    // Throttle history update
    qint64 now = QDateTime::currentMSecsSinceEpoch();
    if (m_updateInterval > 0 &&
        (now - m_lastUpdateTime) < m_updateInterval * 1000LL)
        return;
    m_lastUpdateTime = now;

    // Update history — append nullopt to ALL tracked sensors first,
    // then overwrite with real values. This keeps timelines aligned
    // even when a sensor temporarily disappears from a poll.
    for (const QString &name : m_sensorOrder) {
        if (!m_history.contains(name)) continue;
        auto &hist = m_history[name];
        if (hist.size() >= m_maxlen) hist.removeFirst();
        hist.append(std::nullopt);
    }
    for (const TempReading &t : stats.temps) {
        if (!m_history.contains(t.label)) {
            QVector<std::optional<double>> vec;
            vec.fill(std::nullopt, m_maxlen);
            m_history[t.label] = vec;
        }
        auto &hist = m_history[t.label];
        if (!hist.isEmpty())
            hist[hist.size() - 1] = t.celsius;
    }

    m_graphArea->update();

    // Update tooltip if visible
    if (m_tooltip->isVisible() && m_hoverIndex >= 0) {
        int interval = qMax(1, m_updateInterval);
        int secondsAgo = (m_maxlen - 1 - m_hoverIndex) * interval;
        QString timeStr = formatTimeOffset(secondsAgo);

        QStringList lines;
        lines.append(QStringLiteral("Time: -%1").arg(timeStr));

        for (const QString &name : m_sensorOrder) {
            if (!m_sensorVisible.value(name, true)) continue;
            if (!m_history.contains(name)) continue;
            const auto &pts = m_history[name];
            if (m_hoverIndex < pts.size()) {
                auto val = pts[m_hoverIndex];
                if (val.has_value())
                    lines.append(QStringLiteral("%1: %2\u00b0C").arg(name).arg(*val, 0, 'f', 1));
                else
                    lines.append(QStringLiteral("%1: NA").arg(name));
            }
        }
        m_tooltip->updateInfo(lines.join('\n'));
    }
}

bool TempGraphWidget::eventFilter(QObject *watched, QEvent *event) {
    if (watched == m_graphArea) {
        if (event->type() == QEvent::Paint) {
            paintGraph(static_cast<QPaintEvent *>(event));
            return true;
        }

        if (event->type() == QEvent::MouseMove) {
            auto *me = static_cast<QMouseEvent *>(event);
            if (m_history.isEmpty()) return false;

            int w = m_graphArea->width();
            int index = GraphUtils::hoverIndexFromX(me->pos().x(), w, m_maxlen);

            m_hoverIndex = index;

            int interval = qMax(1, m_updateInterval);
            int secondsAgo = (m_maxlen - 1 - index) * interval;
            QString timeStr = formatTimeOffset(secondsAgo);

            QStringList lines;
            lines.append(QStringLiteral("Time: -%1").arg(timeStr));

            for (const QString &name : m_sensorOrder) {
                if (!m_sensorVisible.value(name, true)) continue;
                if (!m_history.contains(name)) continue;
                const auto &pts = m_history[name];
                if (index < pts.size()) {
                    auto val = pts[index];
                    if (val.has_value())
                        lines.append(QStringLiteral("%1: %2\u00b0C").arg(name).arg(*val, 0, 'f', 1));
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

void TempGraphWidget::paintGraph(QPaintEvent *) {
    QPainter painter(m_graphArea);
    painter.setRenderHint(QPainter::Antialiasing);

    int w = m_graphArea->width();
    int h = m_graphArea->height();
    int bottomMargin = 20;
    int topMargin = 10;
    int graphH = h - bottomMargin - topMargin;

    double minTemp = 30.0;
    double maxTemp = 100.0;
    double tempRange = maxTemp - minTemp;

    // Grid lines at 40, 60, 80, 100°C
    QPen gridPen(QColor(ModernTheme::borderColor));
    gridPen.setStyle(Qt::DotLine);
    painter.setPen(gridPen);

    QFont gridFont;
    gridFont.setPointSize(8);
    painter.setFont(gridFont);

    for (int t : {40, 60, 80, 100}) {
        double normalized = (t - minTemp) / tempRange;
        int y = static_cast<int>(topMargin + graphH - (normalized * graphH));
        painter.setPen(gridPen);
        painter.drawLine(0, y, w, y);
        painter.setPen(QColor(ModernTheme::textSecondary));
        painter.drawText(2, y - 2, QStringLiteral("%1\u00b0C").arg(t));
    }

    // Time axis
    GraphUtils::drawTimeAxis(painter, w, h, bottomMargin, m_maxlen, m_updateInterval);

    // Draw transition line
    double stepX = (m_maxlen > 1) ? (double)w / (m_maxlen - 1) : 1.0;
    int transitionIdx = -1;
    QVector<QPair<double, QColor>> transitionSensors;

    for (const QString &name : m_sensorOrder) {
        if (!m_sensorVisible.value(name, true)) continue;
        if (!m_history.contains(name)) continue;
        const auto &pts = m_history[name];
        int colorIdx = m_sensorOrder.indexOf(name);

        for (int j = 0; j < pts.size(); ++j) {
            if (pts[j].has_value()) {
                if (transitionIdx < 0 || j < transitionIdx)
                    transitionIdx = j;
                transitionSensors.append({*pts[j], sensorColor(colorIdx)});
                break;
            }
        }
    }

    if (transitionIdx > 0 && !transitionSensors.isEmpty()) {
        double tx = transitionIdx * stepX;
        double baselineY = topMargin + graphH;

        // Sort by value (lowest at bottom)
        std::sort(transitionSensors.begin(), transitionSensors.end(),
                  [](const QPair<double, QColor> &a, const QPair<double, QColor> &b) {
                      return a.first < b.first;
                  });

        double prevY = baselineY;
        for (const auto &[val, color] : transitionSensors) {
            double curY = GraphUtils::yFromValue(val, minTemp, maxTemp, topMargin, graphH);
            painter.setPen(QPen(color, 2));
            painter.drawLine(static_cast<int>(tx), static_cast<int>(prevY),
                             static_cast<int>(tx), static_cast<int>(curY));
            prevY = curY;
        }
    }

    // Draw sensor lines
    for (const QString &name : m_sensorOrder) {
        if (!m_sensorVisible.value(name, true)) continue;
        if (!m_history.contains(name)) continue;
        const auto &pts = m_history[name];
        if (pts.size() < 2) continue;

        int colorIdx = m_sensorOrder.indexOf(name);
        QColor color = sensorColor(colorIdx);

        // Build dual paths: unfilled (cyan) and real (sensor color)
        QPainterPath unfilledPath;
        QPainterPath realPath;
        bool prevWasNone = true;
        bool prevWasReal = false;

        for (int j = 0; j < pts.size(); ++j) {
            double x = j * stepX;
            double v = pts[j].value_or(0.0);
            double y = GraphUtils::yFromValue(v, minTemp, maxTemp, topMargin, graphH);

            if (!pts[j].has_value()) {
                if (prevWasNone) {
                    if (j == 0) unfilledPath.moveTo(x, y);
                    else unfilledPath.lineTo(x, y);
                } else {
                    unfilledPath.moveTo(x, y);
                }
                prevWasNone = true;
                prevWasReal = false;
            } else {
                if (prevWasReal) {
                    if (j == 0) realPath.moveTo(x, y);
                    else realPath.lineTo(x, y);
                } else {
                    // Start from baseline then up to real value
                    double baselineY = topMargin + graphH;
                    realPath.moveTo(x, baselineY);
                    realPath.lineTo(x, y);
                }
                prevWasReal = true;
                prevWasNone = false;
            }
        }

        // Draw unfilled in cyan
        painter.setPen(QPen(QColor(ModernTheme::accentCyan), 2));
        painter.setBrush(Qt::NoBrush);
        painter.drawPath(unfilledPath);

        // Draw real in sensor color
        painter.setPen(QPen(color, 2));
        painter.setBrush(Qt::NoBrush);
        painter.drawPath(realPath);
    }

    // Draw hover line once, then dots on top
    if (m_hoverIndex >= 0) {
        double hx = m_hoverIndex * stepX;
        GraphUtils::drawHoverLine(painter, hx, 0, h - bottomMargin);

        for (const QString &name : m_sensorOrder) {
            if (!m_sensorVisible.value(name, true)) continue;
            if (!m_history.contains(name)) continue;
            const auto &pts = m_history[name];
            if (m_hoverIndex < pts.size()) {
                int colorIdx = m_sensorOrder.indexOf(name);
                QColor color = sensorColor(colorIdx);
                double v = pts[m_hoverIndex].value_or(0.0);
                double hy = GraphUtils::yFromValue(v, minTemp, maxTemp, topMargin, graphH);
                GraphUtils::drawHoverDot(painter, hx, hy, color);
            }
        }
    }
}
