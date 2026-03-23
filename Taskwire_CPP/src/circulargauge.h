#pragma once
#include <QWidget>

class CircularGauge : public QWidget {
    Q_OBJECT

public:
    explicit CircularGauge(QWidget *parent = nullptr);

    void setData(double percent, double usedGb, double totalGb);

protected:
    void paintEvent(QPaintEvent *event) override;
    void mouseMoveEvent(QMouseEvent *event) override;
    void leaveEvent(QEvent *event) override;

private:
    double m_percent = 0.0;
    double m_usedGb = 0.0;
    double m_totalGb = 0.0;
    QString m_hoverSection; // "used", "free", or ""
};
