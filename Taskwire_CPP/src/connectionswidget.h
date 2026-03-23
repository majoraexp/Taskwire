#pragma once

#include <QWidget>
#include <QVector>
#include <QString>
#include <QRegularExpression>

class QTableWidget;
class QLineEdit;
class QComboBox;
class QPushButton;
class QLabel;
class QTimer;

// ── ConnectionInfo ──────────────────────────────────────────

struct ConnectionInfo {
    QString proto;      // tcp / udp
    QString state;      // LISTEN, ESTAB, UNCONN, CLOSE-WAIT, ...
    QString localAddr;
    QString localPort;
    QString peerAddr;
    QString peerPort;
    QString process;
    int     pid = 0;    // 0 = no process info
};

// ── ConnectionsWidget ───────────────────────────────────────

class ConnectionsWidget : public QWidget {
    Q_OBJECT

public:
    explicit ConnectionsWidget(QWidget *parent = nullptr);

    void refreshTheme();

private slots:
    void onSearchChanged(const QString &text);
    void onProtoFilterChanged(const QString &text);
    void onStateFilterChanged(const QString &text);

private:
    // Data
    QVector<ConnectionInfo> m_connections;
    QString m_lastRawOutput;   // raw ss stdout for skip-if-unchanged
    bool m_hasSs = false;
    bool m_menuOpen = false;
    bool m_firstLoad = true;   // bypass visibility check on first refresh

    // Filters
    QString m_filterText;
    QString m_protoFilter = QStringLiteral("All");
    QString m_stateFilter = QStringLiteral("All");

    // UI
    QLineEdit  *m_searchInput = nullptr;
    QComboBox  *m_protoCombo  = nullptr;
    QComboBox  *m_stateCombo  = nullptr;
    QPushButton *m_btnRefresh = nullptr;
    QTableWidget *m_table     = nullptr;
    QLabel     *m_headerLabel = nullptr;
    QLabel     *m_statusLabel = nullptr;
    QTimer     *m_refreshTimer = nullptr;

    // Regex for process extraction
    static const QRegularExpression s_processRe;

    // Data
    void refreshConnections();
    QVector<ConnectionInfo> parseOutput(const QString &output) const;
    static void parseAddress(const QString &addrPort, QString &addr, QString &port);
    void populateTable();
    QString stateColor(const QString &state) const;

    // Context menu & actions
    void showContextMenu(const QPoint &pos);
    void copyRow(int row);
    void killProcess(int pid);
    void escalatedKill(int pid, const QString &name);
};
