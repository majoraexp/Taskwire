#include "cpuwidget.h"
#include "styles.h"

CpuWidget::CpuWidget(QWidget *parent)
    : Card("CPU Utilization (Per Thread)", parent)
{
    m_grid = new QGridLayout();
    cardLayout()->addLayout(m_grid);
}

void CpuWidget::refreshTheme() {
    Card::refreshTheme();
    // Clear grid — bars rebuild on next updateData()
    while (m_grid->count()) {
        QLayoutItem *item = m_grid->takeAt(0);
        if (item->widget())
            item->widget()->deleteLater();
        delete item;
    }
    m_cores.clear();
}

void CpuWidget::updateData(const CpuStats &stats) {
    if (!stats.valid) return;

    const auto &perCore = stats.corePercents;
    const auto &freqs = stats.coreFreqsMHz;

    // Create bars lazily on first call (or after theme refresh)
    if (m_cores.isEmpty() && !perCore.isEmpty()) {
        bool lightMode = QColor(ModernTheme::appBackground).lightness() > 128;
        const QString colors[] = {
            ModernTheme::accentPurple,
            lightMode ? ModernTheme::accentBlue : ModernTheme::accentCyan,
            ModernTheme::accentGreen,
            ModernTheme::accentOrange
        };

        for (int i = 0; i < perCore.size(); ++i) {
            CoreRow row;

            row.nameLabel = new QLabel(QStringLiteral("Core %1").arg(i + 1));
            row.nameLabel->setStyleSheet(
                QStringLiteral("color: %1; font-size: 11px;").arg(ModernTheme::textSecondary));

            row.bar = new QProgressBar();
            row.bar->setRange(0, 100);
            row.bar->setTextVisible(false);
            row.bar->setFixedHeight(6);

            const QString &color = colors[i % 4];
            row.bar->setStyleSheet(
                QStringLiteral(
                    "QProgressBar::chunk { background-color: %1; border-radius: 2px; }"
                    "QProgressBar { background-color: %2; border: none; border-radius: 2px; }")
                    .arg(color, ModernTheme::alternateTableBg));

            row.freqLabel = new QLabel("0 MHz");
            row.freqLabel->setStyleSheet(
                QStringLiteral("color: %1; font-size: 10px;").arg(
                    lightMode ? ModernTheme::accentBlue : ModernTheme::accentCyan));
            row.freqLabel->setAlignment(Qt::AlignRight);

            row.valueLabel = new QLabel("0%");
            row.valueLabel->setFixedWidth(45);
            row.valueLabel->setAlignment(Qt::AlignLeft);
            row.valueLabel->setStyleSheet("font-size: 12px;");

            int gridRow = i / 4; // 4 cores per row
            int colGroup = i % 4;
            int baseCol = colGroup * 5; // 4 widgets + 1 spacer

            m_grid->addWidget(row.nameLabel, gridRow, baseCol);
            m_grid->addWidget(row.bar, gridRow, baseCol + 1);
            m_grid->addWidget(row.freqLabel, gridRow, baseCol + 2);
            m_grid->addWidget(row.valueLabel, gridRow, baseCol + 3);

            if (colGroup < 3)
                m_grid->setColumnMinimumWidth(baseCol + 4, 10);

            m_cores.append(row);
        }
    }

    // Update values
    for (int i = 0; i < perCore.size() && i < m_cores.size(); ++i) {
        CoreRow &row = m_cores[i];
        row.bar->setValue(static_cast<int>(perCore[i]));
        row.valueLabel->setText(QStringLiteral("%1%").arg(perCore[i], 0, 'f', 0));

        if (i < freqs.size()) {
            double f = freqs[i];
            if (f >= 1000.0)
                row.freqLabel->setText(QStringLiteral("%1 GHz").arg(f / 1000.0, 0, 'f', 1));
            else
                row.freqLabel->setText(QStringLiteral("%1 MHz").arg(static_cast<int>(f)));
        } else {
            row.freqLabel->setText({});
        }
    }
}
