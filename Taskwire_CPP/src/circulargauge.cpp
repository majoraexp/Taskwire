#include "circulargauge.h"
#include "styles.h"
#include <QPainter>
#include <QMouseEvent>
#include <QToolTip>
#include <cmath>

CircularGauge::CircularGauge(QWidget *parent)
    : QWidget(parent)
{
    // Baseline size — MemoryWidget grows this when its card gets extra
    // height on tall displays; painting scales from a 160×160 design space
    setMinimumSize(160, 160);
    setMaximumSize(160, 160);
    setMouseTracking(true);
}

void CircularGauge::setData(double percent, double usedGb, double totalGb) {
    m_percent = percent;
    m_usedGb = usedGb;
    m_totalGb = totalGb;
    update();
}

void CircularGauge::mouseMoveEvent(QMouseEvent *event) {
    // Hover math in the same 160×160 design space the painting uses
    const double s = qMin(width(), height()) / 160.0;
    double radius = (160.0 - 20.0) / 2.0;

    double dx = event->pos().x() / s - 80.0;
    double dy = event->pos().y() / s - 80.0;
    double dist = std::sqrt(dx * dx + dy * dy);

    if (std::abs(dist - radius) < 15.0) {
        double angleRad = std::atan2(dy, dx);
        double angleDeg = angleRad * 180.0 / M_PI + 90.0;
        if (angleDeg < 0) angleDeg += 360.0;

        double usedDeg = m_percent * 3.6;
        QString text;

        if (angleDeg >= 0 && angleDeg <= usedDeg) {
            if (m_hoverSection != "used") {
                m_hoverSection = "used";
                update();
            }
            text = QString("Used: %1% (%2 GiB)")
                       .arg(m_percent, 0, 'f', 1)
                       .arg(m_usedGb, 0, 'f', 1);
        } else {
            if (m_hoverSection != "free") {
                m_hoverSection = "free";
                update();
            }
            double freeGb = qMax(0.0, m_totalGb - m_usedGb);
            double freePct = qMax(0.0, 100.0 - m_percent);
            text = QString("Free: %1% (%2 GiB)")
                       .arg(freePct, 0, 'f', 1)
                       .arg(freeGb, 0, 'f', 1);
        }

        QToolTip::showText(event->globalPosition().toPoint(), text, this);
    } else {
        if (!m_hoverSection.isEmpty()) {
            m_hoverSection.clear();
            update();
        }
        QToolTip::hideText();
    }

    QWidget::mouseMoveEvent(event);
}

void CircularGauge::leaveEvent(QEvent *event) {
    if (!m_hoverSection.isEmpty()) {
        m_hoverSection.clear();
        update();
    }
    QToolTip::hideText();
    QWidget::leaveEvent(event);
}

void CircularGauge::paintEvent(QPaintEvent *) {
    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing);

    // Drawn in a 160×160 design space, scaled to the actual widget size
    // so the arcs and text grow together
    painter.scale(qMin(width(), height()) / 160.0,
                  qMin(width(), height()) / 160.0);

    QRect r(0, 0, 160, 160);
    double size = qMin(r.width(), r.height()) - 20.0;
    double x = (r.width() - size) / 2.0;
    double y = (r.height() - size) / 2.0;
    double strokeWidth = 6.0;

    // Angles (Qt uses 1/16th degree, start at top = 90°)
    int startAngle = 90 * 16;
    int spanUsed = static_cast<int>(-m_percent * 3.6 * 16);
    int spanFree = static_cast<int>(-(100.0 - m_percent) * 3.6 * 16);

    // Colors based on hover state
    QColor colorUsed(ModernTheme::accentRed);
    QColor colorFree(ModernTheme::accentGreen);

    if (m_hoverSection == "used") {
        colorUsed = colorUsed.lighter(130);
        colorFree = colorFree.darker(200);
    } else if (m_hoverSection == "free") {
        colorFree = colorFree.lighter(130);
        colorUsed = colorUsed.darker(200);
    }

    // Draw used arc
    QPen penUsed(colorUsed, strokeWidth);
    penUsed.setCapStyle(Qt::RoundCap);
    painter.setPen(penUsed);
    painter.drawArc(QRectF(x, y, size, size), startAngle, spanUsed);

    // Draw free arc
    QPen penFree(colorFree, strokeWidth);
    penFree.setCapStyle(Qt::RoundCap);
    painter.setPen(penFree);
    painter.drawArc(QRectF(x, y, size, size), startAngle + spanUsed, spanFree);

    // Draw center text
    QFont font;
    font.setPointSize(20);
    font.setBold(true);
    painter.setFont(font);
    painter.setPen(QColor(ModernTheme::textPrimary));

    QString pctText = QString("%1%").arg(m_percent, 0, 'f', 1);
    QFontMetrics fm(font);
    int textW = fm.horizontalAdvance(pctText);
    painter.drawText(r.center().x() - textW / 2,
                     r.center().y() - 10,
                     pctText);

    // Used GiB below
    font.setPointSize(12);
    painter.setFont(font);
    QString gbText = QString("%1 GiB").arg(m_usedGb, 0, 'f', 1);
    QFontMetrics fm2(font);
    int gbW = fm2.horizontalAdvance(gbText);
    painter.drawText(r.center().x() - gbW / 2,
                     r.center().y() + 25,
                     gbText);
}
