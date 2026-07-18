#pragma once

#include "base.h"
#include "systemmonitor.h"

#include <QWidget>
#include <QAbstractButton>
#include <QHBoxLayout>
#include <QLabel>
#include <QProgressBar>
#include <QGridLayout>
#include <QHash>
#include <QVector>
#include <optional>

// ── ModernDriveIcon ─────────────────────────────────────────

class ModernDriveIcon : public QAbstractButton {
    Q_OBJECT

public:
    explicit ModernDriveIcon(QWidget *parent = nullptr);

    void setActive(bool active);

protected:
    void paintEvent(QPaintEvent *event) override;

private:
    bool m_active = false;
};

// ── DiskWidget ──────────────────────────────────────────────

class DiskWidget : public Card {
    Q_OBJECT

public:
    explicit DiskWidget(QWidget *parent = nullptr);

    void updateData(const DiskUsageStats &stats);
    void refreshTheme() override;

protected:
    bool eventFilter(QObject *watched, QEvent *event) override;
    void resizeEvent(QResizeEvent *event) override;

private:
    void selectDrive(const QString &path);
    void refreshDisplay();
    void updateIconSizes();
    void applyTextStyles();

    int m_iconSide = 45;
    int m_naturalHint = 0;
    double m_uiScale = 1.0;
    QWidget *m_iconsArea;
    QHBoxLayout *m_iconsLayout;
    QHash<QString, ModernDriveIcon *> m_buttons;
    QString m_selectedPath;
    DiskUsageStats m_currentData;

    QLabel *m_modelLabel;
    QProgressBar *m_bar;
    QLabel *m_valLabel;
};

// ── DiskIOWidget ────────────────────────────────────────────

class DiskIOWidget : public Card {
    Q_OBJECT

public:
    explicit DiskIOWidget(QWidget *parent = nullptr);

    void setDuration(int seconds, int interval = 0);
    void updateData(const DiskIoStats &stats);
    void refreshTheme() override;

protected:
    bool eventFilter(QObject *watched, QEvent *event) override;

private:
    void paintGraph(QPaintEvent *event);
    void drawLine(QPainter &painter, const QVector<double> &data,
                  const QString &colorHex, double maxVal,
                  int w, int topMargin, int graphH, int h);

    int m_maxlen = 90;
    int m_updateInterval = 0;
    qint64 m_lastUpdateTime = 0;

    QVector<double> m_readHistory;
    QVector<double> m_writeHistory;

    QLabel *m_readVal;
    QLabel *m_writeVal;
    QProgressBar *m_readBar;
    QProgressBar *m_writeBar;

    QWidget *m_graphArea;
    GameTooltip *m_tooltip;
    int m_hoverIndex = -1;
};
