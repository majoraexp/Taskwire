#include "gaugewidget.h"
#include "styles.h"

#include <QPainter>
#include <QPen>
#include <QFont>
#include <cmath>

ModernGaugeWidget::ModernGaugeWidget(const QString &title,
                                     const QString &colorHex,
                                     QWidget *parent)
    : Card(title, parent)
{
    m_colorHex = colorHex;
    m_color = QColor(colorHex.isEmpty()
        ? (QColor(ModernTheme::appBackground).lightness() > 128
            ? ModernTheme::accentBlue : ModernTheme::accentCyan)
        : colorHex);

    // External label: above gauge
    m_labelUsedExt = new QLabel(this);
    m_labelUsedExt->setAlignment(Qt::AlignCenter);
    m_labelUsedExt->setStyleSheet(
        QStringLiteral("color: %1; font-size: 11px;").arg(ModernTheme::textPrimary));
    cardLayout()->addWidget(m_labelUsedExt);
    m_labelUsedExt->hide();

    // Gauge drawing area
    m_gaugeArea = new QWidget(this);
    m_gaugeArea->setMinimumHeight(140);
    // Override paintEvent via lambda-like approach: use an event filter
    m_gaugeArea->installEventFilter(this);
    cardLayout()->addWidget(m_gaugeArea, 1);

    // External label: below gauge
    m_labelTotalExt = new QLabel(this);
    m_labelTotalExt->setAlignment(Qt::AlignCenter);
    m_labelTotalExt->setStyleSheet(
        QStringLiteral("color: %1; font-size: 11px;").arg(ModernTheme::textPrimary));
    cardLayout()->addWidget(m_labelTotalExt);
    m_labelTotalExt->hide();
}

void ModernGaugeWidget::setSimplePercent(double percent) {
    m_percent = percent;
    m_textLines.clear();
    m_textLines.append({QStringLiteral("%1%").arg(percent, 0, 'f', 1),
                        24, true, ModernTheme::textPrimary});
    m_labelUsedExt->hide();
    m_labelTotalExt->hide();
    m_gaugeArea->update();
}

void ModernGaugeWidget::setDetailedData(double percent, double used, double total,
                                        const QString &unit,
                                        const QString &labelUsed,
                                        const QString &labelTotal) {
    m_percent = percent;

    m_labelUsedExt->setText(labelUsed);
    m_labelUsedExt->show();

    m_textLines.clear();
    m_textLines.append({QStringLiteral("%1 %2").arg(used, 0, 'f', 1).arg(unit),
                        16, true, ModernTheme::textPrimary});
    m_textLines.append({QStringLiteral("%1 %2").arg(total, 0, 'f', 1).arg(unit),
                        16, true, ModernTheme::textPrimary});

    m_labelTotalExt->setText(labelTotal);
    m_labelTotalExt->show();

    m_gaugeArea->update();
}

void ModernGaugeWidget::refreshTheme() {
    Card::refreshTheme();
    m_labelUsedExt->setStyleSheet(
        QStringLiteral("color: %1; font-size: 11px;").arg(ModernTheme::textPrimary));
    m_labelTotalExt->setStyleSheet(
        QStringLiteral("color: %1; font-size: 11px;").arg(ModernTheme::textPrimary));

    // Refresh accent color for theme-adaptive gauges
    if (m_colorHex.isEmpty()) {
        m_color = QColor(QColor(ModernTheme::appBackground).lightness() > 128
            ? ModernTheme::accentBlue : ModernTheme::accentCyan);
    }

    for (auto &line : m_textLines)
        line.color = ModernTheme::textPrimary;

    m_gaugeArea->update();
}

void ModernGaugeWidget::paintGauge(QPaintEvent *) {
    QPainter painter(m_gaugeArea);
    painter.setRenderHint(QPainter::Antialiasing);

    int w = m_gaugeArea->width();
    int h = m_gaugeArea->height();

    double size = qMin(w, h) - 10.0;
    double x = (w - size) / 2.0;
    double y = (h - size) / 2.0;

    QRectF arcRect(x, y, size, size);

    // 1. Track (background ring) — uses theme's alternate table bg for proper light/dark support
    QPen trackPen(QColor(ModernTheme::alternateTableBg), 6);
    trackPen.setCapStyle(Qt::RoundCap);
    painter.setPen(trackPen);
    painter.drawEllipse(arcRect);

    // 2. Progress arc
    int startAngle = 90 * 16;
    int spanAngle = static_cast<int>(-m_percent * 3.6 * 16);

    QPen progPen(m_color, 6);
    progPen.setCapStyle(Qt::RoundCap);
    painter.setPen(progPen);
    painter.drawArc(arcRect, startAngle, spanAngle);

    // 3. Text values centered in gauge
    double cx = w / 2.0;
    double cy = h / 2.0;

    if (m_textLines.size() == 1) {
        // Simple centered percentage
        const TextLine &line = m_textLines[0];
        int dynamicSize = qMax(12, static_cast<int>(size * 0.18));

        QFont font;
        font.setPointSize(dynamicSize);
        font.setBold(line.bold);
        painter.setFont(font);
        painter.setPen(QColor(line.color));

        QFontMetrics fm(font);
        int tw = fm.horizontalAdvance(line.text);
        painter.drawText(static_cast<int>(cx - tw / 2.0),
                         static_cast<int>(cy + fm.ascent() / 2.0 - 5),
                         line.text);

    } else if (m_textLines.size() == 2) {
        // Stacked: used / total with separator line
        int dynamicSize = qMax(10, static_cast<int>(size * 0.12));
        int offsets[2] = {-static_cast<int>(size * 0.1),
                          static_cast<int>(size * 0.1)};

        for (int i = 0; i < 2; ++i) {
            const TextLine &line = m_textLines[i];

            QFont font;
            font.setPointSize(dynamicSize);
            font.setBold(line.bold);
            painter.setFont(font);

            QFontMetrics fm(font);
            int tw = fm.horizontalAdvance(line.text);

            // Draw separator between the two values
            if (i == 1) {
                painter.setPen(QPen(QColor(ModernTheme::borderColor), 1));
                int lineLen = static_cast<int>(size * 0.4);
                painter.drawLine(static_cast<int>(cx - lineLen),
                                 static_cast<int>(cy - 2),
                                 static_cast<int>(cx + lineLen),
                                 static_cast<int>(cy - 2));
            }

            painter.setPen(QColor(line.color));
            painter.drawText(static_cast<int>(cx - tw / 2.0),
                             static_cast<int>(cy + offsets[i] + fm.ascent() / 2.0 - 5),
                             line.text);
        }
    }
}

// Override eventFilter to intercept paint events on m_gaugeArea
#include <QEvent>
#include <QPaintEvent>

bool ModernGaugeWidget::eventFilter(QObject *watched, QEvent *event) {
    if (watched == m_gaugeArea && event->type() == QEvent::Paint) {
        paintGauge(static_cast<QPaintEvent *>(event));
        return true; // handled
    }
    return Card::eventFilter(watched, event);
}
