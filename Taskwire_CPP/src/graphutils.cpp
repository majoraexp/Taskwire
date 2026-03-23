#include "graphutils.h"
#include "base.h"
#include "styles.h"

#include <QPen>
#include <QFont>
#include <QPointF>

namespace GraphUtils {

QString formatBytes(long long bytes) {
    if (bytes < 1024LL)
        return QString::number(bytes) + " B";
    if (bytes < 1024LL * 1024)
        return QString::number(bytes / 1024.0, 'f', 1) + " KiB";
    if (bytes < 1024LL * 1024 * 1024)
        return QString::number(bytes / (1024.0 * 1024.0), 'f', 1) + " MiB";
    return QString::number(bytes / (1024.0 * 1024.0 * 1024.0), 'f', 1) + " GiB";
}

QString formatSpeed(double bytesPerSec) {
    if (bytesPerSec >= 1024.0 * 1024.0 * 1024.0)
        return QString::number(bytesPerSec / (1024.0 * 1024.0 * 1024.0), 'f', 1) + " GB/s";
    if (bytesPerSec >= 1024.0 * 1024.0)
        return QString::number(bytesPerSec / (1024.0 * 1024.0), 'f', 1) + " MB/s";
    if (bytesPerSec >= 1024.0)
        return QString::number(bytesPerSec / 1024.0, 'f', 1) + " KB/s";
    return QString::number(bytesPerSec, 'f', 1) + " B/s";
}

int hoverIndexFromX(int x, int width, int maxlen, int leftMargin) {
    int effectiveWidth = width - leftMargin;
    if (effectiveWidth <= 0 || maxlen <= 1) return 0;
    double stepX = (double)effectiveWidth / (maxlen - 1);
    int index = qRound((x - leftMargin) / stepX);
    return qBound(0, index, maxlen - 1);
}

double xFromIndex(int index, int width, int maxlen, int leftMargin) {
    if (maxlen <= 1) return leftMargin;
    double stepX = (double)(width - leftMargin) / (maxlen - 1);
    return leftMargin + index * stepX;
}

double yFromValue(double value, double minVal, double maxVal, int topMargin, int graphH) {
    if (maxVal <= minVal) return topMargin + graphH;
    double normalized = (value - minVal) / (maxVal - minVal);
    normalized = qBound(0.0, normalized, 1.0);
    return topMargin + graphH - (normalized * graphH);
}

void drawTimeAxis(QPainter &painter, int width, int height, int bottomMargin,
                  int maxlen, int updateInterval, int leftMargin) {
    int totalSeconds = (maxlen - 1) * qMax(1, updateInterval);
    int numTicks = 6;
    int effectiveWidth = width - leftMargin;

    QPen tickPen(QColor(ModernTheme::textSecondary));
    painter.setPen(tickPen);
    QFont axisFont;
    axisFont.setPointSize(8);
    painter.setFont(axisFont);

    for (int i = 0; i < numTicks; ++i) {
        double ratio = (double)i / (numTicks - 1);
        double x = leftMargin + ratio * effectiveWidth;
        int secondsAgo = static_cast<int>(totalSeconds * (1.0 - ratio));
        QString timeStr = formatTimeOffset(secondsAgo);

        Qt::Alignment flags = Qt::AlignCenter;
        QRectF textRect(x - 25, height - bottomMargin + 2, 50, 15);

        if (i == 0) {
            flags = Qt::AlignLeft;
            textRect = QRectF(leftMargin, height - bottomMargin + 2, 50, 15);
        } else if (i == numTicks - 1) {
            flags = Qt::AlignRight;
            textRect = QRectF(width - 50, height - bottomMargin + 2, 50, 15);
        }

        painter.drawText(textRect, flags, timeStr);
    }
}

void drawHoverLine(QPainter &painter, double hx, int top, int bottom) {
    painter.setPen(QPen(QColor(ModernTheme::borderColor), 1, Qt::DashLine));
    painter.drawLine(static_cast<int>(hx), top, static_cast<int>(hx), bottom);
}

void drawHoverDot(QPainter &painter, double hx, double hy, const QColor &color) {
    painter.setBrush(color);
    painter.setPen(Qt::NoPen);
    painter.drawEllipse(QPointF(hx, hy), 4, 4);
}

} // namespace GraphUtils
