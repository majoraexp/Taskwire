#include "toolswidget.h"
#include "styles.h"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QMessageBox>
#include <QProcess>
#include <QSizePolicy>
#include <QStandardPaths>
#include <QTemporaryFile>
#include <QTimer>
#include <QDir>
#include <QFile>
#include <QTextStream>

// ── Embedded caps_control.sh ────────────────────────────────
// Avoids dependency on external script file in binary builds.
// Executed via: pkexec bash <tmpfile> <action>
// No executable bit needed — bash reads the file directly.

const char *ToolsWidget::s_capsControlScript = R"(#!/bin/bash
if [[ $EUID -ne 0 ]]; then
   echo "CRITICAL: This script must be run as ROOT (sudo)." >&2
   exit 1
fi

ACTION=$1

if [ -n "$PKEXEC_UID" ]; then
    REAL_USER=$(getent passwd "$PKEXEC_UID" | cut -d: -f1)
elif [ -n "$SUDO_USER" ]; then
    REAL_USER="$SUDO_USER"
else
    REAL_USER="$USER"
fi

if [ -z "$REAL_USER" ]; then
    echo "Error: Could not detect actual user." >&2
    exit 1
fi

USER_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

# Read current X11 keymap settings to preserve layout/model/variant.
# Returns 0 if layout was parsed successfully, 1 if parsing failed.
# On failure, callers should skip localectl mutation entirely.
# Uses LC_ALL=C to ensure English field labels regardless of system locale.
read_current_keymap() {
    command -v localectl >/dev/null 2>&1 || return 1

    local status
    status=$(LC_ALL=C localectl status 2>/dev/null) || return 1
    [ -n "$status" ] || return 1

    CUR_LAYOUT=$(printf '%s\n' "$status" | sed -n 's/^[[:space:]]*X11 Layout:[[:space:]]*//p' | head -n1)
    CUR_MODEL=$(printf '%s\n' "$status" | sed -n 's/^[[:space:]]*X11 Model:[[:space:]]*//p' | head -n1)
    CUR_VARIANT=$(printf '%s\n' "$status" | sed -n 's/^[[:space:]]*X11 Variant:[[:space:]]*//p' | head -n1)
    CUR_OPTIONS=$(printf '%s\n' "$status" | sed -n 's/^[[:space:]]*X11 Options:[[:space:]]*//p' | head -n1)

    # If we couldn't even parse a layout, don't risk clobbering settings
    [ -n "$CUR_LAYOUT" ] || return 1
    return 0
}

# Check if an XKB option is present in a comma-separated list
has_xkb_option() {
    local list="${1:-}"
    local opt="$2"
    printf '%s\n' "$list" | tr ',' '\n' | sed '/^$/d' | grep -Fxq "$opt"
}

# Add an XKB option to a comma-separated list (idempotent)
add_xkb_option() {
    local list="${1:-}"
    local opt="$2"
    if has_xkb_option "$list" "$opt"; then
        printf '%s\n' "$list"
    elif [ -n "$list" ]; then
        printf '%s,%s\n' "$list" "$opt"
    else
        printf '%s\n' "$opt"
    fi
}

# Remove an XKB option from a comma-separated list
remove_xkb_option() {
    local list="${1:-}"
    local opt="$2"
    printf '%s\n' "$list" | tr ',' '\n' | sed '/^$/d' | grep -Fxv "$opt" | paste -sd ',' -
}

disable_caps() {
    # LAYER 1: SYSTEM CONSOLE (TTY) — optional, preserves existing layout
    # Only modify localectl if we can reliably parse current settings
    if read_current_keymap; then
        if ! has_xkb_option "$CUR_OPTIONS" "caps:none"; then
            NEW_OPTIONS=$(add_xkb_option "$CUR_OPTIONS" "caps:none")
            localectl set-x11-keymap --no-convert \
                "$CUR_LAYOUT" "$CUR_MODEL" "$CUR_VARIANT" "$NEW_OPTIONS" || true
        fi
    fi
    command -v dumpkeys &> /dev/null && command -v loadkeys &> /dev/null && \
        dumpkeys | sed "s/keycode  58 = Caps_Lock/keycode  58 = VoidSymbol/" | loadkeys 2>/dev/null || true

    # LAYER 2: KDE PLASMA
    KXKB_FILE="$USER_HOME/.config/kxkbrc"
    if [ -f "$KXKB_FILE" ]; then
        cp "$KXKB_FILE" "$KXKB_FILE.bak"
        if ! grep -q "\[Layout\]" "$KXKB_FILE"; then
            echo -e "\n[Layout]" >> "$KXKB_FILE"
        fi
        if grep -q "Options=" "$KXKB_FILE"; then
            if ! grep -q "caps:none" "$KXKB_FILE"; then
                sed -i "/Options=/ s/$/,caps:none/" "$KXKB_FILE"
                sed -i "s/Options=,/Options=/" "$KXKB_FILE"
            fi
        else
            sed -i "/\[Layout\]/a Options=caps:none" "$KXKB_FILE"
        fi
        chown "$REAL_USER":"$REAL_USER" "$KXKB_FILE"
    else
        mkdir -p "$USER_HOME/.config"
        echo -e "[Layout]\nOptions=caps:none\nResetOldOptions=true" > "$KXKB_FILE"
        chown -R "$REAL_USER":"$REAL_USER" "$USER_HOME/.config/kxkbrc"
    fi

    # LAYER 3: GNOME — optional
    if command -v gsettings &> /dev/null; then
        PID=$(pgrep -u "$REAL_USER" gnome-session | head -n 1)
        if [ -n "$PID" ]; then
            DBUS_ADDR=$(grep -z DBUS_SESSION_BUS_ADDRESS /proc/"$PID"/environ | cut -d= -f2-)
            export DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR"
            su -c "gsettings set org.gnome.desktop.input-sources xkb-options \"['caps:none']\"" - "$REAL_USER" || true
        fi
    fi

    # LAYER 4: RUNTIME (X11/Xwayland) — optional, fails on pure Wayland
    command -v setxkbmap &> /dev/null && setxkbmap -option caps:none 2>/dev/null || true
}

enable_caps() {
    # LAYER 1: SYSTEM CONSOLE (TTY) — preserves existing layout, removes caps:none
    # Only modify localectl if we can reliably parse current settings
    if read_current_keymap; then
        NEW_OPTIONS=$(remove_xkb_option "$CUR_OPTIONS" "caps:none")
        localectl set-x11-keymap --no-convert \
            "$CUR_LAYOUT" "$CUR_MODEL" "$CUR_VARIANT" "$NEW_OPTIONS" || true
    fi
    command -v loadkeys &> /dev/null && loadkeys -d 2>/dev/null || true

    KXKB_FILE="$USER_HOME/.config/kxkbrc"
    if [ -f "$KXKB_FILE" ]; then
        sed -i "s/caps:none//g" "$KXKB_FILE"
        sed -i "s/Options=,/Options=/g" "$KXKB_FILE"
    fi

    if command -v gsettings &> /dev/null; then
        su -c "gsettings reset org.gnome.desktop.input-sources xkb-options" - "$REAL_USER" || true
    fi

    command -v setxkbmap &> /dev/null && setxkbmap -option 2>/dev/null || true
}

case "$ACTION" in
    disable) disable_caps ;;
    enable) enable_caps ;;
    *) echo "Usage: $0 [disable|enable]" >&2; exit 1 ;;
esac
exit 0
)";

// ── Constructor ─────────────────────────────────────────────

ToolsWidget::ToolsWidget(QWidget *parent)
    : QWidget(parent)
{
    m_mainLayout = new QVBoxLayout(this);
    m_mainLayout->setContentsMargins(20, 20, 20, 20);
    m_mainLayout->setSpacing(20);

    // Header
    m_header = new QLabel(QStringLiteral("System Tools"), this);
    m_header->setStyleSheet(
        QStringLiteral("font-size: 24px; font-weight: bold; color: %1;")
            .arg(QColor(ModernTheme::appBackground).lightness() > 128
                 ? ModernTheme::accentBlue : ModernTheme::accentCyan));
    m_mainLayout->addWidget(m_header);

    // Caps Lock Card
    m_capsCard = new QWidget(this);
    m_capsCard->setProperty("class", "card");
    auto *cardInnerLayout = new QVBoxLayout(m_capsCard);
    cardInnerLayout->setContentsMargins(15, 10, 15, 10);

    // Card title
    auto *cardTitle = new QLabel(QStringLiteral("Input Devices"), m_capsCard);
    cardTitle->setStyleSheet(
        QStringLiteral("font-size: 14px; font-weight: bold; color: %1; border: none;")
            .arg(ModernTheme::textSecondary));
    cardInnerLayout->addWidget(cardTitle);

    // Horizontal row: label | status | spacer | LED | spacer | button | stretch
    auto *capsRow = new QHBoxLayout();
    capsRow->setSpacing(10);

    m_capsLabel = new QLabel(QStringLiteral("Caps Lock Status:"), m_capsCard);
    capsRow->addWidget(m_capsLabel);

    m_capsStatusText = new QLabel(QStringLiteral("Checking..."), m_capsCard);
    capsRow->addWidget(m_capsStatusText);

    capsRow->addSpacing(20);

    // LED indicator (16x16 circle)
    m_capsLed = new QWidget(m_capsCard);
    m_capsLed->setFixedSize(16, 16);
    m_capsLed->setStyleSheet(
        QStringLiteral("border-radius: 8px; background-color: %1;")
            .arg(ModernTheme::textSecondary));
    capsRow->addWidget(m_capsLed);

    capsRow->addSpacing(10);

    // Toggle button
    m_capsBtn = new QPushButton(QStringLiteral("Toggle Caps Lock"), m_capsCard);
    m_capsBtn->setFixedSize(200, 40);
    m_capsBtn->setCursor(Qt::PointingHandCursor);
    connect(m_capsBtn, &QPushButton::clicked, this, &ToolsWidget::toggleCapsLock);
    capsRow->addWidget(m_capsBtn);

    capsRow->addStretch();
    cardInnerLayout->addLayout(capsRow);

    // Card size policy — don't stretch full width
    m_capsCard->setSizePolicy(QSizePolicy::Maximum, QSizePolicy::Preferred);

    // Wrap card in HBox to keep it left-aligned
    auto *cardRow = new QHBoxLayout();
    cardRow->addWidget(m_capsCard);
    cardRow->addStretch();

    m_mainLayout->addLayout(cardRow);
    m_mainLayout->addStretch();

    // Apply initial theme
    refreshTheme();

    // Defer status check to after event loop starts
    QTimer::singleShot(0, this, &ToolsWidget::refreshCapsStatus);
}

// ── State machine ───────────────────────────────────────────

void ToolsWidget::applyCapsState(CapsState state) {
    m_capsState = state;

    switch (state) {
    case CapsState::Enabled:
        m_capsStatusText->setText(QStringLiteral("ENABLED"));
        m_capsStatusText->setStyleSheet(
            QStringLiteral("font-size: 16px; font-weight: bold; color: %1; border: none;")
                .arg(ModernTheme::accentGreen));
        m_capsLed->setStyleSheet(
            QStringLiteral("border-radius: 8px; background-color: %1; border: 2px solid %2;")
                .arg(ModernTheme::accentGreen, ModernTheme::borderColor));
        m_capsBtn->setText(QStringLiteral("Disable Caps Lock"));
        m_capsBtn->setEnabled(true);
        break;

    case CapsState::Disabled:
        m_capsStatusText->setText(QStringLiteral("DISABLED"));
        m_capsStatusText->setStyleSheet(
            QStringLiteral("font-size: 16px; font-weight: bold; color: %1; border: none;")
                .arg(ModernTheme::accentRed));
        m_capsLed->setStyleSheet(
            QStringLiteral("border-radius: 8px; background-color: %1; border: 2px solid %2;")
                .arg(ModernTheme::accentRed, ModernTheme::borderColor));
        m_capsBtn->setText(QStringLiteral("Enable Caps Lock"));
        m_capsBtn->setEnabled(true);
        break;

    case CapsState::Unknown:
        m_capsStatusText->setText(QStringLiteral("UNKNOWN"));
        m_capsStatusText->setStyleSheet(
            QStringLiteral("font-size: 16px; font-weight: bold; color: %1; border: none;")
                .arg(ModernTheme::textSecondary));
        m_capsLed->setStyleSheet(
            QStringLiteral("border-radius: 8px; background-color: %1; border: 2px solid %2;")
                .arg(ModernTheme::textSecondary, ModernTheme::borderColor));
        m_capsBtn->setText(QStringLiteral("Toggle Caps Lock"));
        m_capsBtn->setEnabled(true);
        break;

    case CapsState::Busy:
        m_capsStatusText->setText(QStringLiteral("Applying..."));
        m_capsStatusText->setStyleSheet(
            QStringLiteral("font-size: 16px; font-weight: bold; color: %1; border: none;")
                .arg(ModernTheme::accentOrange));
        m_capsLed->setStyleSheet(
            QStringLiteral("border-radius: 8px; background-color: %1; border: 2px solid %2;")
                .arg(ModernTheme::accentOrange, ModernTheme::borderColor));
        // Keep current button text during busy state
        m_capsBtn->setEnabled(false);
        break;
    }
}

// ── Status detection ────────────────────────────────────────

// Individual probe methods for desktop-aware ordering
static bool probeLocalectl(bool &isDisabled) {
    QString localectlPath = QStandardPaths::findExecutable(QStringLiteral("localectl"));
    if (localectlPath.isEmpty())
        return false;

    QProcess proc;
    proc.start(localectlPath, {QStringLiteral("status")});
    if (proc.waitForStarted(500) && proc.waitForFinished(1500)) {
        if (proc.exitStatus() == QProcess::NormalExit && proc.exitCode() == 0) {
            QString output = QString::fromUtf8(proc.readAllStandardOutput());
            if (output.contains(QStringLiteral("caps:none")))
                isDisabled = true;
            return true; // probe succeeded
        }
    } else {
        proc.kill();
        proc.waitForFinished(200);
    }
    return false;
}

static bool probeKde(bool &isDisabled) {
    QString kxkbPath = QDir::homePath() + QStringLiteral("/.config/kxkbrc");
    QFile kxkbFile(kxkbPath);
    if (kxkbFile.open(QIODevice::ReadOnly | QIODevice::Text)) {
        QString content = QString::fromUtf8(kxkbFile.readAll());
        kxkbFile.close();
        if (content.contains(QStringLiteral("caps:none")))
            isDisabled = true;
        return true; // probe succeeded
    }
    return false;
}

static bool probeGnome(bool &isDisabled) {
    QString gsettingsPath = QStandardPaths::findExecutable(QStringLiteral("gsettings"));
    if (gsettingsPath.isEmpty())
        return false;

    QProcess proc;
    proc.start(gsettingsPath, {
        QStringLiteral("get"),
        QStringLiteral("org.gnome.desktop.input-sources"),
        QStringLiteral("xkb-options")
    });
    if (proc.waitForStarted(500) && proc.waitForFinished(1500)) {
        if (proc.exitStatus() == QProcess::NormalExit && proc.exitCode() == 0) {
            QString output = QString::fromUtf8(proc.readAllStandardOutput());
            if (output.contains(QStringLiteral("caps:none")))
                isDisabled = true;
            return true; // probe succeeded
        }
    } else {
        proc.kill();
        proc.waitForFinished(200);
    }
    return false;
}

void ToolsWidget::refreshCapsStatus() {
    bool isDisabled = false;
    bool detected = false;

    // Detect active desktop to prefer session-specific source first
    const QString desktop =
        qEnvironmentVariable("XDG_CURRENT_DESKTOP").toLower();
    const bool preferKde =
        desktop.contains(QStringLiteral("kde")) ||
        desktop.contains(QStringLiteral("plasma"));
    const bool preferGnome =
        desktop.contains(QStringLiteral("gnome"));

    // True precedence: first successful probe in preferred order wins.
    // This ensures the active desktop's authoritative source is trusted
    // without later fallback sources overriding it.
    using ProbeFn = bool (*)(bool &);
    ProbeFn probes[3];

    if (preferKde) {
        probes[0] = probeKde;
        probes[1] = probeLocalectl;
        probes[2] = probeGnome;
    } else if (preferGnome) {
        probes[0] = probeGnome;
        probes[1] = probeLocalectl;
        probes[2] = probeKde;
    } else {
        probes[0] = probeLocalectl;
        probes[1] = probeKde;
        probes[2] = probeGnome;
    }

    for (auto probe : probes) {
        if (probe(isDisabled)) {
            detected = true;
            break; // first successful probe is authoritative
        }
    }

    if (!detected) {
        applyCapsState(CapsState::Unknown);
    } else {
        applyCapsState(isDisabled ? CapsState::Disabled : CapsState::Enabled);
    }
}

// ── Toggle ──────────────────────────────────────────────────

void ToolsWidget::toggleCapsLock() {
    // Re-entry guard
    if (m_capsState == CapsState::Busy)
        return;

    // Save previous state so we can restore on early failures
    const CapsState previousState = m_capsState;

    // Check required binaries
    QString bashPath = QStandardPaths::findExecutable(QStringLiteral("bash"));
    QString pkexecPath = QStandardPaths::findExecutable(QStringLiteral("pkexec"));

    if (bashPath.isEmpty()) {
        QMessageBox::critical(this, QStringLiteral("Error"),
            QStringLiteral("bash not found on this system."));
        return;
    }
    if (pkexecPath.isEmpty()) {
        QMessageBox::critical(this, QStringLiteral("Error"),
            QStringLiteral("pkexec not found. Install polkit to use this feature."));
        return;
    }

    // Determine action based on current state
    const QString action =
        (m_capsState == CapsState::Disabled)
            ? QStringLiteral("enable")
            : QStringLiteral("disable");
    const QString actionPast =
        (action == QStringLiteral("enable"))
            ? QStringLiteral("enabled")
            : QStringLiteral("disabled");

    applyCapsState(CapsState::Busy);

    // Write script to temp file
    QTemporaryFile tmpFile;
    tmpFile.setAutoRemove(true);
    if (!tmpFile.open()) {
        QMessageBox::critical(this, QStringLiteral("Error"),
            QStringLiteral("Could not create temporary helper script."));
        applyCapsState(previousState);
        return;
    }

    QByteArray scriptData(s_capsControlScript);
    if (tmpFile.write(scriptData) != scriptData.size()) {
        QMessageBox::critical(this, QStringLiteral("Error"),
            QStringLiteral("Failed to write temporary script (disk full?)."));
        applyCapsState(previousState);
        return;
    }
    tmpFile.flush();
    // QTemporaryFile auto-removes on destruction (not on close).
    // Since tmpFile is stack-local and we block until QProcess finishes,
    // the file persists for the entire duration of the process.

    // Run pkexec bash <tmpfile> <action>
    QProcess proc;
    proc.start(pkexecPath, {bashPath, tmpFile.fileName(), action});

    if (!proc.waitForStarted(5000)) {
        QMessageBox::critical(this, QStringLiteral("Error"),
            QStringLiteral("Could not start pkexec. Is a polkit authentication agent running?"));
        applyCapsState(previousState);
        return;
    }

    // pkexec shows an auth dialog — give generous timeout (60s)
    if (!proc.waitForFinished(60000)) {
        proc.kill();
        proc.waitForFinished(2000);
        QMessageBox::critical(this, QStringLiteral("Error"),
            QStringLiteral("The Caps Lock operation timed out."));
        applyCapsState(previousState);
        return;
    }

    tmpFile.close();

    // Capture output for error reporting
    const QString stdErr = QString::fromUtf8(proc.readAllStandardError()).trimmed();
    const QString stdOut = QString::fromUtf8(proc.readAllStandardOutput()).trimmed();
    const QString details = !stdErr.isEmpty() ? stdErr : stdOut;

    // Check result
    if (proc.exitStatus() != QProcess::NormalExit || proc.exitCode() != 0) {
        applyCapsState(previousState);

        const int exitCode = proc.exitCode();

        // Exit 126/127 = user cancelled auth dialog — restore silently
        if (proc.exitStatus() == QProcess::NormalExit &&
            (exitCode == 126 || exitCode == 127)) {
            return;
        }

        QString msg;
        if (proc.exitStatus() != QProcess::NormalExit) {
            msg = QStringLiteral("The process terminated abnormally.");
        } else {
            msg = QStringLiteral("Could not %1 Caps Lock.").arg(action);
        }

        if (!details.isEmpty())
            msg += QStringLiteral("\n\nDetails:\n") + details;

        QMessageBox::warning(this, QStringLiteral("Error"), msg);
        return;
    }

    // Re-check actual state and verify postcondition
    refreshCapsStatus();

    const bool confirmed =
        (action == QStringLiteral("disable") && m_capsState == CapsState::Disabled) ||
        (action == QStringLiteral("enable") && m_capsState == CapsState::Enabled);

    if (!confirmed) {
        QMessageBox::warning(this, QStringLiteral("Result Unconfirmed"),
            QStringLiteral("The operation completed, but the resulting Caps Lock state "
                           "could not be confirmed.\n\n"
                           "Changes may require logging out or rebooting to take effect."));
        return;
    }

    QMessageBox::information(this, QStringLiteral("Success"),
        QStringLiteral("Caps Lock has been %1.\n"
                        "Changes may require logging out or rebooting to fully take effect.")
            .arg(actionPast));
}

// ── Theme ───────────────────────────────────────────────────

void ToolsWidget::refreshTheme() {
    // Header
    const QString &headerColor = QColor(ModernTheme::appBackground).lightness() > 128
        ? ModernTheme::accentBlue : ModernTheme::accentCyan;
    m_header->setStyleSheet(
        QStringLiteral("font-size: 24px; font-weight: bold; color: %1;")
            .arg(headerColor));

    // Card background + border
    m_capsCard->setStyleSheet(
        QStringLiteral("background-color: %1; border: 1px solid %2; border-radius: 10px;")
            .arg(ModernTheme::widgetBackground, ModernTheme::borderColor));

    // Label
    m_capsLabel->setStyleSheet(
        QStringLiteral("font-size: 16px; color: %1; border: none;")
            .arg(ModernTheme::textPrimary));

    // Button
    m_capsBtn->setStyleSheet(
        QStringLiteral(
            "QPushButton {"
            "  background-color: %1;"
            "  color: %2;"
            "  border: 1px solid %3;"
            "  border-radius: 5px;"
            "  font-weight: bold;"
            "}"
            "QPushButton:hover {"
            "  background-color: %3;"
            "  color: %4;"
            "}"
            "QPushButton:disabled {"
            "  background-color: %1;"
            "  color: %5;"
            "  border: 1px solid %5;"
            "}")
            .arg(ModernTheme::alternateTableBg,
                 ModernTheme::textPrimary,
                 ModernTheme::accentPurple,
                 ModernTheme::appBackground,
                 ModernTheme::textSecondary));

    // Re-apply current state colors (LED + status text)
    applyCapsState(m_capsState);
}
