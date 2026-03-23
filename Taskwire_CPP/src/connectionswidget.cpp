#include "connectionswidget.h"
#include "base.h"
#include "styles.h"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QComboBox>
#include <QPushButton>
#include <QTableWidget>
#include <QTableWidgetItem>
#include <QHeaderView>
#include <QAbstractItemView>
#include <QMenu>
#include <QMessageBox>
#include <QScrollBar>
#include <QTimer>
#include <QProcess>
#include <QClipboard>
#include <QApplication>
#include <QStandardPaths>
#include <QRegularExpression>

#include <QFile>
#include <QThread>

#include <signal.h>
#include <cerrno>

// Parser contract:
//   ss -tupnaO --no-header
//   Fields (whitespace-separated):
//     [0] proto   — tcp / udp
//     [1] state   — LISTEN, ESTAB, UNCONN, CLOSE-WAIT, TIME-WAIT, ...
//     [2] recv-q
//     [3] send-q
//     [4] local   — address:port (IPv4, [IPv6]:port, or *:*)
//     [5] peer    — address:port
//     [6+] rest   — may contain users:(("name",pid=N,fd=N))

// Regex: extract first process name + pid from users:((...))
const QRegularExpression ConnectionsWidget::s_processRe(
    QStringLiteral("users:\\(\\(\"([^\"]+)\",pid=(\\d+)")
);

// ── Constructor ─────────────────────────────────────────────

ConnectionsWidget::ConnectionsWidget(QWidget *parent)
    : QWidget(parent)
{
    // Check for ss
    m_hasSs = !QStandardPaths::findExecutable(QStringLiteral("ss")).isEmpty();

    auto *mainLayout = new QVBoxLayout(this);
    mainLayout->setContentsMargins(10, 10, 10, 10);
    mainLayout->setSpacing(10);

    // Header
    m_headerLabel = new QLabel(QStringLiteral("Active Connections"));
    m_headerLabel->setStyleSheet(QStringLiteral("font-size: 24px; font-weight: bold; color: %1;")
                              .arg(QColor(ModernTheme::appBackground).lightness() > 128
                                   ? ModernTheme::accentBlue : ModernTheme::accentCyan));
    mainLayout->addWidget(m_headerLabel);

    if (!m_hasSs) {
        auto *msg = new QLabel(QStringLiteral("ss command not found — iproute2 is not installed."));
        msg->setStyleSheet(QStringLiteral("font-size: 16px; color: %1;").arg(ModernTheme::accentRed));
        mainLayout->addWidget(msg);
        mainLayout->addStretch();
        return;
    }

    // ── Toolbar ─────────────────────────────────────────────
    auto *toolbar = new QHBoxLayout();

    // Search
    m_searchInput = new QLineEdit();
    m_searchInput->setPlaceholderText(QStringLiteral("Search connections..."));
    connect(m_searchInput, &QLineEdit::textChanged, this, &ConnectionsWidget::onSearchChanged);
    toolbar->addWidget(m_searchInput, 1);

    // Protocol filter
    m_protoCombo = new QComboBox();
    m_protoCombo->addItems({QStringLiteral("All"), QStringLiteral("TCP"), QStringLiteral("UDP")});
    m_protoCombo->setFixedWidth(90);
    connect(m_protoCombo, &QComboBox::currentTextChanged, this, &ConnectionsWidget::onProtoFilterChanged);
    toolbar->addWidget(m_protoCombo);

    // State filter
    m_stateCombo = new QComboBox();
    m_stateCombo->addItems({
        QStringLiteral("All"), QStringLiteral("LISTEN"), QStringLiteral("ESTAB"),
        QStringLiteral("UNCONN"), QStringLiteral("CLOSE-WAIT"), QStringLiteral("TIME-WAIT")
    });
    m_stateCombo->setFixedWidth(130);
    connect(m_stateCombo, &QComboBox::currentTextChanged, this, &ConnectionsWidget::onStateFilterChanged);
    toolbar->addWidget(m_stateCombo);

    // Refresh button
    m_btnRefresh = new QPushButton(QStringLiteral("Refresh"));
    m_btnRefresh->setCursor(Qt::PointingHandCursor);
    connect(m_btnRefresh, &QPushButton::clicked, this, &ConnectionsWidget::refreshConnections);
    toolbar->addWidget(m_btnRefresh);

    mainLayout->addLayout(toolbar);

    // ── Table ───────────────────────────────────────────────
    m_table = new QTableWidget();
    m_table->setColumnCount(8);
    m_table->setHorizontalHeaderLabels({
        QStringLiteral("Protocol"), QStringLiteral("State"),
        QStringLiteral("Local Address"), QStringLiteral("Port"),
        QStringLiteral("Peer Address"), QStringLiteral("Peer Port"),
        QStringLiteral("Process"), QStringLiteral("PID")
    });
    m_table->verticalHeader()->setVisible(false);
    m_table->setShowGrid(false);
    m_table->setAlternatingRowColors(true);
    m_table->setSelectionBehavior(QAbstractItemView::SelectRows);
    m_table->setSelectionMode(QAbstractItemView::SingleSelection);
    m_table->setSortingEnabled(true);

    // Apply selection style directly to override native Linux theme
    m_table->setStyleSheet(QStringLiteral(
        "QTableView::item:selected:active,"
        "QTableView::item:selected:!active {"
        "    background-color: %1;"
        "    color: white;"
        "}"
    ).arg(ModernTheme::accentBlue));

    // Custom header
    auto *hdr = new ModernHeader(Qt::Horizontal, m_table);
    m_table->setHorizontalHeader(hdr);
    hdr->setSortIndicatorShown(true);

    // Column sizing — Interactive + fixed widths (no ResizeToContents)
    auto *h = m_table->horizontalHeader();
    h->setSectionResizeMode(0, QHeaderView::Interactive);   // Protocol
    h->setSectionResizeMode(1, QHeaderView::Interactive);   // State
    h->setSectionResizeMode(2, QHeaderView::Stretch);       // Local Address
    h->setSectionResizeMode(3, QHeaderView::Interactive);   // Port
    h->setSectionResizeMode(4, QHeaderView::Stretch);       // Peer Address
    h->setSectionResizeMode(5, QHeaderView::Interactive);   // Peer Port
    h->setSectionResizeMode(6, QHeaderView::Interactive);   // Process
    h->setSectionResizeMode(7, QHeaderView::Interactive);   // PID
    h->resizeSection(0, 70);   // Protocol
    h->resizeSection(1, 100);  // State
    h->resizeSection(3, 60);   // Port
    h->resizeSection(5, 70);   // Peer Port
    h->resizeSection(6, 120);  // Process
    h->resizeSection(7, 60);   // PID

    // Context menu
    m_table->setContextMenuPolicy(Qt::CustomContextMenu);
    connect(m_table, &QTableWidget::customContextMenuRequested,
            this, &ConnectionsWidget::showContextMenu);

    mainLayout->addWidget(m_table);

    // ── Status bar ──────────────────────────────────────────
    m_statusLabel = new QLabel(QStringLiteral("Loading connections..."));
    m_statusLabel->setStyleSheet(QStringLiteral("color: %1; font-size: 12px;")
                                     .arg(ModernTheme::textSecondary));
    mainLayout->addWidget(m_statusLabel);

    // ── Auto-refresh timer (5s) ─────────────────────────────
    m_refreshTimer = new QTimer(this);
    connect(m_refreshTimer, &QTimer::timeout, this, &ConnectionsWidget::refreshConnections);
    m_refreshTimer->start(5000);

    // Initial load
    refreshConnections();
}

// ── Theme ───────────────────────────────────────────────────

void ConnectionsWidget::refreshTheme() {
    if (!m_hasSs) return;
    const QString &headerColor = QColor(ModernTheme::appBackground).lightness() > 128
        ? ModernTheme::accentBlue : ModernTheme::accentCyan;
    m_headerLabel->setStyleSheet(QStringLiteral("font-size: 24px; font-weight: bold; color: %1;")
                                     .arg(headerColor));
    m_statusLabel->setStyleSheet(
        QStringLiteral("color: %1; font-size: 12px;").arg(ModernTheme::textSecondary));
    populateTable();
}

// ── Data ────────────────────────────────────────────────────

void ConnectionsWidget::refreshConnections() {
    // Skip if context menu is open (avoid table churn during user interaction)
    if (m_menuOpen) return;

    // Visibility-gated: skip if tab is not visible (bypass on first load —
    // widget isn't visible during tab construction)
    if (!m_firstLoad && !isVisible()) return;
    m_firstLoad = false;

    QProcess proc;
    proc.start(QStringLiteral("ss"),
               {QStringLiteral("-tupnaO"), QStringLiteral("--no-header")});

    if (!proc.waitForFinished(5000)) {
        m_statusLabel->setText(QStringLiteral("ss timed out"));
        return;
    }
    if (proc.exitCode() != 0) {
        m_statusLabel->setText(QStringLiteral("ss error: %1")
                                   .arg(QString::fromUtf8(proc.readAllStandardError()).trimmed()));
        return;
    }

    QString raw = QString::fromUtf8(proc.readAllStandardOutput());

    // Skip-if-unchanged: compare raw output before parsing
    if (raw == m_lastRawOutput) return;
    m_lastRawOutput = raw;

    m_connections = parseOutput(raw);
    populateTable();
    m_statusLabel->setText(QStringLiteral("%1 connections").arg(m_connections.size()));
}

QVector<ConnectionInfo> ConnectionsWidget::parseOutput(const QString &output) const {
    QVector<ConnectionInfo> result;
    const auto lines = output.split(QLatin1Char('\n'), Qt::SkipEmptyParts);

    for (const auto &line : lines) {
        const auto parts = line.split(QRegularExpression(QStringLiteral("\\s+")),
                                       Qt::SkipEmptyParts);
        if (parts.size() < 6) continue;

        ConnectionInfo ci;
        ci.proto = parts[0];        // tcp / udp
        ci.state = parts[1];        // LISTEN, ESTAB, UNCONN, ...
        // [2] = recv-q, [3] = send-q (skipped)
        parseAddress(parts[4], ci.localAddr, ci.localPort);
        parseAddress(parts[5], ci.peerAddr, ci.peerPort);

        // Extract process info from remaining fields (optional)
        if (parts.size() > 6) {
            QString rest;
            for (int i = 6; i < parts.size(); ++i) {
                if (!rest.isEmpty()) rest += QLatin1Char(' ');
                rest += parts[i];
            }
            auto match = s_processRe.match(rest);
            if (match.hasMatch()) {
                ci.process = match.captured(1);
                ci.pid = match.captured(2).toInt();
            }
        }

        result.append(std::move(ci));
    }
    return result;
}

void ConnectionsWidget::parseAddress(const QString &addrPort, QString &addr, QString &port) {
    if (addrPort.startsWith(QLatin1Char('['))) {
        // IPv6: [::1]:80 or [fe80::1%eth0]:443
        int bracketEnd = addrPort.lastIndexOf(QLatin1Char(']'));
        if (bracketEnd != -1 && bracketEnd + 1 < addrPort.size()
            && addrPort[bracketEnd + 1] == QLatin1Char(':')) {
            addr = addrPort.mid(1, bracketEnd - 1);
            port = addrPort.mid(bracketEnd + 2);
            return;
        }
        addr = (bracketEnd != -1) ? addrPort.mid(1, bracketEnd - 1) : addrPort;
        port = QStringLiteral("*");
        return;
    }
    // IPv4 or wildcard: 0.0.0.0:80, *:*
    int idx = addrPort.lastIndexOf(QLatin1Char(':'));
    if (idx != -1) {
        addr = addrPort.left(idx);
        port = addrPort.mid(idx + 1);
    } else {
        addr = addrPort;
        port = QStringLiteral("*");
    }
}

// ── Table population ────────────────────────────────────────

void ConnectionsWidget::populateTable() {
    // Save selection by composite key (endpoint tuple + pid for uniqueness)
    QString selectedKey;
    auto selRows = m_table->selectionModel()->selectedRows();
    if (!selRows.isEmpty()) {
        auto *item = m_table->item(selRows[0].row(), 0);
        if (item)
            selectedKey = item->data(Qt::UserRole).toString();
    }
    int scrollPos = m_table->verticalScrollBar()->value();

    // Filter
    QVector<const ConnectionInfo *> filtered;
    filtered.reserve(m_connections.size());

    const QString ft = m_filterText.toLower();

    for (const auto &c : m_connections) {
        // Protocol filter
        if (m_protoFilter != QStringLiteral("All")) {
            if (c.proto.compare(m_protoFilter, Qt::CaseInsensitive) != 0)
                continue;
        }
        // State filter
        if (m_stateFilter != QStringLiteral("All")) {
            if (c.state != m_stateFilter)
                continue;
        }
        // Text search (any field)
        if (!ft.isEmpty()) {
            bool found = c.proto.toLower().contains(ft)
                      || c.state.toLower().contains(ft)
                      || c.localAddr.toLower().contains(ft)
                      || c.localPort.toLower().contains(ft)
                      || c.peerAddr.toLower().contains(ft)
                      || c.peerPort.toLower().contains(ft)
                      || c.process.toLower().contains(ft)
                      || QString::number(c.pid).contains(ft);
            if (!found) continue;
        }
        filtered.append(&c);
    }

    m_table->setUpdatesEnabled(false);
    m_table->setSortingEnabled(false);
    m_table->setRowCount(filtered.size());

    QTableWidgetItem *targetItem = nullptr;
    for (int row = 0; row < filtered.size(); ++row) {
        const auto &c = *filtered[row];

        // Composite key: endpoint tuple + pid (for mDNS/multicast disambiguation)
        QString key = QStringLiteral("%1:%2:%3:%4:%5:%6")
                          .arg(c.proto, c.localAddr, c.localPort,
                               c.peerAddr, c.peerPort, QString::number(c.pid));

        // Protocol (color-coded)
        auto *protoItem = new QTableWidgetItem(c.proto.toUpper());
        protoItem->setData(Qt::UserRole, key);
        protoItem->setFlags(protoItem->flags() & ~Qt::ItemIsEditable);
        protoItem->setForeground(QColor(c.proto == QStringLiteral("tcp")
                                            ? ModernTheme::accentCyan
                                            : ModernTheme::accentOrange));
        m_table->setItem(row, 0, protoItem);

        // State (color-coded)
        auto *stateItem = new QTableWidgetItem(c.state);
        stateItem->setFlags(stateItem->flags() & ~Qt::ItemIsEditable);
        stateItem->setForeground(QColor(stateColor(c.state)));
        m_table->setItem(row, 1, stateItem);

        // Local Address
        auto *laItem = new QTableWidgetItem(c.localAddr);
        laItem->setFlags(laItem->flags() & ~Qt::ItemIsEditable);
        m_table->setItem(row, 2, laItem);

        // Local Port — numeric sort via SortableTableWidgetItem
        auto *lpItem = new SortableTableWidgetItem(c.localPort);
        lpItem->setData(Qt::UserRole, c.localPort.toInt());
        lpItem->setFlags(lpItem->flags() & ~Qt::ItemIsEditable);
        m_table->setItem(row, 3, lpItem);

        // Peer Address
        auto *paItem = new QTableWidgetItem(c.peerAddr);
        paItem->setFlags(paItem->flags() & ~Qt::ItemIsEditable);
        m_table->setItem(row, 4, paItem);

        // Peer Port — numeric sort
        auto *ppItem = new SortableTableWidgetItem(c.peerPort);
        ppItem->setData(Qt::UserRole, c.peerPort.toInt());
        ppItem->setFlags(ppItem->flags() & ~Qt::ItemIsEditable);
        m_table->setItem(row, 5, ppItem);

        // Process
        auto *procItem = new QTableWidgetItem(c.process);
        procItem->setFlags(procItem->flags() & ~Qt::ItemIsEditable);
        m_table->setItem(row, 6, procItem);

        // PID — numeric sort
        auto *pidItem = new SortableTableWidgetItem(
            c.pid > 0 ? QString::number(c.pid) : QString());
        if (c.pid > 0)
            pidItem->setData(Qt::UserRole, c.pid);
        pidItem->setFlags(pidItem->flags() & ~Qt::ItemIsEditable);
        m_table->setItem(row, 7, pidItem);

        if (key == selectedKey)
            targetItem = protoItem;  // save pointer, not row index
    }

    m_table->setSortingEnabled(true);
    m_table->setUpdatesEnabled(true);

    // Restore selection by pointer (survives sort re-ordering)
    if (targetItem)
        m_table->selectRow(targetItem->row());
    m_table->verticalScrollBar()->setValue(scrollPos);
}

QString ConnectionsWidget::stateColor(const QString &state) const {
    if (state == QStringLiteral("LISTEN"))
        return ModernTheme::accentGreen;
    if (state == QStringLiteral("ESTAB"))
        return ModernTheme::accentCyan;
    if (state == QStringLiteral("CLOSE-WAIT") || state == QStringLiteral("TIME-WAIT")
        || state == QStringLiteral("FIN-WAIT-1") || state == QStringLiteral("FIN-WAIT-2"))
        return ModernTheme::accentOrange;
    if (state == QStringLiteral("UNCONN"))
        return ModernTheme::textSecondary;
    return ModernTheme::textPrimary;
}

// ── Filter slots ────────────────────────────────────────────

void ConnectionsWidget::onSearchChanged(const QString &text) {
    m_filterText = text;
    populateTable();
}

void ConnectionsWidget::onProtoFilterChanged(const QString &text) {
    m_protoFilter = text;
    populateTable();
}

void ConnectionsWidget::onStateFilterChanged(const QString &text) {
    m_stateFilter = text;
    populateTable();
}

// ── Context menu ────────────────────────────────────────────

void ConnectionsWidget::showContextMenu(const QPoint &pos) {
    // Target the right-clicked row
    auto *clickedItem = m_table->itemAt(pos);
    if (!clickedItem) return;
    m_table->selectRow(clickedItem->row());
    int row = clickedItem->row();

    auto *pidItem = m_table->item(row, 7);
    QString pidText = pidItem ? pidItem->text() : QString();

    QMenu menu(this);

    auto *copyAct = menu.addAction(QStringLiteral("Copy Connection Info"));
    connect(copyAct, &QAction::triggered, this, [this, row]() { copyRow(row); });

    if (!pidText.isEmpty()) {
        menu.addSeparator();
        auto *killAct = menu.addAction(QStringLiteral("Kill Process (PID %1)").arg(pidText));
        connect(killAct, &QAction::triggered, this, [this, pidText]() {
            killProcess(pidText.toInt());
        });
    }

    m_menuOpen = true;
    menu.exec(m_table->viewport()->mapToGlobal(pos));
    m_menuOpen = false;
}

void ConnectionsWidget::copyRow(int row) {
    QStringList parts;
    for (int col = 0; col < m_table->columnCount(); ++col) {
        auto *item = m_table->item(row, col);
        if (item)
            parts.append(item->text());
    }
    QApplication::clipboard()->setText(parts.join(QStringLiteral("  ")));
    m_statusLabel->setText(QStringLiteral("Copied to clipboard"));
}

// ── Kill process ────────────────────────────────────────────

void ConnectionsWidget::killProcess(int pid) {
    if (pid <= 0) return;

    // Check if process exists
    if (::kill(pid, 0) != 0 && errno == ESRCH) {
        QMessageBox::information(this, QStringLiteral("Process Gone"),
                                 QStringLiteral("PID %1 no longer exists.").arg(pid));
        return;
    }

    // Read process name from /proc/pid/comm
    QString name = QStringLiteral("PID %1").arg(pid);
    {
        QFile f(QStringLiteral("/proc/%1/comm").arg(pid));
        if (f.open(QIODevice::ReadOnly))
            name = QString::fromUtf8(f.readAll()).trimmed();
    }

    auto reply = QMessageBox::question(
        this, QStringLiteral("Kill Process"),
        QStringLiteral("Kill %1 (PID %2)?\nThis will close all connections owned by this process.")
            .arg(name).arg(pid),
        QMessageBox::Yes | QMessageBox::No, QMessageBox::No);
    if (reply != QMessageBox::Yes) return;

    // SIGTERM → poll → SIGKILL → pkexec escalation
    if (::kill(pid, SIGTERM) != 0) {
        if (errno == EPERM) {
            escalatedKill(pid, name);
            refreshConnections();
            return;
        }
        m_statusLabel->setText(QStringLiteral("Failed to signal PID %1").arg(pid));
        return;
    }

    // Poll for death (500ms)
    for (int i = 0; i < 10; ++i) {
        QThread::msleep(50);
        QApplication::processEvents();
        if (::kill(pid, 0) != 0 && errno == ESRCH) {
            m_statusLabel->setText(QStringLiteral("Terminated %1 (PID %2)").arg(name).arg(pid));
            refreshConnections();
            return;
        }
    }

    // SIGKILL
    if (::kill(pid, SIGKILL) != 0) {
        if (errno == EPERM) {
            escalatedKill(pid, name);
            refreshConnections();
            return;
        }
        m_statusLabel->setText(QStringLiteral("Failed to kill PID %1").arg(pid));
        refreshConnections();
        return;
    }

    // Verify death after SIGKILL (200ms)
    for (int i = 0; i < 4; ++i) {
        QThread::msleep(50);
        if (::kill(pid, 0) != 0 && errno == ESRCH) {
            m_statusLabel->setText(QStringLiteral("Killed %1 (PID %2)").arg(name).arg(pid));
            refreshConnections();
            return;
        }
    }
    m_statusLabel->setText(QStringLiteral("Sent SIGKILL to %1 (PID %2) — may still be exiting")
                               .arg(name).arg(pid));
    refreshConnections();
}

void ConnectionsWidget::escalatedKill(int pid, const QString &name) {
    QString killBin = QStandardPaths::findExecutable(QStringLiteral("kill"));
    if (killBin.isEmpty()) {
        QMessageBox::critical(this, QStringLiteral("Error"),
                              QStringLiteral("kill command not found."));
        return;
    }
    if (QStandardPaths::findExecutable(QStringLiteral("pkexec")).isEmpty()) {
        QMessageBox::critical(this, QStringLiteral("Error"),
                              QStringLiteral("pkexec not found — cannot escalate privileges."));
        return;
    }

    QProcess proc;
    proc.start(QStringLiteral("pkexec"),
               {killBin, QStringLiteral("-9"), QString::number(pid)});
    if (!proc.waitForFinished(60000)) {
        QMessageBox::warning(this, QStringLiteral("Timeout"),
                             QStringLiteral("pkexec timed out."));
        return;
    }

    if (proc.exitCode() == 0) {
        m_statusLabel->setText(QStringLiteral("Admin-killed %1 (PID %2)").arg(name).arg(pid));
    } else if (proc.exitCode() == 126 || proc.exitCode() == 127) {
        m_statusLabel->setText(QStringLiteral("Authentication cancelled or denied."));
    } else {
        QMessageBox::warning(this, QStringLiteral("Kill Failed"),
                             QString::fromUtf8(proc.readAllStandardError()).trimmed());
    }
}
