#pragma once

#include <QFrame>
#include <QWidget>
#include <QLabel>
#include <QVBoxLayout>
#include <QHeaderView>
#include <QTableWidgetItem>
#include <QString>

// ── Utility ─────────────────────────────────────────────────

QString formatTimeOffset(int seconds);

// ── GameTooltip ─────────────────────────────────────────────
// Custom translucent tooltip widget with neon border (game HUD style).

class GameTooltip : public QWidget {
    Q_OBJECT

public:
    explicit GameTooltip(QWidget *parent = nullptr);

    void updateInfo(const QString &text);

protected:
    void paintEvent(QPaintEvent *event) override;
    QSize sizeHint() const override;

private:
    QString m_text;
};

// ── Card ────────────────────────────────────────────────────
// Base container with optional title and vertical layout.

class Card : public QFrame {
    Q_OBJECT

public:
    explicit Card(const QString &title = {}, QWidget *parent = nullptr);

    QVBoxLayout *cardLayout() const { return m_layout; }

    virtual void refreshTheme();

private:
    QVBoxLayout *m_layout;
    QLabel *m_titleLabel = nullptr;
};

// ── SortableTableWidgetItem ─────────────────────────────────
// Sorts by UserRole data (numeric) when available, falls back to string.

class SortableTableWidgetItem : public QTableWidgetItem {
public:
    using QTableWidgetItem::QTableWidgetItem;
    bool operator<(const QTableWidgetItem &other) const override;
};

// ── ModernHeader ────────────────────────────────────────────
// Themed header with movable sections and a drag-and-drop indicator.

class ModernHeader : public QHeaderView {
    Q_OBJECT

public:
    explicit ModernHeader(Qt::Orientation orientation, QWidget *parent = nullptr);

protected:
    void mousePressEvent(QMouseEvent *event) override;
    void mouseMoveEvent(QMouseEvent *event) override;
    void mouseReleaseEvent(QMouseEvent *event) override;
    void paintEvent(QPaintEvent *event) override;
    void paintSection(QPainter *painter, const QRect &rect, int logicalIndex) const override;

private:
    bool m_dragActive = false;
    int m_dropIndicatorX = -1;
};
