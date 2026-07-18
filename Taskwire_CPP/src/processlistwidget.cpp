#include "processlistwidget.h"
#include "styles.h"
#include "graphutils.h"
#include "filterutils.h"

#include <QTableWidget>
#include <QStackedWidget>
#include <QLineEdit>
#include <QPushButton>
#include <QHBoxLayout>
#include <QHeaderView>
#include <QScrollBar>
#include <QMenu>
#include <QMessageBox>
#include <QDialog>
#include <QCheckBox>
#include <QDialogButtonBox>
#include <QProcess>
#include <QStandardPaths>
#include <QSettings>
#include <QThread>

#include <signal.h>
#include <errno.h>

#include <algorithm>
#include <climits>
#include <functional>

// ── Constructor ─────────────────────────────────────────────

ProcessListWidget::ProcessListWidget(QWidget *parent)
    : Card(QStringLiteral("Processes"), parent)
{
    // Column definitions: id, label, availableGrouped, availableDetail
    m_columnDefs = {
        {QStringLiteral("pid"),         QStringLiteral("PID"),            true,  true},
        {QStringLiteral("name"),        QStringLiteral("Name"),           true,  true},
        {QStringLiteral("ppid"),        QStringLiteral("PPID"),           false, true},
        {QStringLiteral("count"),       QStringLiteral("Count"),          true,  false},
        {QStringLiteral("cpu"),         QStringLiteral("CPU %"),          true,  true},
        {QStringLiteral("gpu"),         QStringLiteral("GPU %"),          true,  true},
        {QStringLiteral("mem"),         QStringLiteral("Memory %"),       true,  true},
        {QStringLiteral("mem_mb"),      QStringLiteral("Resident"),       true,  true},
        {QStringLiteral("mem_shared"),  QStringLiteral("Shared"),         true,  true},
        {QStringLiteral("mem_swap"),    QStringLiteral("Swap"),           true,  true},
        {QStringLiteral("read_bytes"),  QStringLiteral("Read Bytes"),     true,  true},
        {QStringLiteral("write_bytes"), QStringLiteral("Write Bytes"),    true,  true},
        {QStringLiteral("threads"),     QStringLiteral("Threads"),        true,  true},
        {QStringLiteral("user"),        QStringLiteral("User"),           false, true},
        {QStringLiteral("status"),      QStringLiteral("Status"),         false, true},
    };

    m_visibleGrouped = {
        QStringLiteral("name"), QStringLiteral("cpu"), QStringLiteral("gpu"),
        QStringLiteral("mem"), QStringLiteral("mem_mb"), QStringLiteral("mem_swap"),
        QStringLiteral("count")
    };
    m_visibleDetail = {
        QStringLiteral("pid"), QStringLiteral("name"), QStringLiteral("cpu"),
        QStringLiteral("gpu"), QStringLiteral("mem"), QStringLiteral("mem_mb"),
        QStringLiteral("mem_shared"), QStringLiteral("mem_swap")
    };

    // Load persisted column selections (override defaults if saved)
    {
        QSettings settings;
        QStringList saved = settings.value(QStringLiteral("ProcessColumns/grouped")).toStringList();
        if (!saved.isEmpty()) {
            if (!saved.contains(QStringLiteral("gpu")))
                saved.append(QStringLiteral("gpu"));
            m_visibleGrouped = QVector<QString>(saved.begin(), saved.end());
        }

        saved = settings.value(QStringLiteral("ProcessColumns/detail")).toStringList();
        if (!saved.isEmpty()) {
            if (!saved.contains(QStringLiteral("gpu")))
                saved.append(QStringLiteral("gpu"));
            m_visibleDetail = QVector<QString>(saved.begin(), saved.end());
        }
    }

    // Action bar
    auto *actionLayout = new QHBoxLayout();

    m_searchInput = new QLineEdit(this);
    m_searchInput->setPlaceholderText(QStringLiteral("Search Process... (use * for wildcard)"));
    connect(m_searchInput, &QLineEdit::textChanged, this, &ProcessListWidget::onSearchChanged);
    actionLayout->addWidget(m_searchInput);

    m_viewBtn = new QPushButton(QStringLiteral("View: Grouped"), this);
    m_viewBtn->setFixedSize(120, 30);
    connect(m_viewBtn, &QPushButton::clicked, this, &ProcessListWidget::toggleView);
    actionLayout->addWidget(m_viewBtn);

    cardLayout()->addLayout(actionLayout);

    // Stacked widget with two tables
    m_stack = new QStackedWidget(this);
    cardLayout()->addWidget(m_stack);

    // Grouped table
    m_groupTable = new QTableWidget(this);
    setupTableStyle(m_groupTable);
    updateColumns(Grouped);
    m_groupTable->setContextMenuPolicy(Qt::CustomContextMenu);
    connect(m_groupTable, &QTableWidget::customContextMenuRequested,
            this, &ProcessListWidget::showGroupContextMenu);

    auto *gHeader = m_groupTable->horizontalHeader();
    gHeader->setContextMenuPolicy(Qt::CustomContextMenu);
    connect(gHeader, &QHeaderView::customContextMenuRequested,
            this, [this](const QPoint &pos) { showHeaderContextMenu(pos, Grouped); });
    connect(gHeader, &QHeaderView::sectionClicked,
            this, [this](int idx) { onHeaderClicked(idx, Grouped); });

    m_stack->addWidget(m_groupTable);

    // Detail table
    m_detailTable = new QTableWidget(this);
    setupTableStyle(m_detailTable);
    updateColumns(Detail);
    m_detailTable->setContextMenuPolicy(Qt::CustomContextMenu);
    connect(m_detailTable, &QTableWidget::customContextMenuRequested,
            this, &ProcessListWidget::showDetailContextMenu);

    auto *dHeader = m_detailTable->horizontalHeader();
    dHeader->setContextMenuPolicy(Qt::CustomContextMenu);
    connect(dHeader, &QHeaderView::customContextMenuRequested,
            this, [this](const QPoint &pos) { showHeaderContextMenu(pos, Detail); });
    connect(dHeader, &QHeaderView::sectionClicked,
            this, [this](int idx) { onHeaderClicked(idx, Detail); });

    m_stack->addWidget(m_detailTable);

    // Apply initial theme
    refreshTheme();
}

// ── Theme ───────────────────────────────────────────────────

void ProcessListWidget::refreshTheme() {
    Card::refreshTheme();

    // View toggle button uses accentCyan (widget-specific override)
    m_viewBtn->setStyleSheet(QStringLiteral(
        "QPushButton { background-color: %1; color: %2; "
        "border: 1px solid %3; border-radius: 6px; font-weight: bold; padding: 4px 10px; }"
        "QPushButton:hover { background-color: %3; color: %4; }")
        .arg(ModernTheme::widgetBackground, ModernTheme::textPrimary,
             ModernTheme::accentCyan, ModernTheme::appBackground));
}

// ── Table helpers ───────────────────────────────────────────

void ProcessListWidget::setupTableStyle(QTableWidget *table) {
    table->verticalHeader()->setVisible(false);
    table->setShowGrid(false);
    table->setAlternatingRowColors(true);
    table->setSelectionBehavior(QAbstractItemView::SelectRows);
    table->setSelectionMode(QAbstractItemView::SingleSelection);
    table->setSortingEnabled(false);

    // Apply selection style directly to the table widget to override native
    // Linux theme (Breeze/GTK) which ignores global qApp->setStyleSheet()
    table->setStyleSheet(QStringLiteral(
        "QTableView::item:selected:active,"
        "QTableView::item:selected:!active {"
        "    background-color: %1;"
        "    color: white;"
        "}"
    ).arg(ModernTheme::accentBlue));

    auto *header = new ModernHeader(Qt::Horizontal, table);
    table->setHorizontalHeader(header);
}

// ── Column management ───────────────────────────────────────

void ProcessListWidget::updateColumns(ViewMode mode) {
    QTableWidget *table = (mode == Grouped) ? m_groupTable : m_detailTable;
    const auto &visible = (mode == Grouped) ? m_visibleGrouped : m_visibleDetail;

    QStringList labels;
    for (const auto &colId : visible) {
        for (const auto &def : m_columnDefs) {
            if (def.id == colId) {
                labels.append(def.label);
                break;
            }
        }
    }
    table->setColumnCount(labels.size());
    table->setHorizontalHeaderLabels(labels);
}

void ProcessListWidget::updateSortIndicator(QTableWidget *table,
                                             const QVector<QString> &visibleCols) {
    int idx = visibleCols.indexOf(m_sortColId);
    if (idx >= 0) {
        auto order = m_sortDescending ? Qt::DescendingOrder : Qt::AscendingOrder;
        table->horizontalHeader()->setSortIndicatorShown(true);
        table->horizontalHeader()->setSortIndicator(idx, order);
    }
}

void ProcessListWidget::onHeaderClicked(int logicalIndex, ViewMode mode) {
    const auto &visible = (mode == Grouped) ? m_visibleGrouped : m_visibleDetail;
    if (logicalIndex >= visible.size()) return;

    const QString &colId = visible[logicalIndex];

    if (colId == m_sortColId) {
        m_sortDescending = !m_sortDescending;
    } else {
        m_sortColId = colId;
        // Text columns default ascending, numeric descending
        static const QSet<QString> textCols = {
            QStringLiteral("name"), QStringLiteral("user"),
            QStringLiteral("status"), QStringLiteral("pid")
        };
        m_sortDescending = !textCols.contains(colId);
    }

    auto *table = (mode == Grouped) ? m_groupTable : m_detailTable;
    int currentScroll = table->verticalScrollBar()->value();
    int currentRow = table->currentRow();

    table->clearSelection();
    updateSortIndicator(table, visible);
    refreshCurrentView(false);

    // Don't restore row index — after sort it's a different entity.
    // Just restore scroll position.
    table->verticalScrollBar()->setValue(currentScroll);
}

void ProcessListWidget::showHeaderContextMenu(const QPoint &pos, ViewMode mode) {
    auto *table = (mode == Grouped) ? m_groupTable : m_detailTable;

    QMenu menu(this);

    auto *customize = menu.addAction(QStringLiteral("Customize Columns..."));
    connect(customize, &QAction::triggered, this, [this, mode]() { openColumnDialog(mode); });

    menu.exec(table->horizontalHeader()->mapToGlobal(pos));
}

void ProcessListWidget::openColumnDialog(ViewMode mode) {
    QDialog dialog(this);
    dialog.setWindowTitle(QStringLiteral("Select Metrics (%1)")
        .arg(mode == Grouped ? QStringLiteral("Grouped") : QStringLiteral("Details")));
    auto *layout = new QVBoxLayout(&dialog);
    QHash<QString, QCheckBox*> checkboxes;

    const auto &currentVisible = (mode == Grouped) ? m_visibleGrouped : m_visibleDetail;

    for (const auto &def : m_columnDefs) {
        if (mode == Grouped && !def.availableGrouped) continue;
        if (mode == Detail && !def.availableDetail) continue;

        auto *cb = new QCheckBox(def.label, &dialog);
        cb->setChecked(currentVisible.contains(def.id));
        checkboxes.insert(def.id, cb);
        layout->addWidget(cb);
    }

    auto *buttons = new QDialogButtonBox(
        QDialogButtonBox::Ok | QDialogButtonBox::Cancel, &dialog);
    connect(buttons, &QDialogButtonBox::accepted, &dialog, &QDialog::accept);
    connect(buttons, &QDialogButtonBox::rejected, &dialog, &QDialog::reject);
    layout->addWidget(buttons);

    if (dialog.exec() != QDialog::Accepted) return;

    // Preserve definition order
    QVector<QString> newVisible;
    for (const auto &def : m_columnDefs) {
        if (checkboxes.contains(def.id) && checkboxes[def.id]->isChecked())
            newVisible.append(def.id);
    }

    if (newVisible.isEmpty()) {
        QMessageBox::warning(this, QStringLiteral("Invalid Selection"),
                             QStringLiteral("You must select at least one column."));
        return;
    }

    if (mode == Grouped)
        m_visibleGrouped = newVisible;
    else
        m_visibleDetail = newVisible;

    // Persist column selection
    QSettings settings;
    QString key = (mode == Grouped)
        ? QStringLiteral("ProcessColumns/grouped")
        : QStringLiteral("ProcessColumns/detail");
    settings.setValue(key, QStringList(newVisible.begin(), newVisible.end()));

    updateColumns(mode);
    refreshCurrentView();
}

// ── Search / Filter ─────────────────────────────────────────

void ProcessListWidget::onSearchChanged(const QString &text) {
    m_filterText = text;
    refreshCurrentView();
}

// ── View toggle ─────────────────────────────────────────────

void ProcessListWidget::toggleView() {
    if (m_viewMode == Grouped) {
        switchToDetails();
    } else {
        m_viewMode = Grouped;
        m_viewBtn->setText(QStringLiteral("View: Grouped"));
        m_stack->setCurrentIndex(0);
        refreshCurrentView();
    }
}

void ProcessListWidget::switchToDetails(const QString &filterName) {
    m_viewMode = Detail;
    m_viewBtn->setText(QStringLiteral("View: Details"));
    m_stack->setCurrentIndex(1);
    if (!filterName.isEmpty())
        m_searchInput->setText(filterName);
    refreshCurrentView();
}

// ── Data update ─────────────────────────────────────────────

void ProcessListWidget::updateData(const ProcessStats &stats) {
    m_processData = stats.processes;
    m_gpuPollElapsedNs = stats.gpuPollElapsedNs;
    refreshCurrentView();
}

void ProcessListWidget::refreshCurrentView(bool maintainSelection) {
    if (m_viewMode == Grouped)
        updateGroupedTable(maintainSelection);
    else
        updateDetailTable(maintainSelection);
}

// Determine if a column should be sorted numerically (vs string).
// This avoids canConvert<double>() pitfalls (NaN process names, mixed types).
static bool isNumericColumn(const QString &colId) {
    static const QSet<QString> textCols = {
        QStringLiteral("name"), QStringLiteral("user"), QStringLiteral("status")
    };
    return !textCols.contains(colId);
}

// ── Grouped table ───────────────────────────────────────────

void ProcessListWidget::updateGroupedTable(bool maintainSelection) {
    struct GroupedStats {
        int count = 0;
        int parentPid = INT_MAX;
        double cpuPercent = 0.0;
        double memoryPercent = 0.0;
        long long rssBytes = 0;
        long long sharedBytes = 0;
        long long swapBytes = 0;
        long long readBytes = 0;
        long long writeBytes = 0;
        int numThreads = 0;
        QHash<QString, quint64> gpuDeltaByClient; // max delta per unique client
    };

    QHash<QString, GroupedStats> groups;

    for (const auto &p : m_processData) {
        if (!m_filterText.isEmpty() && !FilterUtils::matchesFilter(p.name, m_filterText))
            continue;

        auto &s = groups[p.name];
        s.count++;
        if (p.pid < s.parentPid)
            s.parentPid = p.pid;
        s.cpuPercent += p.cpuPercent;
        s.memoryPercent += p.memoryPercent;
        s.rssBytes += p.rssBytes;
        s.sharedBytes += p.sharedBytes;
        s.swapBytes += p.swapBytes;
        s.readBytes += p.readBytes;
        s.writeBytes += p.writeBytes;
        s.numThreads += p.numThreads;

        for (const auto &c : p.gpuClientDeltas) {
            QString k = c.driver + QLatin1Char('|') + c.pdev + QLatin1Char('|')
                        + QString::number(c.clientId);
            auto git = s.gpuDeltaByClient.find(k);
            if (git == s.gpuDeltaByClient.end() || c.deltaNs > *git)
                s.gpuDeltaByClient[k] = c.deltaNs;
        }
    }

    QVector<RowData> displayData;
    for (auto it = groups.cbegin(); it != groups.cend(); ++it) {
        quint64 gpuUniqueDeltaNs = 0;
        for (quint64 d : it->gpuDeltaByClient)
            gpuUniqueDeltaNs += d;
        double groupedGpu = (m_gpuPollElapsedNs > 0)
            ? std::clamp(static_cast<double>(gpuUniqueDeltaNs)
                         / static_cast<double>(m_gpuPollElapsedNs) * 100.0, 0.0, 100.0)
            : 0.0;

        RowData row;
        row[QStringLiteral("pid")] = it->parentPid;
        row[QStringLiteral("name")] = it.key();
        row[QStringLiteral("count")] = it->count;
        row[QStringLiteral("cpu")] = it->cpuPercent;
        row[QStringLiteral("gpu")] = groupedGpu;
        row[QStringLiteral("mem")] = it->memoryPercent;
        row[QStringLiteral("mem_mb")] = it->rssBytes;
        row[QStringLiteral("mem_shared")] = it->sharedBytes;
        row[QStringLiteral("mem_swap")] = it->swapBytes;
        row[QStringLiteral("read_bytes")] = it->readBytes;
        row[QStringLiteral("write_bytes")] = it->writeBytes;
        row[QStringLiteral("threads")] = it->numThreads;
        displayData.append(row);
    }

    // Sort
    std::sort(displayData.begin(), displayData.end(),
        [this](const RowData &a, const RowData &b) {
            QVariant va = getSortKey(a);
            QVariant vb = getSortKey(b);
            if (isNumericColumn(m_sortColId)) {
                return m_sortDescending
                    ? va.toDouble() > vb.toDouble()
                    : va.toDouble() < vb.toDouble();
            }
            return m_sortDescending
                ? va.toString().toLower() > vb.toString().toLower()
                : va.toString().toLower() < vb.toString().toLower();
        });

    renderTable(m_groupTable, displayData, m_visibleGrouped, maintainSelection);
}

// ── Detail table ────────────────────────────────────────────

void ProcessListWidget::updateDetailTable(bool maintainSelection) {
    QVector<RowData> displayData;

    for (const auto &p : m_processData) {
        if (!m_filterText.isEmpty() && !FilterUtils::matchesFilter(p.name, m_filterText))
            continue;

        RowData row;
        row[QStringLiteral("pid")] = p.pid;
        row[QStringLiteral("name")] = p.name;
        row[QStringLiteral("ppid")] = p.ppid;
        row[QStringLiteral("cpu")] = p.cpuPercent;
        row[QStringLiteral("gpu")] = p.gpuPercent;
        row[QStringLiteral("mem")] = p.memoryPercent;
        row[QStringLiteral("mem_mb")] = p.rssBytes;
        row[QStringLiteral("mem_shared")] = p.sharedBytes;
        row[QStringLiteral("mem_swap")] = p.swapBytes;
        row[QStringLiteral("read_bytes")] = p.readBytes;
        row[QStringLiteral("write_bytes")] = p.writeBytes;
        row[QStringLiteral("threads")] = p.numThreads;
        row[QStringLiteral("user")] = p.user;
        row[QStringLiteral("status")] = p.status;
        displayData.append(row);
    }

    // Sort
    std::sort(displayData.begin(), displayData.end(),
        [this](const RowData &a, const RowData &b) {
            QVariant va = getSortKey(a);
            QVariant vb = getSortKey(b);
            if (isNumericColumn(m_sortColId)) {
                return m_sortDescending
                    ? va.toDouble() > vb.toDouble()
                    : va.toDouble() < vb.toDouble();
            }
            return m_sortDescending
                ? va.toString().toLower() > vb.toString().toLower()
                : va.toString().toLower() < vb.toString().toLower();
        });

    renderTable(m_detailTable, displayData, m_visibleDetail, maintainSelection);
}

// ── Sort key extraction ─────────────────────────────────────

QVariant ProcessListWidget::getSortKey(const RowData &row) const {
    if (row.contains(m_sortColId))
        return row.value(m_sortColId);
    return QVariant(0);
}

// ── Cell formatting ─────────────────────────────────────────

QString ProcessListWidget::formatCellDisplay(const QString &colId, const QVariant &val) {
    if (colId == QLatin1String("pid") || colId == QLatin1String("ppid") ||
        colId == QLatin1String("count") || colId == QLatin1String("threads"))
        return val.toString();

    if (colId == QLatin1String("name") || colId == QLatin1String("user") ||
        colId == QLatin1String("status"))
        return val.toString();

    if (colId == QLatin1String("cpu") || colId == QLatin1String("mem") ||
        colId == QLatin1String("gpu"))
        return QStringLiteral("%1%").arg(val.toDouble(), 0, 'f', 1);

    if (colId == QLatin1String("mem_mb") || colId == QLatin1String("mem_shared") ||
        colId == QLatin1String("mem_swap") || colId == QLatin1String("read_bytes") ||
        colId == QLatin1String("write_bytes"))
        return GraphUtils::formatBytes(val.toLongLong());

    return val.toString();
}

// ── Render table ────────────────────────────────────────────

void ProcessListWidget::renderTable(QTableWidget *table, const QVector<RowData> &data,
                                     const QVector<QString> &visibleCols,
                                     bool maintainSelection) {
    // Save scroll + selection
    int currentScroll = table->verticalScrollBar()->value();
    QString selectedVal;
    int keyColIdx = -1;

    if (maintainSelection) {
        // Use pid for detail, name for grouped
        QString keyId = visibleCols.contains(QStringLiteral("pid"))
            ? QStringLiteral("pid") : QStringLiteral("name");
        keyColIdx = visibleCols.indexOf(keyId);

        auto selected = table->selectedItems();
        if (!selected.isEmpty() && keyColIdx >= 0) {
            int row = selected[0]->row();
            auto *item = table->item(row, keyColIdx);
            if (item) selectedVal = item->data(Qt::DisplayRole).toString();
        }
    }

    table->setUpdatesEnabled(false);
    table->setSortingEnabled(false);
    table->setRowCount(data.size());

    bool foundSelection = false;

    for (int row = 0; row < data.size(); ++row) {
        const auto &rowData = data[row];
        for (int col = 0; col < visibleCols.size(); ++col) {
            const auto &colId = visibleCols[col];
            QVariant val = rowData.value(colId);
            QString display = formatCellDisplay(colId, val);

            auto *item = new SortableTableWidgetItem();
            item->setData(Qt::UserRole, val);
            item->setText(display);

            if (colId == QLatin1String("name"))
                item->setTextAlignment(Qt::AlignLeft | Qt::AlignVCenter);
            else
                item->setTextAlignment(Qt::AlignCenter);

            table->setItem(row, col, item);
        }

        // Restore selection
        if (!selectedVal.isEmpty() && keyColIdx >= 0) {
            auto *keyItem = table->item(row, keyColIdx);
            if (keyItem && keyItem->data(Qt::DisplayRole).toString() == selectedVal) {
                table->selectRow(row);
                foundSelection = true;
            }
        }
    }

    if (!foundSelection)
        table->clearSelection();

    // Auto-size columns once per view mode
    QString modeStr = (table == m_groupTable)
        ? QStringLiteral("grouped") : QStringLiteral("details");
    if (!m_autoSizedViews.contains(modeStr) && !data.isEmpty()) {
        table->resizeColumnsToContents();
        m_autoSizedViews.insert(modeStr);
    }

    // Restore sort indicator (setSortingEnabled(false) clears it)
    updateSortIndicator(table, visibleCols);

    table->setUpdatesEnabled(true);
    table->verticalScrollBar()->setValue(currentScroll);
}

// ── Context menus ───────────────────────────────────────────

void ProcessListWidget::showGroupContextMenu(const QPoint &pos) {
    auto *item = m_groupTable->itemAt(pos);
    if (!item) return;

    int row = item->row();
    int nameIdx = m_visibleGrouped.indexOf(QStringLiteral("name"));
    if (nameIdx < 0) return;
    QString name = m_groupTable->item(row, nameIdx)->text();

    QMenu menu(this);

    auto *detailsAction = menu.addAction(
        QStringLiteral("Show Details for '%1'").arg(name));
    connect(detailsAction, &QAction::triggered,
            this, [this, name]() { switchToDetails(name); });

    // Check if this group contains only real (killable) processes
    bool hasRealPids = false;
    for (const auto &p : m_processData) {
        if (p.name == name && p.pid > 0) { hasRealPids = true; break; }
    }

    if (hasRealPids) {
        menu.addSeparator();

        auto *endAction = menu.addAction(QStringLiteral("End Task (All Instances)"));
        connect(endAction, &QAction::triggered,
                this, [this, name]() { killGroup(name); });

        auto *forceAction = menu.addAction(QStringLiteral("Force Kill (Admin)"));
        connect(forceAction, &QAction::triggered,
                this, [this, name]() { forceKillGroup(name); });
    }

    menu.exec(m_groupTable->viewport()->mapToGlobal(pos));
}

void ProcessListWidget::showDetailContextMenu(const QPoint &pos) {
    auto *item = m_detailTable->itemAt(pos);
    if (!item) return;

    int row = item->row();
    int pid = -1;
    QString name = QStringLiteral("Unknown");

    int pidIdx = m_visibleDetail.indexOf(QStringLiteral("pid"));
    if (pidIdx >= 0)
        pid = m_detailTable->item(row, pidIdx)->data(Qt::UserRole).toInt();

    int nameIdx = m_visibleDetail.indexOf(QStringLiteral("name"));
    if (nameIdx >= 0)
        name = m_detailTable->item(row, nameIdx)->text();

    if (pid <= 0) return;

    QMenu menu(this);

    auto *endAction = menu.addAction(
        QStringLiteral("End Process (%1)").arg(pid));
    connect(endAction, &QAction::triggered,
            this, [this, pid, name]() { killProcess(pid, name); });

    auto *treeAction = menu.addAction(QStringLiteral("End Process Tree"));
    connect(treeAction, &QAction::triggered,
            this, [this, pid, name]() { killProcessTree(pid, name); });

    menu.addSeparator();

    auto *forceAction = menu.addAction(QStringLiteral("Force Kill (Admin)"));
    connect(forceAction, &QAction::triggered,
            this, [this, pid, name]() { forceKillProcess(pid, name); });

    menu.exec(m_detailTable->viewport()->mapToGlobal(pos));
}

// ── Kill operations ─────────────────────────────────────────

void ProcessListWidget::killProcess(int pid, const QString &name) {
    auto reply = QMessageBox::question(this,
        QStringLiteral("Confirm End Process"),
        QStringLiteral("Are you sure you want to end process '%1' (PID: %2)?")
            .arg(name).arg(pid));
    if (reply == QMessageBox::Yes)
        killPid(pid);
}

void ProcessListWidget::killProcessTree(int pid, const QString &name) {
    auto reply = QMessageBox::question(this,
        QStringLiteral("Confirm End Tree"),
        QStringLiteral("Are you sure you want to end the process tree for '%1' (PID: %2)?\n"
                        "This will terminate the process and all its children.")
            .arg(name).arg(pid));
    if (reply != QMessageBox::Yes) return;

    // Build pid → children map from current process data
    QHash<int, QVector<int>> childrenMap;
    for (const auto &p : m_processData)
        childrenMap[p.ppid].append(p.pid);

    // Collect descendants (children-first order for deepest-first kill)
    // Use visited set to prevent infinite recursion from circular PPID references
    QVector<int> allPids;
    QSet<int> visited;
    std::function<void(int)> collect = [&](int parent) {
        if (visited.contains(parent)) return;
        visited.insert(parent);
        for (int child : childrenMap.value(parent)) {
            collect(child);
            allPids.append(child);
        }
    };
    collect(pid);
    allPids.append(pid);

    int killed = 0;
    QVector<int> deniedPids;

    for (int p : allPids) {
        if (p <= 0) continue; // Never signal pid 0 or -1
        if (::kill(p, SIGTERM) == -1) {
            if (errno == ESRCH) continue;       // already dead
            if (errno == EPERM) { deniedPids.append(p); continue; }
            continue;
        }
        // Poll for exit (max 1.5s)
        bool died = false;
        for (int i = 0; i < 15; ++i) {
            QThread::msleep(100);
            if (::kill(p, 0) == -1 && errno == ESRCH) { died = true; break; }
        }
        if (!died)
            ::kill(p, SIGKILL);
        killed++;
    }

    if (!deniedPids.isEmpty()) {
        auto escalate = QMessageBox::question(this,
            QStringLiteral("Access Denied"),
            QStringLiteral("Terminated %1 process(es) in tree, but %2 require admin privileges.\n\n"
                            "Do you want to force kill them as admin?")
                .arg(killed).arg(deniedPids.size()));
        if (escalate == QMessageBox::Yes) {
            if (forceKillPids(deniedPids, true))
                killed += deniedPids.size();
        }
    }

    QMessageBox::information(this, QStringLiteral("Success"),
        QStringLiteral("Process tree for '%1' terminated (%2 processes).")
            .arg(name).arg(killed));
}

void ProcessListWidget::killGroup(const QString &name) {
    auto reply = QMessageBox::question(this,
        QStringLiteral("Confirm End Group"),
        QStringLiteral("Are you sure you want to end ALL processes named '%1'?").arg(name));
    if (reply != QMessageBox::Yes) return;

    int killed = 0;
    QVector<int> deniedPids;

    for (const auto &p : m_processData) {
        if (p.name != name || p.pid <= 0) continue;

        if (::kill(p.pid, SIGTERM) == -1) {
            if (errno == ESRCH) continue;
            if (errno == EPERM) { deniedPids.append(p.pid); continue; }
            continue;
        }
        bool died = false;
        for (int i = 0; i < 15; ++i) {
            QThread::msleep(100);
            if (::kill(p.pid, 0) == -1 && errno == ESRCH) { died = true; break; }
        }
        if (!died)
            ::kill(p.pid, SIGKILL);
        killed++;
    }

    if (!deniedPids.isEmpty()) {
        auto escalate = QMessageBox::question(this,
            QStringLiteral("Access Denied"),
            QStringLiteral("Terminated %1 process(es), but %2 require admin privileges.\n\n"
                            "Do you want to force kill them as admin?")
                .arg(killed).arg(deniedPids.size()));
        if (escalate == QMessageBox::Yes) {
            if (forceKillPids(deniedPids, true))
                killed += deniedPids.size();
        }
    }

    QMessageBox::information(this, QStringLiteral("Success"),
        QStringLiteral("Terminated %1 instances of '%2'.").arg(killed).arg(name));
}

void ProcessListWidget::forceKillProcess(int pid, const QString &name) {
    auto reply = QMessageBox::question(this,
        QStringLiteral("Confirm Force Kill"),
        QStringLiteral("Are you sure you want to force kill '%1' (PID: %2) as admin?\n\n"
                        "This will prompt for your password and send SIGKILL.")
            .arg(name).arg(pid));
    if (reply == QMessageBox::Yes)
        forceKillPids({pid});
}

void ProcessListWidget::forceKillGroup(const QString &name) {
    QVector<int> pids;
    for (const auto &p : m_processData) {
        if (p.name == name && p.pid > 0)
            pids.append(p.pid);
    }

    if (pids.isEmpty()) {
        QMessageBox::warning(this, QStringLiteral("Error"),
            QStringLiteral("No processes named '%1' found.").arg(name));
        return;
    }

    auto reply = QMessageBox::question(this,
        QStringLiteral("Confirm Force Kill Group"),
        QStringLiteral("Are you sure you want to force kill ALL %1 processes named '%2' as admin?\n\n"
                        "This will prompt for your password.")
            .arg(pids.size()).arg(name));
    if (reply == QMessageBox::Yes)
        forceKillPids(pids);
}

bool ProcessListWidget::killPid(int pid, bool silent) {
    if (pid <= 0) return false; // Never signal pid 0 or -1

    if (::kill(pid, SIGTERM) == -1) {
        if (errno == ESRCH) {
            if (!silent)
                QMessageBox::warning(this, QStringLiteral("Error"),
                                     QStringLiteral("Process no longer exists."));
            return false;
        }
        if (errno == EPERM) {
            if (!silent) {
                auto reply = QMessageBox::question(this,
                    QStringLiteral("Access Denied"),
                    QStringLiteral("Process %1 requires administrator privileges to terminate.\n\n"
                                    "Do you want to force kill it as admin?").arg(pid));
                if (reply == QMessageBox::Yes)
                    return forceKillPids({pid}, silent);
            }
            return false;
        }
        if (!silent)
            QMessageBox::critical(this, QStringLiteral("Error"),
                QStringLiteral("Could not terminate process %1.").arg(pid));
        return false;
    }

    // Poll for exit (max 1.5s)
    for (int i = 0; i < 15; ++i) {
        QThread::msleep(100);
        if (::kill(pid, 0) == -1 && errno == ESRCH) {
            if (!silent)
                QMessageBox::information(this, QStringLiteral("Success"),
                    QStringLiteral("Process %1 terminated.").arg(pid));
            return true;
        }
    }

    // Still alive — send SIGKILL
    ::kill(pid, SIGKILL);
    if (!silent)
        QMessageBox::information(this, QStringLiteral("Success"),
            QStringLiteral("Process %1 terminated.").arg(pid));
    return true;
}

bool ProcessListWidget::forceKillPids(const QVector<int> &pids, bool silent) {
    // Filter out invalid PIDs (pid <= 0 would signal process groups)
    QVector<int> safePids;
    for (int p : pids) {
        if (p > 0) safePids.append(p);
    }
    if (safePids.isEmpty()) return false;

    QString pkexecPath = QStandardPaths::findExecutable(QStringLiteral("pkexec"));
    if (pkexecPath.isEmpty()) {
        if (!silent) {
            QStringList pidStrs;
            for (int p : safePids) pidStrs.append(QString::number(p));
            QMessageBox::critical(this, QStringLiteral("Error"),
                QStringLiteral("pkexec is not installed on this system.\n\n"
                                "You can manually kill these processes from a terminal:\n"
                                "  sudo kill -9 %1").arg(pidStrs.join(QLatin1Char(' '))));
        }
        return false;
    }

    QString killBin = QStandardPaths::findExecutable(QStringLiteral("kill"));
    if (killBin.isEmpty()) killBin = QStringLiteral("/usr/bin/kill");

    QStringList args;
    args << killBin << QStringLiteral("-9");
    for (int p : safePids) args << QString::number(p);

    QProcess proc;
    proc.start(pkexecPath, args);
    if (!proc.waitForFinished(60000)) {
        if (!silent)
            QMessageBox::warning(this, QStringLiteral("Timeout"),
                                 QStringLiteral("The authentication dialog timed out."));
        return false;
    }

    int rc = proc.exitCode();
    if (rc == 0) {
        if (!silent)
            QMessageBox::information(this, QStringLiteral("Success"),
                QStringLiteral("Force killed %1 process(es).").arg(safePids.size()));
        return true;
    }
    if (rc == 126) return false; // User dismissed dialog
    if (rc == 127) {
        if (!silent)
            QMessageBox::warning(this, QStringLiteral("Error"),
                                 QStringLiteral("Authentication was not granted."));
        return false;
    }

    QString errOutput = QString::fromUtf8(proc.readAllStandardError()).trimmed();
    if (errOutput.contains(QStringLiteral("No such process"), Qt::CaseInsensitive)) {
        if (!silent)
            QMessageBox::warning(this, QStringLiteral("Error"),
                                 QStringLiteral("Process no longer exists."));
    } else if (!silent) {
        QMessageBox::critical(this, QStringLiteral("Error"),
            QStringLiteral("Failed to kill process(es).\n%1").arg(errOutput));
    }
    return false;
}
