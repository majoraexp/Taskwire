# pylint: disable=E0611
"""
System tools widget: ToolsWidget.
"""
import os
import shutil
import stat
import subprocess
import tempfile

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QMessageBox, QSizePolicy
)

from .base import Card
from ..styles import ModernTheme

# Embedded caps_control.sh — avoids dependency on external script file
# (Nuitka binaries don't bundle shell scripts)
_CAPS_CONTROL_SCRIPT = r'''#!/bin/bash
if [[ $EUID -ne 0 ]]; then
   echo "CRITICAL: This script must be run as ROOT (sudo)."
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
    echo "Error: Could not detect actual user."
    exit 1
fi

USER_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

disable_caps() {
    # LAYER 1: SYSTEM CONSOLE (TTY)
    localectl set-x11-keymap --no-convert us "" "" "caps:none"
    dumpkeys | sed "s/keycode  58 = Caps_Lock/keycode  58 = VoidSymbol/" | loadkeys 2>/dev/null

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

    # LAYER 3: GNOME
    if command -v gsettings &> /dev/null; then
        PID=$(pgrep -u "$REAL_USER" gnome-session | head -n 1)
        if [ -n "$PID" ]; then
            DBUS_ADDR=$(grep -z DBUS_SESSION_BUS_ADDRESS /proc/"$PID"/environ | cut -d= -f2-)
            export DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR"
            su -c "gsettings set org.gnome.desktop.input-sources xkb-options \"['caps:none']\"" - "$REAL_USER"
        fi
    fi

    # LAYER 4: RUNTIME (X11/Xwayland)
    if command -v setxkbmap &> /dev/null; then
        setxkbmap -option caps:none 2>/dev/null
    fi
}

enable_caps() {
    localectl set-x11-keymap --no-convert us "" "" ""
    loadkeys -d 2>/dev/null

    KXKB_FILE="$USER_HOME/.config/kxkbrc"
    if [ -f "$KXKB_FILE" ]; then
        sed -i "s/caps:none//g" "$KXKB_FILE"
        sed -i "s/Options=,/Options=/g" "$KXKB_FILE"
    fi

    if command -v gsettings &> /dev/null; then
        su -c "gsettings reset org.gnome.desktop.input-sources xkb-options" - "$REAL_USER"
    fi

    setxkbmap -option 2>/dev/null
}

case "$ACTION" in
    disable) disable_caps ;;
    enable) enable_caps ;;
    *) echo "Usage: $0 [disable|enable]"; exit 1 ;;
esac
'''


class ToolsWidget(QWidget):
    """
    A widget that provides system tools and toggles, such as Caps Lock control.
    """
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(20)

        # Header
        header = QLabel("System Tools")
        header.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {ModernTheme.ACCENT_CYAN};")
        self.layout.addWidget(header)

        # Caps Lock Control Card
        self.caps_card = Card("Input Devices")
        self.caps_card.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        self.caps_layout = QHBoxLayout()
        self.caps_card.layout.addLayout(self.caps_layout)

        # Label
        self.caps_label = QLabel("Caps Lock Status:")
        self.caps_label.setStyleSheet(f"font-size: 16px; color: {ModernTheme.TEXT_PRIMARY};")
        self.caps_layout.addWidget(self.caps_label)

        # Status Text (Enabled/Disabled)
        self.caps_status_text = QLabel("Checking...")
        self.caps_status_text.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {ModernTheme.TEXT_SECONDARY};")
        self.caps_layout.addWidget(self.caps_status_text)

        # Spacer
        self.caps_layout.addSpacing(20)

        # LED Indicator
        self.caps_led = QWidget()
        self.caps_led.setFixedSize(16, 16)
        self.caps_led.setStyleSheet("border-radius: 8px; background-color: #444;") # Default off
        self.caps_layout.addWidget(self.caps_led)

        # Spacer
        self.caps_layout.addSpacing(10)

        # Toggle Button
        self.caps_btn = QPushButton("Enable/Disable Capslock")
        self.caps_btn.setFixedSize(200, 40)
        self.caps_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.caps_btn.clicked.connect(self.toggle_caps_lock)
        self.caps_layout.addWidget(self.caps_btn)

        # Push everything to the left in the card
        self.caps_layout.addStretch()

        # Wrap Card in HBox to prevent horizontal stretching
        card_row = QHBoxLayout()
        card_row.addWidget(self.caps_card)
        card_row.addStretch() # Push card to left

        self.layout.addLayout(card_row)
        self.layout.addStretch() # Push everything up

        # Initial Status Check
        self.check_caps_status()

    def refresh_theme(self):
        """Refreshes the widget's colors based on the current ModernTheme."""
        self.caps_card.setStyleSheet(f"background-color: {ModernTheme.WIDGET_BACKGROUND}; border: 1px solid {ModernTheme.BORDER_COLOR}; border-radius: 10px;")
        self.caps_label.setStyleSheet(f"font-size: 16px; color: {ModernTheme.TEXT_PRIMARY};")
        # Button styling
        self.caps_btn.setStyleSheet(
            f"QPushButton {{"
            f"background-color: {ModernTheme.ALTERNATE_TABLE_BG};"
            f"color: {ModernTheme.TEXT_PRIMARY};"
            f"border: 1px solid {ModernTheme.ACCENT_PURPLE};"
            f"border-radius: 5px;"
            f"font-weight: bold;"
            f"}}"
            f"QPushButton:hover {{"
            f"background-color: {ModernTheme.ACCENT_PURPLE};"
            f"color: {ModernTheme.APP_BACKGROUND};"
            f"}}"
        )
        # Re-apply status color
        self.update_status_ui(self.is_caps_enabled)

    def check_caps_status(self):
        """
        Checks if Caps Lock is disabled via config files (simulating the shell script logic).
        """
        # Logic: Assume Enabled unless we find 'caps:none' in configs
        is_disabled = False

        # 1. Check KDE Config (~/.config/kxkbrc)
        home = os.path.expanduser("~")
        kxkb_file = os.path.join(home, ".config", "kxkbrc")
        if os.path.exists(kxkb_file):
            try:
                with open(kxkb_file, "r") as f:
                    content = f.read()
                    if "caps:none" in content:
                        is_disabled = True
            except:
                pass

        # 2. Check GNOME (gsettings)
        # Simple check using subprocess
        if not is_disabled:
            try:
                # This might fail if gsettings not installed, that's fine
                res = subprocess.run(
                    ["gsettings", "get", "org.gnome.desktop.input-sources", "xkb-options"],
                    capture_output=True, text=True
                )
                if res.returncode == 0 and "caps:none" in res.stdout:
                    is_disabled = True
            except:
                pass

        self.is_caps_enabled = not is_disabled
        self.update_status_ui(self.is_caps_enabled)

    def update_status_ui(self, enabled):
        """Updates the LED and text based on status."""
        if enabled:
            self.caps_status_text.setText("ENABLED")
            self.caps_status_text.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {ModernTheme.ACCENT_GREEN};")
            self.caps_led.setStyleSheet(f"border-radius: 8px; background-color: {ModernTheme.ACCENT_GREEN}; border: 2px solid #2f3640;")
        else:
            self.caps_status_text.setText("DISABLED")
            self.caps_status_text.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {ModernTheme.ACCENT_RED};")
            self.caps_led.setStyleSheet(f"border-radius: 8px; background-color: {ModernTheme.ACCENT_RED}; border: 2px solid #2f3640;")

        # Apply button style (always same style, just needs refresh)
        self.caps_btn.setStyleSheet(
            f"QPushButton {{"
            f"background-color: {ModernTheme.ALTERNATE_TABLE_BG};"
            f"color: {ModernTheme.TEXT_PRIMARY};"
            f"border: 1px solid {ModernTheme.ACCENT_PURPLE};"
            f"border-radius: 5px;"
            f"font-weight: bold;"
            f"}}"
            f"QPushButton:hover {{"
            f"background-color: {ModernTheme.ACCENT_PURPLE};"
            f"color: {ModernTheme.APP_BACKGROUND};"
            f"}}"
        )

    def toggle_caps_lock(self):
        """
        Writes the embedded caps_control script to a temp file and runs it via pkexec.
        Works in both source and Nuitka binary builds.
        """
        bash_path = shutil.which("bash")
        pkexec_path = shutil.which("pkexec")
        if not bash_path:
            QMessageBox.critical(self, "Error", "bash not found on this system.")
            return
        if not pkexec_path:
            QMessageBox.critical(self, "Error", "pkexec not found. Install polkit to use this feature.")
            return

        action = "disable" if self.is_caps_enabled else "enable"

        # Write embedded script to temp file
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".sh", prefix="taskwire_caps_")
        try:
            with os.fdopen(tmp_fd, "w") as f:
                f.write(_CAPS_CONTROL_SCRIPT)
            os.chmod(tmp_path, os.stat(tmp_path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

            subprocess.run([pkexec_path, bash_path, tmp_path, action], check=True)

            # Re-check status
            self.check_caps_status()

            QMessageBox.information(self, "Success", f"Caps Lock has been {action}d.\nA reboot is required for changes to fully take effect.")

        except subprocess.CalledProcessError:
            QMessageBox.warning(self, "Error", "Failed to execute command. Did you cancel the authentication?")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
