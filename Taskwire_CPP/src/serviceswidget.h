#pragma once

#include <QWidget>
#include <QVector>
#include <QString>
#include <QProcess>

class QTableWidget;
class QLineEdit;
class QComboBox;
class QPushButton;
class QLabel;
class QTimer;

// ── ServiceInfo ─────────────────────────────────────────────

struct ServiceInfo {
    QString unit;           // e.g. "NetworkManager.service"
    QString name;           // e.g. "NetworkManager" (display)
    QString loadState;      // loaded, not-found, masked, ...
    QString activeState;    // active, inactive, failed, activating, ...
    QString subState;       // running, dead, exited, ...
    QString description;    // human-readable description
    QString unitFileState;  // enabled, disabled, static, masked, indirect, ...
};

// ── ServicesWidget ──────────────────────────────────────────

class ServicesWidget : public QWidget {
    Q_OBJECT

public:
    explicit ServicesWidget(QWidget *parent = nullptr);

    void refreshTheme();

private slots:
    void onSearchChanged(const QString &text);
    void onStatusFilterChanged(const QString &text);
    void onHeaderClicked(int col);

private:
    // Data
    QVector<ServiceInfo> m_services;
    bool m_hasSystemctl = false;
    QString m_systemctlPath;

    // Filter / sort
    QString m_filterText;
    QString m_statusFilter = QStringLiteral("All");
    int m_sortCol = 0;
    Qt::SortOrder m_sortOrder = Qt::AscendingOrder;

    // Refresh guard
    bool m_refreshing = false;
    bool m_refreshPending = false;
    bool m_actionRunning = false;

    // UI
    QLineEdit *m_searchInput = nullptr;
    QComboBox *m_statusCombo = nullptr;
    QPushButton *m_btnStart = nullptr;
    QPushButton *m_btnStop = nullptr;
    QPushButton *m_btnRestart = nullptr;
    QPushButton *m_btnRefresh = nullptr;
    QTableWidget *m_table = nullptr;
    QLabel *m_headerLabel = nullptr;
    QLabel *m_statusLabel = nullptr;
    QTimer *m_refreshTimer = nullptr;

    // Async refresh state
    QProcess *m_listUnitsProc = nullptr;
    QProcess *m_isEnabledProc = nullptr;
    QVector<ServiceInfo> m_pendingServices;

    // Data
    void refreshServices();
    void onListUnitsFinished(int exitCode, QProcess::ExitStatus exitStatus);
    void onIsEnabledFinished(int exitCode, QProcess::ExitStatus exitStatus);
    void onRefreshError(QProcess::ProcessError error);
    void populateTable();
    QString statusColor(const QString &activeState) const;

    // Actions
    void doAction(const QString &action);
    void onActionFinished(int exitCode, QProcess::ExitStatus exitStatus,
                          const QString &action, const QString &unit);
    void showContextMenu(const QPoint &pos);
    void showServiceStatus();
    void updateButtonState();

    // Selection
    QString selectedUnit() const;
    const ServiceInfo *selectedServiceInfo() const;
};
