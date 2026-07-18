#pragma once

#include "base.h"
#include "systemmonitor.h"

#include <QVector>
#include <QHash>
#include <QSet>

class QTableWidget;
class QStackedWidget;
class QLineEdit;
class QPushButton;

// ── Column definition ───────────────────────────────────────

struct ColumnDef {
    QString id;
    QString label;
    bool availableGrouped;
    bool availableDetail;
};

// ── ProcessListWidget ───────────────────────────────────────

class ProcessListWidget : public Card {
    Q_OBJECT

public:
    explicit ProcessListWidget(QWidget *parent = nullptr);

    void refreshTheme() override;

public slots:
    void updateData(const ProcessStats &stats);

private slots:
    void onSearchChanged(const QString &text);
    void toggleView();

private:
    enum ViewMode { Grouped, Detail };
    ViewMode m_viewMode = Grouped;

    // Data
    QVector<ProcessInfo> m_processData;
    quint64 m_gpuPollElapsedNs = 0;

    // UI
    QTableWidget *m_groupTable;
    QTableWidget *m_detailTable;
    QStackedWidget *m_stack;
    QLineEdit *m_searchInput;
    QPushButton *m_viewBtn;

    // Columns
    QVector<ColumnDef> m_columnDefs;
    QVector<QString> m_visibleGrouped;
    QVector<QString> m_visibleDetail;

    // Sort
    QString m_sortColId = QStringLiteral("mem");
    bool m_sortDescending = true;
    QSet<QString> m_autoSizedViews;

    // Filter
    QString m_filterText;

    // Table helpers
    void setupTableStyle(QTableWidget *table);
    void updateColumns(ViewMode mode);
    void updateSortIndicator(QTableWidget *table, const QVector<QString> &visibleCols);
    void onHeaderClicked(int logicalIndex, ViewMode mode);
    void showHeaderContextMenu(const QPoint &pos, ViewMode mode);
    void openColumnDialog(ViewMode mode);

    // View
    void switchToDetails(const QString &filterName = {});
    void refreshCurrentView(bool maintainSelection = true);
    void updateGroupedTable(bool maintainSelection = true);
    void updateDetailTable(bool maintainSelection = true);

    // Render
    using RowData = QHash<QString, QVariant>;
    void renderTable(QTableWidget *table, const QVector<RowData> &data,
                     const QVector<QString> &visibleCols, bool maintainSelection);
    static QString formatCellDisplay(const QString &colId, const QVariant &val);
    QVariant getSortKey(const RowData &row) const;

    // Context menus
    void showGroupContextMenu(const QPoint &pos);
    void showDetailContextMenu(const QPoint &pos);

    // Kill operations
    void killProcess(int pid, const QString &name);
    void killProcessTree(int pid, const QString &name);
    void killGroup(const QString &name);
    void forceKillProcess(int pid, const QString &name);
    void forceKillGroup(const QString &name);
    bool killPid(int pid, bool silent = false);
    bool forceKillPids(const QVector<int> &pids, bool silent = false);
};
