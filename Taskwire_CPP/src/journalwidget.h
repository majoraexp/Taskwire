#pragma once

#include <QWidget>
#include <QString>
#include <QStringList>
#include <QByteArray>
#include <QProcess>
#include <QTextCharFormat>

class QTextCursor;
class QPlainTextEdit;
class QLineEdit;
class QComboBox;
class QPushButton;
class QLabel;
class QTimer;

// ── JournalLogWidget ────────────────────────────────────────

class JournalLogWidget : public QWidget {
    Q_OBJECT

public:
    explicit JournalLogWidget(QWidget *parent = nullptr);
    ~JournalLogWidget() override;

    void refreshTheme();
    void stop();   // safe to call multiple times; stops timers/process

private slots:
    void onStdoutReady();
    void onStderrReady();
    void onProcessError(QProcess::ProcessError error);
    void onProcessFinished(int exitCode, QProcess::ExitStatus exitStatus);
    void onFilterChanged();
    void onSearchChanged(const QString &text);
    void onScrollChanged(int value);

private:
    bool m_hasJournalctl = false;

    // Process
    QProcess *m_process = nullptr;
    quint64   m_processGen = 0;     // generation counter for stale signal protection

    // Buffering (UTF-8-safe: accumulate raw bytes, decode only complete lines)
    QByteArray m_partialBytes;
    QStringList m_lineBuffer;
    bool m_paused = false;
    int  m_pauseDropped = 0;        // lines dropped during pause overflow

    // Auto-scroll
    bool m_autoScroll = true;

    // Search
    QString m_currentSearch;

    // UI — Toolbar Row 1
    QComboBox  *m_severityCombo = nullptr;
    QLineEdit  *m_unitInput     = nullptr;
    QComboBox  *m_bootCombo     = nullptr;

    // UI — Toolbar Row 2
    QLineEdit  *m_searchInput   = nullptr;
    QPushButton *m_btnPause     = nullptr;
    QPushButton *m_btnWrap      = nullptr;
    QPushButton *m_btnClear     = nullptr;
    QPushButton *m_btnBottom    = nullptr;
    QPushButton *m_btnExport    = nullptr;

    // UI — Log + Status
    QPlainTextEdit *m_logView   = nullptr;
    QLabel     *m_headerLabel   = nullptr;
    QLabel     *m_statusLabel   = nullptr;
    QLabel     *m_lineCountLabel = nullptr;

    // Timers
    QTimer *m_flushTimer  = nullptr;
    QTimer *m_searchTimer = nullptr;

    // Pre-built severity formats
    QTextCharFormat m_fmtError;
    QTextCharFormat m_fmtWarning;
    QTextCharFormat m_fmtNotice;
    QTextCharFormat m_fmtInfo;
    QTextCharFormat m_fmtDebug;
    QTextCharFormat m_fmtDefault;

    // Theme helpers
    void applyLogStyle();
    void buildFormats();

    // Boot management
    void loadBoots();

    // Process lifecycle
    QStringList buildCommand() const;
    void startJournalctl();
    void stopJournalctl();

    // Display
    void flushBuffer();
    const QTextCharFormat &detectFormat(const QString &line) const;
    void updateLineCount();
    void reapplyThemeToDocument();

    // Search
    void applySearch();
    void highlightSearch(const QString &text);
    void clearHighlights();
    void highlightInRange(const QString &text, const QTextCursor &from);

    // Controls
    void togglePause(bool checked);
    void toggleWrap(bool checked);
    void clearLogs();
    void jumpToBottom();
    void exportLogs();
};
