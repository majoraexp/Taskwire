#pragma once

#include "base.h"
#include <QWidget>
#include <QLabel>
#include <QColor>
#include <QVector>
#include <QVariantMap>

// ── ModernGaugeWidget ───────────────────────────────────────
// A Card containing a circular progress arc gauge with percentage
// and optional detailed (used/total) display modes.

class ModernGaugeWidget : public Card {
    Q_OBJECT

public:
    explicit ModernGaugeWidget(const QString &title,
                               const QString &colorHex = {},
                               QWidget *parent = nullptr);

    void setColor(const QString &colorHex);
    void setSimplePercent(double percent);
    void setDetailedData(double percent, double used, double total,
                         const QString &unit = QStringLiteral("GiB"),
                         const QString &labelUsed = QStringLiteral("Used"),
                         const QString &labelTotal = QStringLiteral("Total"));

    void refreshTheme() override;

protected:
    bool eventFilter(QObject *watched, QEvent *event) override;

private:
    void paintGauge(QPaintEvent *event);

    struct TextLine {
        QString text;
        int size;
        bool bold;
        QString color;
    };

    double m_percent = 0.0;
    QString m_colorHex;   // empty = theme-adaptive (cyan dark / blue light)
    QColor m_color;
    QVector<TextLine> m_textLines;

    QLabel *m_labelUsedExt;
    QLabel *m_labelTotalExt;
    QWidget *m_gaugeArea;
};
