#pragma once

#include <QString>
#include <QPainter>
#include <QRectF>
#include <QColor>

namespace GraphUtils {

// Format bytes to human-readable string (KiB, MiB, GiB)
QString formatBytes(long long bytes);

// Format speed in bytes/sec to human-readable (B/s, KB/s, MB/s, GB/s)
QString formatSpeed(double bytesPerSec);

// Convert mouse X position to data index (clamped to [0, maxlen-1])
int hoverIndexFromX(int x, int width, int maxlen, int leftMargin = 0);

// Convert data index to pixel X position
double xFromIndex(int index, int width, int maxlen, int leftMargin = 0);

// Convert a value to pixel Y (value in [minVal,maxVal] → pixel in [topMargin, topMargin+graphH])
double yFromValue(double value, double minVal, double maxVal, int topMargin, int graphH);

// Draw time axis labels along the bottom
void drawTimeAxis(QPainter &painter, int width, int height, int bottomMargin,
                  int maxlen, int updateInterval, int leftMargin = 0);

// Draw vertical dashed hover line
void drawHoverLine(QPainter &painter, double hx, int top, int bottom);

// Draw hover dot at position
void drawHoverDot(QPainter &painter, double hx, double hy, const QColor &color);

} // namespace GraphUtils
