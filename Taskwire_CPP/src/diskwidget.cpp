#include "diskwidget.h"
#include "graphutils.h"
#include "styles.h"

#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QBrush>
#include <QFont>
#include <QPolygonF>
#include <QLinearGradient>
#include <QRadialGradient>
#include <QMouseEvent>
#include <QEvent>
#include <QDateTime>
#include <QSettings>
#include <algorithm>

// ── ModernDriveIcon ─────────────────────────────────────────

ModernDriveIcon::ModernDriveIcon(QWidget *parent)
    : QAbstractButton(parent)
{
    setFixedSize(45, 45);
    setCursor(Qt::PointingHandCursor);
}

void ModernDriveIcon::setActive(bool active) {
    m_active = active;
    update();
}

void ModernDriveIcon::paintEvent(QPaintEvent *) {
    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing);

    int w = width();
    int h = height();

    QColor baseColor(ModernTheme::alternateTableBg);
    QColor highlight(ModernTheme::borderColor);
    bool lightMode = QColor(ModernTheme::appBackground).lightness() > 128;
    QString accentStr = lightMode ? ModernTheme::accentBlue : ModernTheme::accentCyan;
    QColor accent = m_active ? QColor(accentStr) : QColor(ModernTheme::accentBlue);

    // Top face (lightest)
    QPolygonF topPoly;
    topPoly << QPointF(7, 10) << QPointF(15, 5) << QPointF(38, 5) << QPointF(30, 10);
    painter.setPen(Qt::NoPen);
    painter.setBrush(highlight.lighter(130));
    painter.drawPolygon(topPoly);

    // Side face (darkest)
    QPolygonF sidePoly;
    sidePoly << QPointF(30, 10) << QPointF(38, 5) << QPointF(38, 35) << QPointF(30, 40);
    painter.setBrush(baseColor.darker(120));
    painter.drawPolygon(sidePoly);

    // Front face (gradient)
    QRectF faceRect(7, 10, 23, 30);
    QLinearGradient grad(faceRect.topLeft(), faceRect.bottomRight());
    grad.setColorAt(0, highlight);
    grad.setColorAt(1, baseColor);
    painter.setBrush(grad);
    painter.drawRoundedRect(faceRect, 2, 2);

    // Sticker label
    QRectF labelRect(10, 14, 17, 10);
    painter.setBrush(QColor(ModernTheme::appBackground));
    painter.drawRoundedRect(labelRect, 1, 1);

    // LED
    QPointF ledCenter(18, 32);
    if (m_active) {
        QRadialGradient glow(ledCenter, 6);
        glow.setColorAt(0, accent);
        glow.setColorAt(1, Qt::transparent);
        painter.setBrush(glow);
        painter.drawEllipse(ledCenter, 3, 3);
        painter.setBrush(accent.lighter(150));
        painter.drawEllipse(ledCenter, 1, 1);
    } else {
        painter.setBrush(QColor(ModernTheme::textSecondary).darker(150));
        painter.drawEllipse(ledCenter, 1.5, 1.5);
    }

    // Selection ring
    if (m_active) {
        painter.setBrush(Qt::NoBrush);
        painter.setPen(QPen(accent, 2));
        painter.drawRoundedRect(2, 2, w - 4, h - 4, 5, 5);
    } else if (underMouse()) {
        painter.setBrush(Qt::NoBrush);
        painter.setPen(QPen(QColor(ModernTheme::borderColor), 1));
        painter.drawRoundedRect(2, 2, w - 4, h - 4, 5, 5);
    }
}

// ── DiskWidget ──────────────────────────────────────────────

DiskWidget::DiskWidget(QWidget *parent)
    : Card("Disk Usage", parent)
{
    QSettings settings;
    m_selectedPath = settings.value(QStringLiteral("DiskUsage/selectedDrive")).toString();

    auto *iconsWidget = new QWidget();
    m_iconsLayout = new QHBoxLayout(iconsWidget);
    m_iconsLayout->setContentsMargins(0, 0, 0, 0);
    m_iconsLayout->setSpacing(10);
    m_iconsLayout->setAlignment(Qt::AlignLeft);
    cardLayout()->addWidget(iconsWidget);

    m_modelLabel = new QLabel("Scanning...");
    {
        const QString &c = QColor(ModernTheme::appBackground).lightness() > 128
            ? ModernTheme::accentBlue : ModernTheme::accentCyan;
        m_modelLabel->setStyleSheet(
            QStringLiteral("color: %1; font-weight: bold; font-size: 14px;").arg(c));
    }
    m_modelLabel->setAlignment(Qt::AlignCenter);
    cardLayout()->addWidget(m_modelLabel);

    m_bar = new QProgressBar();
    m_bar->setRange(0, 100);
    m_bar->setTextVisible(false);
    m_bar->setStyleSheet(
        QStringLiteral("QProgressBar::chunk { background-color: %1; }").arg(ModernTheme::accentOrange));
    cardLayout()->addWidget(m_bar);

    m_valLabel = new QLabel("0 / 0 GB");
    m_valLabel->setAlignment(Qt::AlignCenter);
    cardLayout()->addWidget(m_valLabel);

    cardLayout()->addStretch();
}

void DiskWidget::refreshTheme() {
    Card::refreshTheme();
    {
        const QString &c = QColor(ModernTheme::appBackground).lightness() > 128
            ? ModernTheme::accentBlue : ModernTheme::accentCyan;
        m_modelLabel->setStyleSheet(
            QStringLiteral("color: %1; font-weight: bold; font-size: 14px;").arg(c));
    }
    m_bar->setStyleSheet(
        QStringLiteral("QProgressBar::chunk { background-color: %1; }").arg(ModernTheme::accentOrange));
    for (auto *btn : m_buttons)
        btn->update();
}

void DiskWidget::updateData(const DiskUsageStats &stats) {
    if (!stats.valid) return;
    m_currentData = stats;

    QSet<QString> currentKeys;
    for (auto it = stats.disks.constBegin(); it != stats.disks.constEnd(); ++it)
        currentKeys.insert(it.key());

    QSet<QString> existingKeys;
    for (auto it = m_buttons.constBegin(); it != m_buttons.constEnd(); ++it)
        existingKeys.insert(it.key());

    if (currentKeys != existingKeys) {
        // Clear existing buttons
        for (auto *btn : m_buttons) {
            m_iconsLayout->removeWidget(btn);
            btn->deleteLater();
        }
        m_buttons.clear();

        // Create new buttons (sorted for stable order)
        QStringList sortedKeys = currentKeys.values();
        std::sort(sortedKeys.begin(), sortedKeys.end());

        for (const QString &path : sortedKeys) {
            auto *btn = new ModernDriveIcon();
            const DiskInfo &info = stats.disks[path];
            btn->setToolTip(QStringLiteral("%1 (%2)").arg(info.model, path));

            connect(btn, &QAbstractButton::clicked, this, [this, path]() {
                selectDrive(path);
            });

            m_iconsLayout->addWidget(btn);
            m_buttons[path] = btn;
        }

        // Restore or default selection
        if (currentKeys.contains(m_selectedPath)) {
            selectDrive(m_selectedPath);
        } else if (!currentKeys.isEmpty()) {
            selectDrive(sortedKeys.first());
        }
    }

    if (!m_selectedPath.isEmpty() && m_currentData.disks.contains(m_selectedPath))
        refreshDisplay();
}

void DiskWidget::selectDrive(const QString &path) {
    m_selectedPath = path;
    QSettings settings;
    settings.setValue(QStringLiteral("DiskUsage/selectedDrive"), path);
    for (auto it = m_buttons.constBegin(); it != m_buttons.constEnd(); ++it)
        it.value()->setActive(it.key() == path);
    refreshDisplay();
}

void DiskWidget::refreshDisplay() {
    if (m_selectedPath.isEmpty() || !m_currentData.disks.contains(m_selectedPath))
        return;

    const DiskInfo &info = m_currentData.disks[m_selectedPath];
    double totalGb = info.sizeBytes / (1024.0 * 1024.0 * 1024.0);
    double usedGb = info.usedBytes / (1024.0 * 1024.0 * 1024.0);

    QString sizeStr, usedStr, totalStr;
    if (totalGb >= 1000.0) {
        sizeStr = QStringLiteral("%1 TiB").arg(totalGb / 1024.0, 0, 'f', 2);
        usedStr = QStringLiteral("%1 TiB").arg(usedGb / 1024.0, 0, 'f', 2);
        totalStr = sizeStr;
    } else {
        sizeStr = QStringLiteral("%1 GiB").arg(totalGb, 0, 'f', 1);
        usedStr = QStringLiteral("%1 GiB").arg(usedGb, 0, 'f', 1);
        totalStr = sizeStr;
    }

    m_modelLabel->setText(QStringLiteral("%1 (%2)").arg(info.model, sizeStr));
    m_bar->setValue(static_cast<int>(info.percent));
    m_valLabel->setText(QStringLiteral("%1 / %2  %3%").arg(usedStr, totalStr)
                            .arg(info.percent, 0, 'f', 1));
}

// ── DiskIOWidget ────────────────────────────────────────────

DiskIOWidget::DiskIOWidget(QWidget *parent)
    : Card("Hard Disk Activity", parent)
{
    m_readHistory.fill(0.0, m_maxlen);
    m_writeHistory.fill(0.0, m_maxlen);

    // Read row
    auto *readTop = new QHBoxLayout();
    auto *readLabel = new QLabel("Read Rate");
    m_readVal = new QLabel("0.0 B/s");
    m_readVal->setAlignment(Qt::AlignRight);
    readTop->addWidget(readLabel);
    readTop->addWidget(m_readVal);
    cardLayout()->addLayout(readTop);

    m_readBar = new QProgressBar();
    m_readBar->setRange(0, 100);
    m_readBar->setTextVisible(false);
    m_readBar->setFixedHeight(8);
    m_readBar->setStyleSheet(
        QStringLiteral("QProgressBar::chunk { background-color: %1; }").arg(ModernTheme::accentBlue));
    cardLayout()->addWidget(m_readBar);

    cardLayout()->addSpacing(10);

    // Write row
    auto *writeTop = new QHBoxLayout();
    auto *writeLabel = new QLabel("Write Rate");
    m_writeVal = new QLabel("0.0 B/s");
    m_writeVal->setAlignment(Qt::AlignRight);
    writeTop->addWidget(writeLabel);
    writeTop->addWidget(m_writeVal);
    cardLayout()->addLayout(writeTop);

    m_writeBar = new QProgressBar();
    m_writeBar->setRange(0, 100);
    m_writeBar->setTextVisible(false);
    m_writeBar->setFixedHeight(8);
    m_writeBar->setStyleSheet(
        QStringLiteral("QProgressBar::chunk { background-color: %1; }").arg(ModernTheme::accentRed));
    cardLayout()->addWidget(m_writeBar);

    cardLayout()->addSpacing(10);

    // Graph area
    m_graphArea = new QWidget(this);
    m_graphArea->setMinimumHeight(150);
    m_graphArea->setMouseTracking(true);
    m_graphArea->installEventFilter(this);
    cardLayout()->addWidget(m_graphArea, 1);

    m_tooltip = new GameTooltip(m_graphArea);
}

void DiskIOWidget::refreshTheme() {
    Card::refreshTheme();
    m_readBar->setStyleSheet(
        QStringLiteral("QProgressBar::chunk { background-color: %1; }").arg(ModernTheme::accentBlue));
    m_writeBar->setStyleSheet(
        QStringLiteral("QProgressBar::chunk { background-color: %1; }").arg(ModernTheme::accentRed));
    m_graphArea->update();
}

void DiskIOWidget::setDuration(int seconds, int interval) {
    m_maxlen = seconds;
    m_updateInterval = interval;
    m_readHistory.clear();
    m_readHistory.fill(0.0, m_maxlen);
    m_writeHistory.clear();
    m_writeHistory.fill(0.0, m_maxlen);
    m_graphArea->update();
}

void DiskIOWidget::updateData(const DiskIoStats &stats) {
    if (!stats.valid) return;

    double readSpeed = stats.readBytesPerSec;
    double writeSpeed = stats.writeBytesPerSec;

    m_readVal->setText(GraphUtils::formatSpeed(readSpeed));
    m_writeVal->setText(GraphUtils::formatSpeed(writeSpeed));

    // Bar scaling (cap at 500 MB/s)
    double maxSpeed = 500.0 * 1024.0 * 1024.0;
    int rPct = qMin(100, static_cast<int>((readSpeed / maxSpeed) * 100));
    int wPct = qMin(100, static_cast<int>((writeSpeed / maxSpeed) * 100));
    if (readSpeed > 0 && rPct < 1) rPct = 1;
    if (writeSpeed > 0 && wPct < 1) wPct = 1;
    m_readBar->setValue(rPct);
    m_writeBar->setValue(wPct);

    // Throttle history
    qint64 now = QDateTime::currentMSecsSinceEpoch();
    if (m_updateInterval > 0 &&
        (now - m_lastUpdateTime) < m_updateInterval * 1000LL)
        return;
    m_lastUpdateTime = now;

    if (m_readHistory.size() >= m_maxlen) m_readHistory.removeFirst();
    m_readHistory.append(readSpeed);
    if (m_writeHistory.size() >= m_maxlen) m_writeHistory.removeFirst();
    m_writeHistory.append(writeSpeed);

    m_graphArea->update();

    // Update tooltip if visible
    if (m_tooltip->isVisible() && m_hoverIndex >= 0 && m_hoverIndex < m_readHistory.size()) {
        int interval = qMax(1, m_updateInterval);
        int secondsAgo = (m_maxlen - 1 - m_hoverIndex) * interval;
        QString timeStr = formatTimeOffset(secondsAgo);
        m_tooltip->updateInfo(QStringLiteral("Time: -%1\nRead: %2\nWrite: %3")
            .arg(timeStr,
                 GraphUtils::formatSpeed(m_readHistory[m_hoverIndex]),
                 GraphUtils::formatSpeed(m_writeHistory[m_hoverIndex])));
    }
}

bool DiskIOWidget::eventFilter(QObject *watched, QEvent *event) {
    if (watched == m_graphArea) {
        if (event->type() == QEvent::Paint) {
            paintGraph(static_cast<QPaintEvent *>(event));
            return true;
        }

        if (event->type() == QEvent::MouseMove) {
            auto *me = static_cast<QMouseEvent *>(event);
            if (m_readHistory.size() < 2) return false;

            int w = m_graphArea->width();
            int index = GraphUtils::hoverIndexFromX(me->pos().x(), w, m_maxlen);
            index = qBound(0, index, m_readHistory.size() - 1);

            m_hoverIndex = index;
            m_hoverPos = me->pos();

            int interval = qMax(1, m_updateInterval);
            int secondsAgo = (m_maxlen - 1 - index) * interval;
            QString timeStr = formatTimeOffset(secondsAgo);

            m_tooltip->updateInfo(QStringLiteral("Time: -%1\nRead: %2\nWrite: %3")
                .arg(timeStr,
                     GraphUtils::formatSpeed(m_readHistory[index]),
                     GraphUtils::formatSpeed(m_writeHistory[index])));

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

void DiskIOWidget::drawLine(QPainter &painter, const QVector<double> &data,
                             const QString &colorHex, double maxVal,
                             int w, int topMargin, int graphH, int h) {
    if (data.size() < 2) return;

    QPainterPath path;
    double stepX = (m_maxlen > 1) ? (double)w / (m_maxlen - 1) : 1.0;

    double startY = topMargin + graphH - ((data[0] / maxVal) * graphH);
    path.moveTo(0, startY);

    for (int i = 0; i < data.size(); ++i) {
        double x = i * stepX;
        double y = topMargin + graphH - ((data[i] / maxVal) * graphH);
        path.lineTo(x, y);
    }

    painter.setPen(QPen(QColor(colorHex), 2));
    painter.setBrush(Qt::NoBrush);
    painter.drawPath(path);
}

void DiskIOWidget::paintGraph(QPaintEvent *) {
    QPainter painter(m_graphArea);
    painter.setRenderHint(QPainter::Antialiasing);

    int w = m_graphArea->width();
    int h = m_graphArea->height();
    int bottomMargin = 20;
    int topMargin = 10;
    int graphH = h - bottomMargin - topMargin;

    // Dynamic Y scale
    double maxVal = 0.0;
    for (double v : m_readHistory) maxVal = qMax(maxVal, v);
    for (double v : m_writeHistory) maxVal = qMax(maxVal, v);
    if (maxVal == 0.0) maxVal = 100.0;
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

    // Draw read (blue) then write (red)
    drawLine(painter, m_readHistory, ModernTheme::accentBlue, maxVal, w, topMargin, graphH, h);
    drawLine(painter, m_writeHistory, ModernTheme::accentRed, maxVal, w, topMargin, graphH, h);

    // Draw hover line once, then dots on top
    if (m_hoverIndex >= 0 && m_hoverIndex < m_readHistory.size()) {
        double stepX = (m_maxlen > 1) ? (double)w / (m_maxlen - 1) : 1.0;
        double hx = m_hoverIndex * stepX;
        GraphUtils::drawHoverLine(painter, hx, 0, h - bottomMargin);

        if (m_hoverIndex < m_readHistory.size()) {
            double hy = topMargin + graphH - ((m_readHistory[m_hoverIndex] / maxVal) * graphH);
            GraphUtils::drawHoverDot(painter, hx, hy, QColor(ModernTheme::accentBlue));
        }
        if (m_hoverIndex < m_writeHistory.size()) {
            double hy = topMargin + graphH - ((m_writeHistory[m_hoverIndex] / maxVal) * graphH);
            GraphUtils::drawHoverDot(painter, hx, hy, QColor(ModernTheme::accentRed));
        }
    }
}
