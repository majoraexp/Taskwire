#pragma once

#include "base.h"
#include "systemmonitor.h"

#include <QGridLayout>
#include <QProgressBar>
#include <QLabel>
#include <QVector>

class CpuWidget : public Card {
    Q_OBJECT

public:
    explicit CpuWidget(QWidget *parent = nullptr);

    void updateData(const CpuStats &stats);
    void refreshTheme() override;

private:
    struct CoreRow {
        QLabel *nameLabel = nullptr;
        QProgressBar *bar = nullptr;
        QLabel *freqLabel = nullptr;
        QLabel *valueLabel = nullptr;
    };

    QGridLayout *m_grid;
    QVector<CoreRow> m_cores;
};
