#include "journalwidget.h"
#include "styles.h"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QComboBox>
#include <QPushButton>
#include <QPlainTextEdit>
#include <QScrollBar>
#include <QTimer>
#include <QProcess>
#include <QTextCursor>
#include <QTextBlock>
#include <QTextCharFormat>
#include <QMessageBox>
#include <QFileDialog>
#include <QApplication>
#include <QStandardPaths>
#include <QDateTime>
#include <QFile>
#include <QRegularExpression>

// Command contract:
//   journalctl --follow --no-pager --output=short-precise --no-hostname -n 200
//              [-b BOOT] [-p PRIORITY] [-u UNIT1 -u UNIT2 ...]
// Output: one line per log entry, severity detected by keyword heuristic.

static constexpr int MAX_LINES = 5000;
static constexpr int MAX_FLUSH_BATCH = 500;
static constexpr int MAX_PAUSE_BUFFER = 10000;

// Priority labels and journalctl values
struct PriorityEntry {
    const char *label;
    const char *value;  // nullptr = "All"
};
static const PriorityEntry s_priorities[] = {
    {"All",        nullptr},
    {"Emergency",  "0"},
    {"Alert",      "1"},
    {"Critical",   "2"},
    {"Error",      "3"},
    {"Warning",    "4"},
    {"Notice",     "5"},
    {"Info",       "6"},
    {"Debug",      "7"},
};

// ── Constructor ─────────────────────────────────────────────

JournalLogWidget::JournalLogWidget(QWidget *parent)
    : QWidget(parent)
{
    m_hasJournalctl = !QStandardPaths::findExecutable(
        QStringLiteral("journalctl")).isEmpty();

    auto *mainLayout = new QVBoxLayout(this);
    mainLayout->setContentsMargins(10, 10, 10, 10);
    mainLayout->setSpacing(10);

    // Header
    m_headerLabel = new QLabel(QStringLiteral("System Logs"));
    m_headerLabel->setStyleSheet(QStringLiteral("font-size: 24px; font-weight: bold; color: %1;")
                              .arg(QColor(ModernTheme::appBackground).lightness() > 128
                                   ? ModernTheme::accentBlue : ModernTheme::accentCyan));
    mainLayout->addWidget(m_headerLabel);

    if (!m_hasJournalctl) {
        auto *msg = new QLabel(QStringLiteral(
            "journalctl not found — systemd journal is not available on this system."));
        msg->setStyleSheet(QStringLiteral("font-size: 16px; color: %1;")
                               .arg(ModernTheme::accentRed));
        mainLayout->addWidget(msg);
        mainLayout->addStretch();
        return;
    }

    // ── Toolbar Row 1: Filters ──────────────────────────────
    auto *toolbar1 = new QHBoxLayout();

    auto *sevLabel = new QLabel(QStringLiteral("Priority:"));
    sevLabel->setStyleSheet(QStringLiteral("color: %1; font-weight: bold;")
                                .arg(ModernTheme::textSecondary));
    toolbar1->addWidget(sevLabel);

    m_severityCombo = new QComboBox();
    for (const auto &p : s_priorities)
        m_severityCombo->addItem(QString::fromUtf8(p.label));
    m_severityCombo->setFixedWidth(160);
    connect(m_severityCombo, &QComboBox::currentIndexChanged,
            this, &JournalLogWidget::onFilterChanged);
    toolbar1->addWidget(m_severityCombo);

    auto *unitLabel = new QLabel(QStringLiteral("Unit:"));
    unitLabel->setStyleSheet(QStringLiteral("color: %1; font-weight: bold;")
                                 .arg(ModernTheme::textSecondary));
    toolbar1->addWidget(unitLabel);

    m_unitInput = new QLineEdit();
    m_unitInput->setPlaceholderText(QStringLiteral("e.g. docker.service, sshd..."));
    m_unitInput->setFixedWidth(220);
    connect(m_unitInput, &QLineEdit::editingFinished,
            this, &JournalLogWidget::onFilterChanged);
    toolbar1->addWidget(m_unitInput);

    auto *bootLabel = new QLabel(QStringLiteral("Boot:"));
    bootLabel->setStyleSheet(QStringLiteral("color: %1; font-weight: bold;")
                                 .arg(ModernTheme::textSecondary));
    toolbar1->addWidget(bootLabel);

    m_bootCombo = new QComboBox();
    m_bootCombo->setFixedWidth(180);
    connect(m_bootCombo, &QComboBox::currentIndexChanged,
            this, &JournalLogWidget::onFilterChanged);
    toolbar1->addWidget(m_bootCombo);

    toolbar1->addStretch();
    mainLayout->addLayout(toolbar1);

    // ── Toolbar Row 2: Search + Controls ────────────────────
    auto *toolbar2 = new QHBoxLayout();

    m_searchInput = new QLineEdit();
    m_searchInput->setPlaceholderText(QStringLiteral("Search logs..."));
    connect(m_searchInput, &QLineEdit::textChanged,
            this, &JournalLogWidget::onSearchChanged);
    toolbar2->addWidget(m_searchInput, 1);

    auto mkBtn = [&](const QString &text) -> QPushButton* {
        auto *btn = new QPushButton(text);
        btn->setCursor(Qt::PointingHandCursor);
        toolbar2->addWidget(btn);
        return btn;
    };

    m_btnPause = mkBtn(QStringLiteral("Pause"));
    m_btnPause->setCheckable(true);
    connect(m_btnPause, &QPushButton::clicked, this, &JournalLogWidget::togglePause);

    m_btnWrap = mkBtn(QStringLiteral("Wrap"));
    m_btnWrap->setCheckable(true);
    m_btnWrap->setChecked(true);
    connect(m_btnWrap, &QPushButton::clicked, this, &JournalLogWidget::toggleWrap);

    m_btnClear = mkBtn(QStringLiteral("Clear"));
    connect(m_btnClear, &QPushButton::clicked, this, &JournalLogWidget::clearLogs);

    m_btnBottom = mkBtn(QStringLiteral("Bottom"));
    connect(m_btnBottom, &QPushButton::clicked, this, &JournalLogWidget::jumpToBottom);

    m_btnExport = mkBtn(QStringLiteral("Export"));
    m_btnExport->setToolTip(QStringLiteral("Save current logs to a file"));
    connect(m_btnExport, &QPushButton::clicked, this, &JournalLogWidget::exportLogs);

    mainLayout->addLayout(toolbar2);

    // ── Log output ──────────────────────────────────────────
    m_logView = new QPlainTextEdit();
    m_logView->setReadOnly(true);
    m_logView->setUndoRedoEnabled(false);
    m_logView->setMaximumBlockCount(MAX_LINES);
    m_logView->setLineWrapMode(QPlainTextEdit::WidgetWidth);
    applyLogStyle();

    connect(m_logView->verticalScrollBar(), &QScrollBar::valueChanged,
            this, &JournalLogWidget::onScrollChanged);

    mainLayout->addWidget(m_logView);

    // ── Status bar ──────────────────────────────────────────
    auto *statusRow = new QHBoxLayout();

    m_statusLabel = new QLabel(QStringLiteral("Starting..."));
    m_statusLabel->setStyleSheet(QStringLiteral("color: %1; font-size: 12px;")
                                     .arg(ModernTheme::textSecondary));
    statusRow->addWidget(m_statusLabel);

    m_lineCountLabel = new QLabel(QStringLiteral("0 lines"));
    m_lineCountLabel->setStyleSheet(QStringLiteral("color: %1; font-size: 12px;")
                                        .arg(ModernTheme::textSecondary));
    m_lineCountLabel->setAlignment(Qt::AlignRight);
    statusRow->addWidget(m_lineCountLabel);

    mainLayout->addLayout(statusRow);

    // ── Timers ──────────────────────────────────────────────
    m_flushTimer = new QTimer(this);
    connect(m_flushTimer, &QTimer::timeout, this, &JournalLogWidget::flushBuffer);
    m_flushTimer->start(100);

    m_searchTimer = new QTimer(this);
    m_searchTimer->setSingleShot(true);
    connect(m_searchTimer, &QTimer::timeout, this, &JournalLogWidget::applySearch);

    // Build severity formats
    buildFormats();

    // Load boots and start streaming
    loadBoots();
    startJournalctl();
}

JournalLogWidget::~JournalLogWidget() {
    stop();
}

// ── Theme ───────────────────────────────────────────────────

void JournalLogWidget::applyLogStyle() {
    m_logView->setStyleSheet(
        QStringLiteral("QPlainTextEdit {"
                       "background-color: %1;"
                       "color: %2;"
                       "font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;"
                       "font-size: 12px;"
                       "border: 1px solid %3;"
                       "border-radius: 5px;"
                       "padding: 5px;"
                       "}")
            .arg(ModernTheme::appBackground,
                 ModernTheme::textPrimary,
                 ModernTheme::borderColor));
}

void JournalLogWidget::buildFormats() {
    m_fmtError.setForeground(QColor(ModernTheme::accentRed));
    m_fmtWarning.setForeground(QColor(ModernTheme::accentOrange));
    m_fmtNotice.setForeground(QColor(ModernTheme::accentCyan));
    m_fmtInfo.setForeground(QColor(ModernTheme::accentGreen));
    m_fmtDebug.setForeground(QColor(ModernTheme::textSecondary));
    m_fmtDefault.setForeground(QColor(ModernTheme::textPrimary));
}

void JournalLogWidget::refreshTheme() {
    if (!m_hasJournalctl) return;
    const QString &headerColor = QColor(ModernTheme::appBackground).lightness() > 128
        ? ModernTheme::accentBlue : ModernTheme::accentCyan;
    m_headerLabel->setStyleSheet(QStringLiteral("font-size: 24px; font-weight: bold; color: %1;")
                                     .arg(headerColor));
    applyLogStyle();
    m_statusLabel->setStyleSheet(
        QStringLiteral("color: %1; font-size: 12px;").arg(ModernTheme::textSecondary));
    m_lineCountLabel->setStyleSheet(
        QStringLiteral("color: %1; font-size: 12px;").arg(ModernTheme::textSecondary));
    buildFormats();
    reapplyThemeToDocument();
    if (!m_currentSearch.isEmpty())
        highlightSearch(m_currentSearch);
}

// ── Boot management ─────────────────────────────────────────

void JournalLogWidget::loadBoots() {
    m_bootCombo->blockSignals(true);
    m_bootCombo->clear();
    m_bootCombo->addItem(QStringLiteral("Current Boot"), QStringLiteral("0"));

    QProcess proc;
    proc.start(QStringLiteral("journalctl"),
               {QStringLiteral("--list-boots"), QStringLiteral("--no-pager")});
    if (proc.waitForFinished(10000) && proc.exitCode() == 0) {
        const QString out = QString::fromUtf8(proc.readAllStandardOutput());
        const auto lines = out.split(QLatin1Char('\n'), Qt::SkipEmptyParts);
        for (const auto &line : lines) {
            const auto parts = line.split(QRegularExpression(QStringLiteral("\\s+")),
                                           Qt::SkipEmptyParts);
            if (parts.size() >= 2 && parts[0] != QStringLiteral("0")) {
                QString shortId = parts[1].left(12);
                m_bootCombo->addItem(
                    QStringLiteral("Boot %1 (%2...)").arg(parts[0], shortId),
                    parts[0]);
            }
        }
    }
    m_bootCombo->blockSignals(false);
}

// ── Process lifecycle ───────────────────────────────────────

QStringList JournalLogWidget::buildCommand() const {
    QStringList args = {
        QStringLiteral("--follow"),
        QStringLiteral("--no-pager"),
        QStringLiteral("--output=short-precise"),
        QStringLiteral("--no-hostname"),
        QStringLiteral("-n"), QStringLiteral("200"),
    };

    // Boot
    QVariant bootData = m_bootCombo->currentData();
    if (bootData.isValid()) {
        args << QStringLiteral("-b") << bootData.toString();
    }

    // Priority
    int sevIdx = m_severityCombo->currentIndex();
    if (sevIdx > 0 && s_priorities[sevIdx].value) {
        args << QStringLiteral("-p") << QString::fromUtf8(s_priorities[sevIdx].value);
    }

    // Units (comma-separated)
    QString unitText = m_unitInput->text().trimmed();
    if (!unitText.isEmpty()) {
        const auto units = unitText.split(QLatin1Char(','), Qt::SkipEmptyParts);
        for (const auto &u : units) {
            QString trimmed = u.trimmed();
            if (!trimmed.isEmpty())
                args << QStringLiteral("-u") << trimmed;
        }
    }

    return args;
}

void JournalLogWidget::startJournalctl() {
    stopJournalctl();
    m_partialBytes.clear();
    m_pauseDropped = 0;

    m_processGen++;
    quint64 gen = m_processGen;

    m_process = new QProcess(this);
    m_process->setProcessChannelMode(QProcess::SeparateChannels);

    connect(m_process, &QProcess::readyReadStandardOutput, this, [this, gen]() {
        if (m_processGen != gen) return;  // stale signal
        onStdoutReady();
    });
    connect(m_process, &QProcess::readyReadStandardError, this, [this, gen]() {
        if (m_processGen != gen) return;
        onStderrReady();
    });
    connect(m_process, &QProcess::errorOccurred, this, [this, gen](QProcess::ProcessError err) {
        if (m_processGen != gen) return;
        onProcessError(err);
    });
    connect(m_process, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
            this, [this, gen](int code, QProcess::ExitStatus status) {
        if (m_processGen != gen) return;
        onProcessFinished(code, status);
    });

    m_process->start(QStringLiteral("journalctl"), buildCommand());

    m_statusLabel->setText(QStringLiteral("Streaming..."));
    m_paused = false;
    m_btnPause->setChecked(false);
    m_btnPause->setText(QStringLiteral("Pause"));
}

void JournalLogWidget::stopJournalctl() {
    if (!m_process) return;

    // Disconnect all signals to prevent stale handlers
    m_process->disconnect();

    if (m_process->state() != QProcess::NotRunning) {
        m_process->kill();
        m_process->waitForFinished(3000);
    }
    m_process->deleteLater();
    m_process = nullptr;
}

// ── QProcess signal handlers ────────────────────────────────

void JournalLogWidget::onStdoutReady() {
    if (!m_process) return;

    // UTF-8-safe: accumulate raw bytes, split on \n, decode only complete lines
    m_partialBytes.append(m_process->readAllStandardOutput());

    int nlIdx;
    while ((nlIdx = m_partialBytes.indexOf('\n')) != -1) {
        QByteArray lineBytes = m_partialBytes.left(nlIdx);
        m_partialBytes.remove(0, nlIdx + 1);

        QString line = QString::fromUtf8(lineBytes);
        m_lineBuffer.append(line);
    }

    // Cap partial bytes buffer (defense against malformed stream with no newlines)
    if (m_partialBytes.size() > 65536) {
        // Force-decode what we have and reset
        m_lineBuffer.append(QString::fromUtf8(m_partialBytes));
        m_partialBytes.clear();
    }

    // Cap line buffer — prevents unbounded growth during bursts (paused or not).
    // During normal streaming the flush timer drains ~5000 lines/sec, so this
    // only triggers under extreme sustained bursts.
    if (m_lineBuffer.size() > MAX_PAUSE_BUFFER) {
        int excess = m_lineBuffer.size() - MAX_PAUSE_BUFFER;
        if (m_paused) m_pauseDropped += excess;
        m_lineBuffer.erase(m_lineBuffer.begin(), m_lineBuffer.begin() + excess);
    }
}

void JournalLogWidget::onStderrReady() {
    if (!m_process) return;
    QString err = QString::fromUtf8(m_process->readAllStandardError()).trimmed();
    if (!err.isEmpty())
        m_statusLabel->setText(QStringLiteral("journalctl: %1").arg(err));
}

void JournalLogWidget::onProcessError(QProcess::ProcessError error) {
    QString msg;
    switch (error) {
    case QProcess::FailedToStart:
        msg = QStringLiteral("Failed to start journalctl — you may need to be in the 'systemd-journal' group");
        break;
    case QProcess::Crashed:
        msg = QStringLiteral("journalctl process crashed");
        break;
    case QProcess::Timedout:
        msg = QStringLiteral("journalctl timed out");
        break;
    default:
        msg = QStringLiteral("journalctl error (%1)").arg(error);
        break;
    }
    m_statusLabel->setText(msg);
}

void JournalLogWidget::onProcessFinished(int exitCode, QProcess::ExitStatus /*exitStatus*/) {
    // Any finished() that reaches this slot is unexpected — intentional stops
    // disconnect signals before killing, so they never fire this handler.
    if (exitCode == 0)
        m_statusLabel->setText(QStringLiteral("journalctl exited unexpectedly"));
    else
        m_statusLabel->setText(QStringLiteral("journalctl exited with code %1").arg(exitCode));
}

// ── Buffer flush & display ──────────────────────────────────

void JournalLogWidget::flushBuffer() {
    if (m_lineBuffer.isEmpty() || m_paused)
        return;

    // Cap lines per flush to avoid UI stall during bursts
    int count = qMin(m_lineBuffer.size(), MAX_FLUSH_BATCH);
    QStringList batch = m_lineBuffer.mid(0, count);
    m_lineBuffer = m_lineBuffer.mid(count);

    QTextCursor cursor = m_logView->textCursor();
    cursor.movePosition(QTextCursor::End);

    // Save cursor position before insertion for incremental search highlighting.
    // Block number arithmetic breaks when setMaximumBlockCount prunes old blocks,
    // but a QTextCursor tracks its position through document edits automatically.
    QTextCursor searchStart(cursor);

    cursor.beginEditBlock();

    for (const auto &line : batch) {
        const auto &fmt = detectFormat(line);
        cursor.insertText(line + QLatin1Char('\n'), fmt);
    }

    cursor.endEditBlock();

    updateLineCount();

    // Highlight newly appended lines if search is active
    if (!m_currentSearch.isEmpty()) {
        highlightInRange(m_currentSearch, searchStart);
    }

    // Auto-scroll — use ensureCursorVisible() instead of scrollbar setValue()
    // because word-wrap mode calculates layouts asynchronously, making
    // scrollBar()->maximum() stale immediately after insertText.
    if (m_autoScroll) {
        QTextCursor endCursor = m_logView->textCursor();
        endCursor.movePosition(QTextCursor::End);
        m_logView->setTextCursor(endCursor);
        m_logView->ensureCursorVisible();
    }
}

const QTextCharFormat &JournalLogWidget::detectFormat(const QString &line) const {
    // Keyword heuristic for severity detection (v1 approach)
    // Matches patterns like " err:", " error:", " crit:", " warn:", etc.
    QString lower = line.toLower();

    if (lower.contains(QStringLiteral(" emerg"))
        || lower.contains(QStringLiteral(" crit:"))
        || lower.contains(QStringLiteral(" critical:"))
        || lower.contains(QStringLiteral(" crit["))
        || lower.contains(QStringLiteral(" err:"))
        || lower.contains(QStringLiteral(" error:"))
        || lower.contains(QStringLiteral(" error["))
        || lower.contains(QStringLiteral(" err[")))
        return m_fmtError;

    if (lower.contains(QStringLiteral("kernel:"))
        && (lower.contains(QStringLiteral("error"))
            || lower.contains(QStringLiteral("fail"))
            || lower.contains(QStringLiteral("panic"))
            || lower.contains(QStringLiteral("oops"))))
        return m_fmtError;

    if (lower.contains(QStringLiteral(" warn:"))
        || lower.contains(QStringLiteral(" warning:"))
        || lower.contains(QStringLiteral(" warn["))
        || lower.contains(QStringLiteral(" warning[")))
        return m_fmtWarning;

    if (lower.contains(QStringLiteral("kernel:")) && lower.contains(QStringLiteral("warn")))
        return m_fmtWarning;

    if (lower.contains(QStringLiteral(" notice:"))
        || lower.contains(QStringLiteral(" notice[")))
        return m_fmtNotice;

    if (lower.contains(QStringLiteral(" debug:"))
        || lower.contains(QStringLiteral(" debug[")))
        return m_fmtDebug;

    return m_fmtDefault;
}

void JournalLogWidget::reapplyThemeToDocument() {
    auto *doc = m_logView->document();
    if (!doc || doc->blockCount() <= 1) return;

    QTextCursor cursor(doc);
    cursor.beginEditBlock();

    for (QTextBlock block = doc->begin(); block.isValid(); block = block.next()) {
        const QString line = block.text();
        if (line.isEmpty()) continue;

        QTextCursor blockCursor(block);
        blockCursor.movePosition(QTextCursor::StartOfBlock);
        blockCursor.movePosition(QTextCursor::EndOfBlock, QTextCursor::KeepAnchor);
        blockCursor.setCharFormat(detectFormat(line));
    }

    cursor.endEditBlock();
}

void JournalLogWidget::updateLineCount() {
    int count = m_logView->document()->blockCount();
    m_lineCountLabel->setText(QStringLiteral("%1 lines").arg(count));
}

// ── Scroll management ───────────────────────────────────────

void JournalLogWidget::onScrollChanged(int value) {
    auto *sb = m_logView->verticalScrollBar();
    m_autoScroll = (value >= sb->maximum() - 50);
}

void JournalLogWidget::jumpToBottom() {
    m_autoScroll = true;
    m_logView->verticalScrollBar()->setValue(
        m_logView->verticalScrollBar()->maximum());
}

// ── Controls ────────────────────────────────────────────────

void JournalLogWidget::togglePause(bool checked) {
    m_paused = checked;
    if (checked) {
        m_btnPause->setText(QStringLiteral("Resume"));
        m_statusLabel->setText(QStringLiteral("Paused"));
    } else {
        m_btnPause->setText(QStringLiteral("Pause"));
        // Show drop count before clearing — flushBuffer() can't report it
        // because we need to set m_paused=false first to allow flushing
        if (m_pauseDropped > 0) {
            m_statusLabel->setText(
                QStringLiteral("Streaming... (%1 lines dropped during pause)")
                    .arg(m_pauseDropped));
        } else {
            m_statusLabel->setText(QStringLiteral("Streaming..."));
        }
        m_pauseDropped = 0;
        // Flush accumulated lines on resume
        flushBuffer();
    }
}

void JournalLogWidget::toggleWrap(bool checked) {
    m_logView->setLineWrapMode(checked ? QPlainTextEdit::WidgetWidth
                                       : QPlainTextEdit::NoWrap);
}

void JournalLogWidget::clearLogs() {
    m_logView->clear();
    m_logView->setExtraSelections({});
    m_lineBuffer.clear();
    m_partialBytes.clear();
    m_pauseDropped = 0;
    m_lineCountLabel->setText(QStringLiteral("0 lines"));
}

void JournalLogWidget::onFilterChanged() {
    clearLogs();
    startJournalctl();
}

// ── Search ──────────────────────────────────────────────────

void JournalLogWidget::onSearchChanged(const QString &text) {
    m_currentSearch = text;
    m_searchTimer->start(200);
}

void JournalLogWidget::applySearch() {
    clearHighlights();
    if (!m_currentSearch.isEmpty())
        highlightSearch(m_currentSearch);
}

void JournalLogWidget::highlightSearch(const QString &text) {
    if (text.isEmpty()) {
        m_logView->setExtraSelections({});
        return;
    }

    QList<QTextEdit::ExtraSelection> selections;
    auto *doc = m_logView->document();
    QColor hlColor(ModernTheme::accentYellow);
    hlColor.setAlpha(80);
    QColor textColor(ModernTheme::textPrimary);

    QTextCursor cursor = doc->find(text);
    int seen = 0;
    while (!cursor.isNull() && seen < 5000) {
        QTextEdit::ExtraSelection sel;
        sel.cursor = cursor;
        sel.format.setBackground(hlColor);
        sel.format.setForeground(textColor);
        selections.append(sel);
        cursor = doc->find(text, cursor);
        seen++;
    }
    m_logView->setExtraSelections(selections);
}

void JournalLogWidget::highlightInRange(const QString &text, const QTextCursor &from) {
    // Incrementally highlight only newly appended text (from saved cursor to end)
    if (text.isEmpty()) return;

    auto *doc = m_logView->document();

    QColor hlColor(ModernTheme::accentYellow);
    hlColor.setAlpha(80);
    QColor textColor(ModernTheme::textPrimary);

    // Prune ghost selections — collapsed cursors from blocks pruned by maxBlockCount
    auto existing = m_logView->extraSelections();
    QList<QTextEdit::ExtraSelection> valid;
    valid.reserve(existing.size());
    for (const auto &sel : existing) {
        if (sel.cursor.hasSelection())
            valid.append(sel);
    }

    QTextCursor cursor = doc->find(text, from);
    int added = 0;
    while (!cursor.isNull() && added < 1000) {
        QTextEdit::ExtraSelection sel;
        sel.cursor = cursor;
        sel.format.setBackground(hlColor);
        sel.format.setForeground(textColor);
        valid.append(sel);
        cursor = doc->find(text, cursor);
        added++;
    }

    // Cap total selections
    if (valid.size() > 5000)
        valid = valid.mid(valid.size() - 5000);

    m_logView->setExtraSelections(valid);
}

void JournalLogWidget::clearHighlights() {
    m_logView->setExtraSelections({});
}

// ── Export ───────────────────────────────────────────────────

void JournalLogWidget::exportLogs() {
    QString content = m_logView->toPlainText();
    if (content.trimmed().isEmpty()) {
        QMessageBox::warning(this, QStringLiteral("Export Logs"),
                             QStringLiteral("No logs to export — the log view is empty."));
        return;
    }

    QString defaultName = QDateTime::currentDateTime().toString(
        QStringLiteral("'taskwire_logs_'yyyyMMdd_HHmm'.log'"));

    QString filepath = QFileDialog::getSaveFileName(
        this, QStringLiteral("Export Logs"), defaultName,
        QStringLiteral("Log Files (*.log);;Text Files (*.txt);;All Files (*)"));
    if (filepath.isEmpty()) return;

    QFile f(filepath);
    if (!f.open(QIODevice::WriteOnly | QIODevice::Text)) {
        QMessageBox::critical(this, QStringLiteral("Export Logs"),
                              QStringLiteral("Failed to save logs:\n%1").arg(f.errorString()));
        return;
    }
    QByteArray data = content.toUtf8();
    qint64 written = f.write(data);
    f.close();

    if (written != data.size()) {
        QMessageBox::critical(this, QStringLiteral("Export Logs"),
                              QStringLiteral("Failed to write all data (disk full?)\n%1").arg(filepath));
        return;
    }

    QMessageBox::information(this, QStringLiteral("Export Logs"),
                             QStringLiteral("Logs saved to:\n%1").arg(filepath));
}

// ── Cleanup ─────────────────────────────────────────────────

void JournalLogWidget::stop() {
    if (m_flushTimer) m_flushTimer->stop();
    if (m_searchTimer) m_searchTimer->stop();
    stopJournalctl();
}
