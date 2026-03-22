# pylint: disable=E0611
"""
System tools widget: ToolsWidget.
"""
import os
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QMessageBox, QSizePolicy
)

from .base import Card
from ..styles import ModernTheme


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
        Calls the caps_control.sh script using pkexec to toggle functionality.
        """
        import sys

        # Determine script path
        # This file is in Taskwire/src/ui/
        # Script is in Taskwire/src/scripts/

        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Taskwire/src
        script_path = os.path.join(base_path, "scripts", "caps_control.sh")

        if not os.path.exists(script_path):
             # Fallback: Check relative to cwd
             script_path = os.path.abspath(os.path.join("Taskwire", "src", "scripts", "caps_control.sh"))

        action = "disable" if self.is_caps_enabled else "enable"

        cmd = ["pkexec", script_path, action]

        try:
            # Run blocking or non-blocking? Blocking to update UI after.
            subprocess.run(cmd, check=True)

            # Re-check status
            self.check_caps_status()

            # Show message
            QMessageBox.information(self, "Success", f"Caps Lock has been {action}d.\nA reboot is required for changes to fully take effect.")

        except subprocess.CalledProcessError:
             QMessageBox.warning(self, "Error", "Failed to execute command. Did you cancel the authentication?")
        except Exception as e:
             QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
