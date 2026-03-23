#include "base.h"
#include "styles.h"

#include <QPainter>
#include <QMouseEvent>
#include <QFont>

// ── formatTimeOffset ────────────────────────────────────────

QString formatTimeOffset(int seconds) {
    if (seconds < 0) seconds = 0;
    if (seconds < 60)
        return QStringLiteral("%1s").arg(seconds);
    int m = seconds / 60;
    int s = seconds % 60;
    if (s > 0)
        return QStringLiteral("%1m %2s").arg(m).arg(s);
    return QStringLiteral("%1m").arg(m);
}

// ── GameTooltip ─────────────────────────────────────────────

GameTooltip::GameTooltip(QWidget *parent)
    : QWidget(parent, Qt::ToolTip | Qt::FramelessWindowHint)
{
    setAttribute(Qt::WA_TranslucentBackground);
    setAttribute(Qt::WA_ShowWithoutActivating);
    setAttribute(Qt::WA_TransparentForMouseEvents);

    QFont f;
    f.setPointSize(10);
    setFont(f);
}

void GameTooltip::updateInfo(const QString &text) {
    if (m_text != text) {
        m_text = text;
        adjustSize();
        update();
    }
}

void GameTooltip::paintEvent(QPaintEvent *) {
    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing);

    QRect r = rect();

    // Semi-transparent background
    QColor bg(ModernTheme::widgetBackground);
    bg.setAlpha(230);
    painter.setBrush(bg);

    // Neon border
    painter.setPen(QPen(QColor(ModernTheme::accentPurple), 1));
    painter.drawRoundedRect(r.adjusted(0, 0, -1, -1), 5, 5);

    // Text
    painter.setPen(QColor(ModernTheme::textPrimary));
    painter.drawText(r, Qt::AlignCenter, m_text);
}

QSize GameTooltip::sizeHint() const {
    QFontMetrics fm = fontMetrics();
    QSize s = fm.size(0, m_text);
    return QSize(s.width() + 20, s.height() + 15);
}

// ── Card ────────────────────────────────────────────────────

Card::Card(const QString &title, QWidget *parent)
    : QFrame(parent)
{
    setProperty("class", "card");
    m_layout = new QVBoxLayout(this);

    if (!title.isEmpty()) {
        m_titleLabel = new QLabel(title, this);
        m_titleLabel->setProperty("class", "title");
        m_titleLabel->setStyleSheet(
            QStringLiteral("font-size: 14px; font-weight: bold; color: %1;")
                .arg(ModernTheme::textPrimary));
        m_layout->addWidget(m_titleLabel);
        m_layout->addSpacing(10);
    }
}

void Card::refreshTheme() {
    if (m_titleLabel) {
        m_titleLabel->setStyleSheet(
            QStringLiteral("font-size: 14px; font-weight: bold; color: %1;")
                .arg(ModernTheme::textPrimary));
    }
    // Subclasses should override and call base
}

// ── SortableTableWidgetItem ─────────────────────────────────

bool SortableTableWidgetItem::operator<(const QTableWidgetItem &other) const {
    QVariant myVal = data(Qt::UserRole);
    QVariant otherVal = other.data(Qt::UserRole);

    // Numeric comparison if both are numeric
    if (myVal.canConvert<double>() && otherVal.canConvert<double>())
        return myVal.toDouble() < otherVal.toDouble();

    // String comparison (case-insensitive)
    return myVal.toString().toLower() < otherVal.toString().toLower();
}

// ── ModernHeader ────────────────────────────────────────────

ModernHeader::ModernHeader(Qt::Orientation orientation, QWidget *parent)
    : QHeaderView(orientation, parent)
{
    setSectionsMovable(true);
    setSectionsClickable(true);
    setSectionResizeMode(QHeaderView::Interactive);
    setStretchLastSection(false);
    setDefaultAlignment(Qt::AlignCenter);
}

void ModernHeader::mousePressEvent(QMouseEvent *event) {
    QHeaderView::mousePressEvent(event);
    if (event->button() == Qt::LeftButton)
        m_dragActive = true;
}

void ModernHeader::mouseMoveEvent(QMouseEvent *event) {
    QHeaderView::mouseMoveEvent(event);
    if (m_dragActive && (event->buttons() & Qt::LeftButton)) {
        int posX = event->pos().x();
        int logicalIdx = logicalIndexAt(event->pos());
        if (logicalIdx < 0) return;

        int sectionX = sectionViewportPosition(logicalIdx);
        int sectionW = sectionSize(logicalIdx);
        int center = sectionX + sectionW / 2;

        m_dropIndicatorX = (posX < center) ? sectionX : sectionX + sectionW;
        viewport()->update();
    }
}

void ModernHeader::mouseReleaseEvent(QMouseEvent *event) {
    QHeaderView::mouseReleaseEvent(event);
    m_dragActive = false;
    m_dropIndicatorX = -1;
    viewport()->update();
}

void ModernHeader::paintEvent(QPaintEvent *event) {
    QHeaderView::paintEvent(event);

    if (m_dragActive && m_dropIndicatorX >= 0) {
        QPainter painter(viewport());
        painter.setPen(QPen(QColor(ModernTheme::accentRed), 2));
        painter.drawLine(m_dropIndicatorX, 0, m_dropIndicatorX, height());
    }
}

void ModernHeader::paintSection(QPainter *painter, const QRect &rect, int logicalIndex) const {
    painter->save();
    QHeaderView::paintSection(painter, rect, logicalIndex);
    painter->restore();

    // Themed separator on right edge
    painter->save();
    painter->setPen(QPen(QColor(ModernTheme::accentBlue), 1));
    painter->drawLine(rect.topRight() - QPoint(1, 0), rect.bottomRight() - QPoint(1, 0));
    painter->restore();
}
