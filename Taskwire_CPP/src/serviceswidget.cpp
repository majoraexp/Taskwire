#include "serviceswidget.h"
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
#include <QDialog>
#include <QTextEdit>
#include <QScrollBar>
#include <QTimer>
#include <QProcess>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QStandardPaths>

// ── Constructor ─────────────────────────────────────────────

ServicesWidget::ServicesWidget(QWidget *parent)
    : QWidget(parent)
{
    m_systemctlPath = QStandardPaths::findExecutable(QStringLiteral("systemctl"));
    m_hasSystemctl = !m_systemctlPath.isEmpty();

    auto *mainLayout = new QVBoxLayout(this);
    mainLayout->setContentsMargins(10, 10, 10, 10);
    mainLayout->setSpacing(10);

    // Header
    m_headerLabel = new QLabel(QStringLiteral("Systemd Services"));
    m_headerLabel->setStyleSheet(QStringLiteral("font-size: 24px; font-weight: bold; color: %1;")
                              .arg(QColor(ModernTheme::appBackground).lightness() > 128
                                   ? ModernTheme::accentBlue : ModernTheme::accentCyan));
    mainLayout->addWidget(m_headerLabel);

    if (!m_hasSystemctl) {
        auto *msg = new QLabel(QStringLiteral("systemctl not found — systemd is not available on this system."));
        msg->setStyleSheet(QStringLiteral("font-size: 16px; color: %1;").arg(ModernTheme::accentRed));
        mainLayout->addWidget(msg);
        mainLayout->addStretch();
        return;
    }

    // ── Toolbar ─────────────────────────────────────────────
    auto *toolbar = new QHBoxLayout();

    m_searchInput = new QLineEdit(this);
    m_searchInput->setPlaceholderText(QStringLiteral("Search services..."));
    connect(m_searchInput, &QLineEdit::textChanged, this, &ServicesWidget::onSearchChanged);
    toolbar->addWidget(m_searchInput, 1);

    m_statusCombo = new QComboBox(this);
    m_statusCombo->addItems({QStringLiteral("All"), QStringLiteral("Active"),
                             QStringLiteral("Inactive"), QStringLiteral("Failed")});
    m_statusCombo->setFixedWidth(120);
    connect(m_statusCombo, &QComboBox::currentTextChanged,
            this, &ServicesWidget::onStatusFilterChanged);
    toolbar->addWidget(m_statusCombo);

    m_btnStart   = new QPushButton(QStringLiteral("Start"), this);
    m_btnStop    = new QPushButton(QStringLiteral("Stop"), this);
    m_btnRestart = new QPushButton(QStringLiteral("Restart"), this);
    m_btnRefresh = new QPushButton(QStringLiteral("Refresh"), this);

    for (auto *btn : {m_btnStart, m_btnStop, m_btnRestart, m_btnRefresh}) {
        btn->setCursor(Qt::PointingHandCursor);
        toolbar->addWidget(btn);
    }

    connect(m_btnStart,   &QPushButton::clicked, this, [this]() { doAction(QStringLiteral("start")); });
    connect(m_btnStop,    &QPushButton::clicked, this, [this]() { doAction(QStringLiteral("stop")); });
    connect(m_btnRestart, &QPushButton::clicked, this, [this]() { doAction(QStringLiteral("restart")); });
    connect(m_btnRefresh, &QPushButton::clicked, this, &ServicesWidget::refreshServices);

    m_btnStart->setEnabled(false);
    m_btnStop->setEnabled(false);
    m_btnRestart->setEnabled(false);

    mainLayout->addLayout(toolbar);

    // ── Table ───────────────────────────────────────────────
    m_table = new QTableWidget(this);
    m_table->setColumnCount(5);
    m_table->setHorizontalHeaderLabels({QStringLiteral("Service"),
                                        QStringLiteral("Description"),
                                        QStringLiteral("Active"),
                                        QStringLiteral("Sub-State"),
                                        QStringLiteral("Enabled")});
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

    auto *hdr = new ModernHeader(Qt::Horizontal, m_table);
    m_table->setHorizontalHeader(hdr);
    hdr->setSortIndicatorShown(true);
    connect(hdr, &QHeaderView::sectionClicked, this, &ServicesWidget::onHeaderClicked);

    auto *h = m_table->horizontalHeader();
    h->setSectionResizeMode(0, QHeaderView::Interactive);
    h->setSectionResizeMode(1, QHeaderView::Stretch);
    h->setSectionResizeMode(2, QHeaderView::Interactive);
    h->setSectionResizeMode(3, QHeaderView::Interactive);
    h->setSectionResizeMode(4, QHeaderView::Interactive);
    h->resizeSection(2, 80);   // Active
    h->resizeSection(3, 90);   // Sub-State
    h->resizeSection(4, 80);   // Enabled

    m_table->setContextMenuPolicy(Qt::CustomContextMenu);
    connect(m_table, &QTableWidget::customContextMenuRequested,
            this, &ServicesWidget::showContextMenu);
    connect(m_table, &QTableWidget::doubleClicked,
            this, &ServicesWidget::showServiceStatus);
    connect(m_table, &QTableWidget::itemSelectionChanged,
            this, &ServicesWidget::updateButtonState);

    mainLayout->addWidget(m_table);

    // ── Status bar ──────────────────────────────────────────
    m_statusLabel = new QLabel(QStringLiteral("Loading services..."), this);
    m_statusLabel->setStyleSheet(
        QStringLiteral("color: %1; font-size: 12px;").arg(ModernTheme::textSecondary));
    mainLayout->addWidget(m_statusLabel);

    // ── Auto-refresh timer (5s) ─────────────────────────────
    m_refreshTimer = new QTimer(this);
    connect(m_refreshTimer, &QTimer::timeout, this, &ServicesWidget::refreshServices);
    m_refreshTimer->start(30000);

    // Initial load
    refreshServices();
}

// ── Theme ───────────────────────────────────────────────────

void ServicesWidget::refreshTheme() {
    if (!m_hasSystemctl) return;
    const QString &headerColor = QColor(ModernTheme::appBackground).lightness() > 128
        ? ModernTheme::accentBlue : ModernTheme::accentCyan;
    m_headerLabel->setStyleSheet(QStringLiteral("font-size: 24px; font-weight: bold; color: %1;")
                                     .arg(headerColor));
    m_statusLabel->setStyleSheet(
        QStringLiteral("color: %1; font-size: 12px;").arg(ModernTheme::textSecondary));
    populateTable();
}

// ── Async data refresh ──────────────────────────────────────
// Matches Python: list-units --all (loaded services only), then batch is-enabled.

void ServicesWidget::refreshServices() {
    if (m_refreshing) {
        m_refreshPending = true;
        return;
    }
    m_refreshing = true;

    // Step 1: fetch loaded services
    m_listUnitsProc = new QProcess(this);
    connect(m_listUnitsProc, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
            this, &ServicesWidget::onListUnitsFinished);
    connect(m_listUnitsProc, &QProcess::errorOccurred,
            this, &ServicesWidget::onRefreshError);

    m_listUnitsProc->start(m_systemctlPath,
                           {QStringLiteral("list-units"),
                            QStringLiteral("--type=service"),
                            QStringLiteral("--all"),
                            QStringLiteral("--no-pager"),
                            QStringLiteral("--output=json")});
}

void ServicesWidget::onListUnitsFinished(int /*exitCode*/, QProcess::ExitStatus exitStatus) {
    auto *proc = qobject_cast<QProcess *>(sender());
    if (!proc || proc != m_listUnitsProc) return;

    QVector<ServiceInfo> services;
    bool ok = false;

    if (exitStatus == QProcess::NormalExit && proc) {
        QJsonParseError err;
        auto doc = QJsonDocument::fromJson(proc->readAllStandardOutput(), &err);

        if (err.error == QJsonParseError::NoError && doc.isArray()) {
            const auto arr = doc.array();
            services.reserve(arr.size());

            for (const auto &val : arr) {
                auto obj = val.toObject();
                ServiceInfo info;
                info.unit = obj.value(QStringLiteral("unit")).toString();

                info.name = info.unit;
                if (info.name.endsWith(QStringLiteral(".service")))
                    info.name.chop(8);

                info.loadState   = obj.value(QStringLiteral("load")).toString();
                info.activeState = obj.value(QStringLiteral("active")).toString();
                info.subState    = obj.value(QStringLiteral("sub")).toString();
                info.description = obj.value(QStringLiteral("description")).toString();
                services.append(info);
            }
            ok = true;
        }
    }

    if (proc) proc->deleteLater();
    m_listUnitsProc = nullptr;

    if (!ok) {
        m_refreshing = false;
        m_statusLabel->setText(QStringLiteral("Failed to parse service list"));
        if (m_refreshPending) { m_refreshPending = false; refreshServices(); }
        return;
    }

    // Step 2: batch is-enabled for all units in one call (matches Python)
    QStringList unitNames;
    unitNames.reserve(services.size());
    for (const auto &svc : services)
        unitNames.append(svc.unit);

    m_pendingServices = std::move(services);

    m_isEnabledProc = new QProcess(this);
    connect(m_isEnabledProc, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
            this, &ServicesWidget::onIsEnabledFinished);
    connect(m_isEnabledProc, &QProcess::errorOccurred,
            this, &ServicesWidget::onRefreshError);

    QStringList args = {QStringLiteral("is-enabled"), QStringLiteral("--no-pager")};
    args.append(unitNames);
    m_isEnabledProc->start(m_systemctlPath, args);
}

void ServicesWidget::onIsEnabledFinished(int /*exitCode*/, QProcess::ExitStatus /*exitStatus*/) {
    auto *proc = qobject_cast<QProcess *>(sender());
    if (!proc || proc != m_isEnabledProc) return;

    // is-enabled returns one line per unit (enabled/disabled/static/masked/etc.)
    // Non-zero exit code is normal (any disabled unit causes exit 1)
    QStringList enabledLines = QString::fromUtf8(proc->readAllStandardOutput())
                                   .trimmed().split(QLatin1Char('\n'));

    for (int i = 0; i < m_pendingServices.size() && i < enabledLines.size(); ++i)
        m_pendingServices[i].unitFileState = enabledLines[i].trimmed();

    if (proc) proc->deleteLater();
    m_isEnabledProc = nullptr;
    m_refreshing = false;

    // Skip rebuild if data hasn't changed
    bool changed = (m_pendingServices.size() != m_services.size());
    if (!changed) {
        for (int i = 0; i < m_pendingServices.size(); ++i) {
            const auto &a = m_pendingServices[i];
            const auto &b = m_services[i];
            if (a.unit != b.unit || a.activeState != b.activeState ||
                a.subState != b.subState || a.unitFileState != b.unitFileState ||
                a.description != b.description) {
                changed = true;
                break;
            }
        }
    }

    if (changed) {
        m_services = std::move(m_pendingServices);
        populateTable();
    }
    m_pendingServices.clear();

    m_statusLabel->setText(QStringLiteral("%1 services loaded").arg(m_services.size()));

    if (m_refreshPending) {
        m_refreshPending = false;
        refreshServices();
    }
}

void ServicesWidget::onRefreshError(QProcess::ProcessError /*error*/) {
    auto *proc = qobject_cast<QProcess *>(sender());
    if (proc) {
        proc->deleteLater();
        if (proc == m_listUnitsProc) m_listUnitsProc = nullptr;
        if (proc == m_isEnabledProc) m_isEnabledProc = nullptr;
    }
    m_pendingServices.clear();
    m_refreshing = false;
    m_statusLabel->setText(QStringLiteral("Failed to run systemctl"));

    if (m_refreshPending) {
        m_refreshPending = false;
        refreshServices();
    }
}

// ── Table population ────────────────────────────────────────

void ServicesWidget::populateTable() {
    // Save selection by unit name
    QString selectedUnitName;
    auto selRows = m_table->selectionModel()->selectedRows();
    if (!selRows.isEmpty()) {
        auto *item = m_table->item(selRows.first().row(), 0);
        if (item)
            selectedUnitName = item->data(Qt::UserRole).toString();
    }

    int scrollPos = m_table->verticalScrollBar()->value();

    // Filter
    QVector<const ServiceInfo *> filtered;
    for (const auto &svc : m_services) {
        // Status filter
        if (m_statusFilter != QStringLiteral("All")) {
            auto sf = m_statusFilter.toLower();
            if (svc.activeState != sf)
                continue;
        }
        // Text filter
        if (!m_filterText.isEmpty()) {
            auto ft = m_filterText.toLower();
            if (!svc.name.toLower().contains(ft) &&
                !svc.description.toLower().contains(ft))
                continue;
        }
        filtered.append(&svc);
    }

    m_table->setUpdatesEnabled(false);
    m_table->setSortingEnabled(false);
    m_table->setRowCount(filtered.size());

    QTableWidgetItem *targetItem = nullptr;
    for (int row = 0; row < filtered.size(); ++row) {
        const auto &svc = *filtered[row];

        // Service name (stores full unit in UserRole)
        auto *nameItem = new QTableWidgetItem(svc.name);
        nameItem->setData(Qt::UserRole, svc.unit);
        nameItem->setFlags(nameItem->flags() & ~Qt::ItemIsEditable);
        m_table->setItem(row, 0, nameItem);

        // Description
        auto *descItem = new QTableWidgetItem(svc.description);
        descItem->setFlags(descItem->flags() & ~Qt::ItemIsEditable);
        m_table->setItem(row, 1, descItem);

        // Active state (color-coded)
        auto *activeItem = new QTableWidgetItem(svc.activeState);
        activeItem->setFlags(activeItem->flags() & ~Qt::ItemIsEditable);
        activeItem->setForeground(QColor(statusColor(svc.activeState)));
        m_table->setItem(row, 2, activeItem);

        // Sub-state
        auto *subItem = new QTableWidgetItem(svc.subState);
        subItem->setFlags(subItem->flags() & ~Qt::ItemIsEditable);
        m_table->setItem(row, 3, subItem);

        // Unit file state (color-coded)
        auto *enItem = new QTableWidgetItem(svc.unitFileState);
        enItem->setFlags(enItem->flags() & ~Qt::ItemIsEditable);
        if (svc.unitFileState == QStringLiteral("enabled"))
            enItem->setForeground(QColor(ModernTheme::accentGreen));
        else if (svc.unitFileState == QStringLiteral("disabled") ||
                 svc.unitFileState == QStringLiteral("masked"))
            enItem->setForeground(QColor(ModernTheme::accentRed));
        else
            enItem->setForeground(QColor(ModernTheme::textSecondary));
        m_table->setItem(row, 4, enItem);

        if (svc.unit == selectedUnitName)
            targetItem = nameItem;
    }

    m_table->setSortingEnabled(true);
    // Explicitly reapply our tracked sort state + sync header indicator
    m_table->sortItems(m_sortCol, m_sortOrder);
    m_table->horizontalHeader()->setSortIndicator(m_sortCol, m_sortOrder);
    m_table->setUpdatesEnabled(true);

    // Restore selection by item pointer (row index may have changed after sort)
    if (targetItem)
        m_table->selectRow(targetItem->row());

    m_table->verticalScrollBar()->setValue(scrollPos);
}

QString ServicesWidget::statusColor(const QString &activeState) const {
    if (activeState == QStringLiteral("active"))
        return ModernTheme::accentGreen;
    if (activeState == QStringLiteral("failed"))
        return ModernTheme::accentRed;
    if (activeState == QStringLiteral("activating") ||
        activeState == QStringLiteral("deactivating") ||
        activeState == QStringLiteral("reloading"))
        return ModernTheme::accentOrange;
    return ModernTheme::textSecondary;
}

// ── Selection helpers ───────────────────────────────────────

QString ServicesWidget::selectedUnit() const {
    auto sel = m_table->selectionModel()->selectedRows();
    if (sel.isEmpty()) return {};
    auto *item = m_table->item(sel.first().row(), 0);
    return item ? item->data(Qt::UserRole).toString() : QString();
}

const ServiceInfo *ServicesWidget::selectedServiceInfo() const {
    auto unit = selectedUnit();
    if (unit.isEmpty()) return nullptr;
    for (const auto &svc : m_services) {
        if (svc.unit == unit)
            return &svc;
    }
    return nullptr;
}

// ── Button state ────────────────────────────────────────────

void ServicesWidget::updateButtonState() {
    // Don't re-enable buttons while an action is in progress
    if (m_actionRunning) {
        m_btnStart->setEnabled(false);
        m_btnStop->setEnabled(false);
        m_btnRestart->setEnabled(false);
        return;
    }

    auto *svc = selectedServiceInfo();
    if (!svc) {
        m_btnStart->setEnabled(false);
        m_btnStop->setEnabled(false);
        m_btnRestart->setEnabled(false);
        return;
    }

    bool isRunning = (svc->activeState == QStringLiteral("active") ||
                      svc->activeState == QStringLiteral("activating") ||
                      svc->activeState == QStringLiteral("reloading") ||
                      svc->activeState == QStringLiteral("deactivating"));
    bool isStopped = (svc->activeState == QStringLiteral("inactive") ||
                      svc->activeState == QStringLiteral("failed") ||
                      svc->activeState.isEmpty());

    m_btnStart->setEnabled(isStopped);
    m_btnStop->setEnabled(isRunning);
    m_btnRestart->setEnabled(isRunning);
}

// ── Filter / Sort ───────────────────────────────────────────

void ServicesWidget::onSearchChanged(const QString &text) {
    m_filterText = text;
    populateTable();
}

void ServicesWidget::onStatusFilterChanged(const QString &text) {
    m_statusFilter = text;
    populateTable();
}

void ServicesWidget::onHeaderClicked(int col) {
    if (col == m_sortCol) {
        m_sortOrder = (m_sortOrder == Qt::AscendingOrder)
                          ? Qt::DescendingOrder
                          : Qt::AscendingOrder;
    } else {
        m_sortCol = col;
        m_sortOrder = Qt::AscendingOrder;
    }
    m_table->sortItems(m_sortCol, m_sortOrder);
}

// ── Actions ─────────────────────────────────────────────────

void ServicesWidget::doAction(const QString &action) {
    if (m_actionRunning) return;

    auto unit = selectedUnit();
    if (unit.isEmpty()) {
        QMessageBox::information(this, QStringLiteral("No Selection"),
                                 QStringLiteral("Select a service first."));
        return;
    }

    // Confirmation for stop/restart
    if (action == QStringLiteral("stop") || action == QStringLiteral("restart")) {
        auto reply = QMessageBox::question(
            this,
            QStringLiteral("Confirm %1").arg(action.at(0).toUpper() + action.mid(1)),
            QStringLiteral("Are you sure you want to %1 %2?").arg(action, unit),
            QMessageBox::Yes | QMessageBox::No,
            QMessageBox::No);
        if (reply != QMessageBox::Yes)
            return;
    }

    auto pkexecPath = QStandardPaths::findExecutable(QStringLiteral("pkexec"));
    if (pkexecPath.isEmpty()) {
        QMessageBox::critical(this, QStringLiteral("Error"),
                              QStringLiteral("pkexec not found. Cannot perform privileged actions."));
        return;
    }

    m_actionRunning = true;
    m_statusLabel->setText(QStringLiteral("Running %1 on %2...").arg(action, unit));
    m_btnStart->setEnabled(false);
    m_btnStop->setEnabled(false);
    m_btnRestart->setEnabled(false);

    auto *proc = new QProcess(this);
    connect(proc, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
            this, [this, proc, action, unit](int exitCode, QProcess::ExitStatus exitStatus) {
                onActionFinished(exitCode, exitStatus, action, unit);
                proc->deleteLater();
            });
    connect(proc, &QProcess::errorOccurred, this,
            [this, proc](QProcess::ProcessError) {
                m_actionRunning = false;
                m_statusLabel->setText(QStringLiteral("Failed to run pkexec"));
                updateButtonState();
                proc->deleteLater();
            });

    proc->start(pkexecPath, {m_systemctlPath, action, unit});
}

void ServicesWidget::onActionFinished(int exitCode, QProcess::ExitStatus exitStatus,
                                      const QString &action, const QString &unit) {
    m_actionRunning = false;
    if (exitStatus == QProcess::NormalExit && exitCode == 0) {
        m_statusLabel->setText(QStringLiteral("Successfully ran '%1' on %2").arg(action, unit));
        refreshServices();
    } else if (exitCode == 126 || exitCode == 127) {
        m_statusLabel->setText(QStringLiteral("Authentication cancelled or denied."));
        updateButtonState();
    } else {
        QMessageBox::warning(
            this, QStringLiteral("Action Failed"),
            QStringLiteral("systemctl %1 %2 failed (exit code %3).")
                .arg(action, unit, QString::number(exitCode)));
        updateButtonState();
    }
}

// ── Context menu ────────────────────────────────────────────

void ServicesWidget::showContextMenu(const QPoint &pos) {
    // Select the row under the cursor — right-click doesn't auto-select in Qt
    auto *clickedItem = m_table->itemAt(pos);
    if (!clickedItem) return;
    m_table->selectRow(clickedItem->row());

    auto *svc = selectedServiceInfo();
    if (!svc) return;

    bool isRunning = (svc->activeState == QStringLiteral("active") ||
                      svc->activeState == QStringLiteral("activating") ||
                      svc->activeState == QStringLiteral("reloading") ||
                      svc->activeState == QStringLiteral("deactivating"));
    bool isStopped = (svc->activeState == QStringLiteral("inactive") ||
                      svc->activeState == QStringLiteral("failed") ||
                      svc->activeState.isEmpty());
    bool isEnabled = (svc->unitFileState == QStringLiteral("enabled"));
    bool isMasked  = (svc->unitFileState == QStringLiteral("masked"));

    QMenu menu(this);

    auto *actStart = menu.addAction(QStringLiteral("Start"),
                                    [this]() { doAction(QStringLiteral("start")); });
    actStart->setEnabled(isStopped);

    auto *actStop = menu.addAction(QStringLiteral("Stop"),
                                   [this]() { doAction(QStringLiteral("stop")); });
    actStop->setEnabled(isRunning);

    auto *actRestart = menu.addAction(QStringLiteral("Restart"),
                                      [this]() { doAction(QStringLiteral("restart")); });
    actRestart->setEnabled(isRunning);

    menu.addSeparator();

    auto *actEnable = menu.addAction(QStringLiteral("Enable"),
                                     [this]() { doAction(QStringLiteral("enable")); });
    actEnable->setEnabled(!isEnabled && !isMasked);

    auto *actDisable = menu.addAction(QStringLiteral("Disable"),
                                      [this]() { doAction(QStringLiteral("disable")); });
    actDisable->setEnabled(isEnabled);

    menu.addSeparator();
    menu.addAction(QStringLiteral("View Status..."),
                   this, &ServicesWidget::showServiceStatus);

    menu.exec(m_table->viewport()->mapToGlobal(pos));
}

// ── Status dialog ───────────────────────────────────────────

void ServicesWidget::showServiceStatus() {
    auto unit = selectedUnit();
    if (unit.isEmpty()) return;

    // Run synchronous here — status is a quick read-only operation
    // triggered by explicit user action (double-click / menu), not auto-refresh
    QProcess proc;
    proc.start(m_systemctlPath,
               {QStringLiteral("status"), unit,
                QStringLiteral("--no-pager"), QStringLiteral("-l")});
    proc.waitForFinished(10000);

    QString output;
    if (proc.exitStatus() == QProcess::NormalExit) {
        output = QString::fromUtf8(proc.readAllStandardOutput());
        auto errOutput = QString::fromUtf8(proc.readAllStandardError());
        if (output.isEmpty())
            output = errOutput.isEmpty() ? QStringLiteral("No output") : errOutput;
    } else {
        output = QStringLiteral("Failed to run systemctl status");
    }

    auto *dlg = new QDialog(this);
    dlg->setWindowTitle(QStringLiteral("Status: %1").arg(unit));
    dlg->resize(700, 500);
    dlg->setAttribute(Qt::WA_DeleteOnClose);

    auto *layout = new QVBoxLayout(dlg);

    auto *text = new QTextEdit(dlg);
    text->setReadOnly(true);
    text->setPlainText(output);
    text->setStyleSheet(
        QStringLiteral("QTextEdit {"
                       "  background-color: %1;"
                       "  color: %2;"
                       "  font-family: monospace;"
                       "  border: 1px solid %3;"
                       "}")
            .arg(ModernTheme::appBackground,
                 ModernTheme::textPrimary,
                 ModernTheme::borderColor));
    layout->addWidget(text);

    auto *closeBtn = new QPushButton(QStringLiteral("Close"), dlg);
    connect(closeBtn, &QPushButton::clicked, dlg, &QDialog::accept);
    layout->addWidget(closeBtn);

    dlg->exec();
}
