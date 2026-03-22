# pylint: disable=E0611
"""
Systemd services management widget: ServicesWidget.
"""
import subprocess
import shutil

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QPushButton, QMessageBox, QLineEdit, QMenu,
    QDialog, QComboBox
)

from .base import ModernHeader
from ..styles import ModernTheme

class ServicesWidget(QWidget):
    """
    A tab widget for managing systemd services.
    Lists all services with status, supports start/stop/restart/enable/disable via pkexec.
    """
    _RUNNING_STATES = ("active", "activating", "reloading", "deactivating")
    _STOPPED_STATES = ("inactive", "failed")

    def __init__(self):
        super().__init__()
        self._services = []  # List of dicts: {unit, load, active, sub, description, enabled}
        self._filter_text = ""
        self._status_filter = "All"
        self._sort_col = 0
        self._sort_order = Qt.SortOrder.AscendingOrder
        self._has_systemctl = shutil.which("systemctl") is not None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Header
        header = QLabel("Systemd Services")
        header.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {ModernTheme.ACCENT_CYAN};")
        main_layout.addWidget(header)

        if not self._has_systemctl:
            msg = QLabel("systemctl not found \u2014 systemd is not available on this system.")
            msg.setStyleSheet(f"font-size: 16px; color: {ModernTheme.ACCENT_RED};")
            main_layout.addWidget(msg)
            main_layout.addStretch()
            return

        # Toolbar row
        toolbar = QHBoxLayout()

        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search services...")
        self._apply_search_style()
        self.search_input.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_input, 1)

        # Status filter
        self.status_combo = QComboBox()
        self.status_combo.addItems(["All", "Active", "Inactive", "Failed"])
        self.status_combo.setFixedWidth(120)
        self.status_combo.currentTextChanged.connect(self._on_status_filter_changed)
        toolbar.addWidget(self.status_combo)

        # Action buttons
        btn_style = (
            f"QPushButton {{"
            f"background-color: {ModernTheme.WIDGET_BACKGROUND};"
            f"color: {ModernTheme.TEXT_PRIMARY};"
            f"border: 1px solid {ModernTheme.ACCENT_PURPLE};"
            f"border-radius: 5px;"
            f"font-weight: bold;"
            f"padding: 5px 12px;"
            f"}}"
            f"QPushButton:hover {{"
            f"background-color: {ModernTheme.ACCENT_PURPLE};"
            f"color: {ModernTheme.APP_BACKGROUND};"
            f"}}"
        )

        self.btn_start = QPushButton("Start")
        self.btn_stop = QPushButton("Stop")
        self.btn_restart = QPushButton("Restart")
        self.btn_refresh = QPushButton("Refresh")

        for btn in (self.btn_start, self.btn_stop, self.btn_restart, self.btn_refresh):
            btn.setStyleSheet(btn_style)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            toolbar.addWidget(btn)

        self.btn_start.clicked.connect(lambda: self._do_action("start"))
        self.btn_stop.clicked.connect(lambda: self._do_action("stop"))
        self.btn_restart.clicked.connect(lambda: self._do_action("restart"))
        self.btn_refresh.clicked.connect(self._refresh_services)

        # Disable action buttons initially (no selection)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_restart.setEnabled(False)

        main_layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Service", "Description", "Active", "Sub-State", "Enabled"])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)

        # Set custom header with visible column separators
        header = ModernHeader(Qt.Orientation.Horizontal, self.table)
        self.table.setHorizontalHeader(header)
        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self._on_header_clicked)

        # Column stretch
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(2, 80)   # Active
        self.table.setColumnWidth(3, 90)   # Sub-State
        self.table.setColumnWidth(4, 80)   # Enabled

        self._apply_table_theme()

        # Context menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        # Double-click for details
        self.table.doubleClicked.connect(self._show_service_status)

        # Update button state on selection change
        self.table.itemSelectionChanged.connect(self._update_button_state)

        main_layout.addWidget(self.table)

        # Status bar
        self.status_label = QLabel("Loading services...")
        self.status_label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY}; font-size: 12px;")
        main_layout.addWidget(self.status_label)

        # Auto-refresh timer (every 5 seconds)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_services)
        self._refresh_timer.start(30000)

        # Initial load
        self._refresh_services()

    def _apply_search_style(self):
        self.search_input.setStyleSheet(
            f"QLineEdit {{"
            f"background-color: {ModernTheme.APP_BACKGROUND};"
            f"color: {ModernTheme.TEXT_PRIMARY};"
            f"border: 1px solid {ModernTheme.BORDER_COLOR};"
            f"border-radius: 5px;"
            f"padding: 5px;"
            f"}}"
        )

    def _apply_table_theme(self):
        self.table.setStyleSheet(
            f"""
            QTableWidget {{
                background-color: {ModernTheme.WIDGET_BACKGROUND};
                alternate-background-color: {ModernTheme.ALTERNATE_TABLE_BG};
                gridline-color: {ModernTheme.BORDER_COLOR};
                border: none;
            }}
            QHeaderView::section {{
                background-color: {ModernTheme.WIDGET_BACKGROUND};
                color: {ModernTheme.TEXT_PRIMARY};
                padding: 5px;
                border: none;
                border-bottom: 1px solid {ModernTheme.BORDER_COLOR};
            }}
            QTableWidget::item {{
                padding: 5px;
            }}
            QTableWidget::item:selected {{
                background-color: {ModernTheme.ACCENT_BLUE};
                color: white;
            }}
            """
        )

    def refresh_theme(self):
        """Refreshes colors on theme change."""
        if not self._has_systemctl:
            return
        self._apply_search_style()
        self._apply_table_theme()
        btn_style = (
            f"QPushButton {{"
            f"background-color: {ModernTheme.WIDGET_BACKGROUND};"
            f"color: {ModernTheme.TEXT_PRIMARY};"
            f"border: 1px solid {ModernTheme.ACCENT_PURPLE};"
            f"border-radius: 5px;"
            f"font-weight: bold;"
            f"padding: 5px 12px;"
            f"}}"
            f"QPushButton:hover {{"
            f"background-color: {ModernTheme.ACCENT_PURPLE};"
            f"color: {ModernTheme.APP_BACKGROUND};"
            f"}}"
        )
        for btn in (self.btn_start, self.btn_stop, self.btn_restart, self.btn_refresh):
            btn.setStyleSheet(btn_style)
        self.status_label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY}; font-size: 12px;")
        # Re-populate to update status colors
        self._populate_table()

    def _refresh_services(self):
        """Fetch service list from systemctl and update the table."""
        try:
            result = subprocess.run(
                ["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--output=json"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                self.status_label.setText(f"systemctl error: {result.stderr.strip()}")
                return

            import json
            units = json.loads(result.stdout)

            # Batch fetch enabled status — collect unit names
            unit_names = [u["unit"] for u in units]

            enabled_result = subprocess.run(
                ["systemctl", "is-enabled", "--no-pager"] + unit_names,
                capture_output=True, text=True, timeout=10
            )
            enabled_lines = enabled_result.stdout.strip().split("\n")

            services = []
            for i, u in enumerate(units):
                enabled = enabled_lines[i].strip() if i < len(enabled_lines) else "unknown"
                # Strip .service suffix for cleaner display
                name = u["unit"]
                if name.endswith(".service"):
                    name = name[:-8]
                services.append({
                    "unit": u["unit"],
                    "name": name,
                    "load": u.get("load", ""),
                    "active": u.get("active", ""),
                    "sub": u.get("sub", ""),
                    "description": u.get("description", ""),
                    "enabled": enabled,
                })

            self._services = services
            self._populate_table()
            self.status_label.setText(f"{len(services)} services loaded")

        except subprocess.TimeoutExpired:
            self.status_label.setText("systemctl timed out")
        except Exception as e:
            self.status_label.setText(f"Error: {e}")

    def _populate_table(self):
        """Filter and populate the table from cached service data."""
        # Save selection
        selected_unit = None
        sel_rows = self.table.selectionModel().selectedRows()
        if sel_rows:
            row = sel_rows[0].row()
            item = self.table.item(row, 0)
            if item:
                selected_unit = item.data(Qt.ItemDataRole.UserRole)

        # Save scroll position
        scroll_pos = self.table.verticalScrollBar().value()

        # Filter
        filtered = self._services
        if self._filter_text:
            ft = self._filter_text.lower()
            filtered = [s for s in filtered if ft in s["name"].lower() or ft in s["description"].lower()]
        if self._status_filter != "All":
            sf = self._status_filter.lower()
            filtered = [s for s in filtered if s["active"] == sf]

        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(filtered))

        sel_item = None
        for row, svc in enumerate(filtered):
            # Service name
            name_item = QTableWidgetItem(svc["name"])
            name_item.setData(Qt.ItemDataRole.UserRole, svc["unit"])
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, name_item)

            # Description
            desc_item = QTableWidgetItem(svc["description"])
            desc_item.setFlags(desc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, desc_item)

            # Active state (color-coded)
            active_item = QTableWidgetItem(svc["active"])
            active_item.setFlags(active_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            color = self._status_color(svc["active"])
            active_item.setForeground(QColor(color))
            self.table.setItem(row, 2, active_item)

            # Sub-state
            sub_item = QTableWidgetItem(svc["sub"])
            sub_item.setFlags(sub_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, sub_item)

            # Enabled
            en_item = QTableWidgetItem(svc["enabled"])
            en_item.setFlags(en_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if svc["enabled"] == "enabled":
                en_item.setForeground(QColor(ModernTheme.ACCENT_GREEN))
            elif svc["enabled"] in ("disabled", "masked"):
                en_item.setForeground(QColor(ModernTheme.ACCENT_RED))
            else:
                en_item.setForeground(QColor(ModernTheme.TEXT_SECONDARY))
            self.table.setItem(row, 4, en_item)

            if svc["unit"] == selected_unit:
                sel_item = name_item  # save pointer for sort-safe restoration

        self.table.setSortingEnabled(True)
        self.table.setUpdatesEnabled(True)

        # Restore selection — query row() AFTER setSortingEnabled(True) re-sorts,
        # since the row index changes during sort
        if selected_unit and sel_item is not None:
            self.table.selectRow(sel_item.row())

        # Restore scroll
        self.table.verticalScrollBar().setValue(scroll_pos)

    def _status_color(self, active_state):
        if active_state == "active":
            return ModernTheme.ACCENT_GREEN
        elif active_state == "failed":
            return ModernTheme.ACCENT_RED
        elif active_state in ("activating", "deactivating", "reloading"):
            return ModernTheme.ACCENT_ORANGE
        return ModernTheme.TEXT_SECONDARY

    def _update_button_state(self):
        """Enable/disable action buttons based on current selection and service state."""
        svc = self._selected_service_info()
        if not svc:
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.btn_restart.setEnabled(False)
            return
        active = svc.get("active", "inactive")
        is_running = active in self._RUNNING_STATES
        is_stopped = active in self._STOPPED_STATES
        self.btn_start.setEnabled(is_stopped)
        self.btn_stop.setEnabled(is_running)
        self.btn_restart.setEnabled(is_running)

    def _selected_service_info(self):
        """Return the full service dict for the selected row, or None."""
        unit = self._selected_unit()
        if not unit:
            return None
        for svc in self._services:
            if svc["unit"] == unit:
                return svc
        return None

    def _on_search_changed(self, text):
        self._filter_text = text
        self._populate_table()

    def _on_status_filter_changed(self, text):
        self._status_filter = text
        self._populate_table()

    def _on_header_clicked(self, col):
        if col == self._sort_col:
            self._sort_order = (
                Qt.SortOrder.DescendingOrder
                if self._sort_order == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
        else:
            self._sort_col = col
            self._sort_order = Qt.SortOrder.AscendingOrder
        self.table.sortItems(self._sort_col, self._sort_order)

    def _selected_unit(self):
        """Return the unit name of the selected row, or None."""
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            return None
        item = self.table.item(sel[0].row(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _do_action(self, action):
        """Run pkexec systemctl <action> <unit>."""
        unit = self._selected_unit()
        if not unit:
            QMessageBox.information(self, "No Selection", "Select a service first.")
            return

        if action in ("stop", "restart"):
            reply = QMessageBox.question(
                self, f"Confirm {action.title()}",
                f"Are you sure you want to {action} {unit}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        kill_bin = shutil.which("systemctl")
        if not kill_bin:
            QMessageBox.critical(self, "Error", "systemctl not found.")
            return

        try:
            result = subprocess.run(
                ["pkexec", kill_bin, action, unit],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                self.status_label.setText(f"Successfully ran '{action}' on {unit}")
                self._refresh_services()
            elif result.returncode in (126, 127):
                self.status_label.setText("Authentication cancelled or denied.")
            else:
                QMessageBox.warning(
                    self, "Action Failed",
                    f"systemctl {action} {unit} failed:\n{result.stderr.strip()}"
                )
        except subprocess.TimeoutExpired:
            QMessageBox.warning(self, "Timeout", f"systemctl {action} timed out.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _show_context_menu(self, pos):
        """Right-click context menu with state-aware action graying."""
        # Use itemAt(pos) to target the right-clicked row, not the previously
        # selected row — right-click doesn't auto-select in Qt
        clicked_item = self.table.itemAt(pos)
        if not clicked_item:
            return
        self.table.selectRow(clicked_item.row())

        svc = self._selected_service_info()
        if not svc:
            return

        active = svc.get("active", "inactive")
        is_running = active in self._RUNNING_STATES
        is_stopped = active in self._STOPPED_STATES
        is_enabled = svc["enabled"] == "enabled"
        is_masked = svc["enabled"] == "masked"

        menu = QMenu(self)
        act_start = menu.addAction("Start", lambda: self._do_action("start"))
        act_start.setEnabled(is_stopped)
        act_stop = menu.addAction("Stop", lambda: self._do_action("stop"))
        act_stop.setEnabled(is_running)
        act_restart = menu.addAction("Restart", lambda: self._do_action("restart"))
        act_restart.setEnabled(is_running)
        menu.addSeparator()
        act_enable = menu.addAction("Enable", lambda: self._do_action("enable"))
        act_enable.setEnabled(not is_enabled and not is_masked)
        act_disable = menu.addAction("Disable", lambda: self._do_action("disable"))
        act_disable.setEnabled(is_enabled)
        menu.addSeparator()
        menu.addAction("View Status...", self._show_service_status)

        menu.setStyleSheet(
            f"QMenu {{"
            f"background-color: {ModernTheme.WIDGET_BACKGROUND};"
            f"color: {ModernTheme.TEXT_PRIMARY};"
            f"border: 1px solid {ModernTheme.BORDER_COLOR};"
            f"}}"
            f"QMenu::item:selected {{"
            f"background-color: {ModernTheme.ACCENT_PURPLE};"
            f"}}"
        )
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _show_service_status(self, _index=None):
        """Show full systemctl status output in a dialog."""
        unit = self._selected_unit()
        if not unit:
            return

        try:
            result = subprocess.run(
                ["systemctl", "status", unit, "--no-pager", "-l"],
                capture_output=True, text=True, timeout=10
            )
            output = result.stdout or result.stderr or "No output"
        except Exception as e:
            output = str(e)

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Status: {unit}")
        dlg.resize(700, 500)
        layout = QVBoxLayout(dlg)

        from PyQt6.QtWidgets import QTextEdit
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(output)
        text.setStyleSheet(
            f"QTextEdit {{"
            f"background-color: {ModernTheme.APP_BACKGROUND};"
            f"color: {ModernTheme.TEXT_PRIMARY};"
            f"font-family: monospace;"
            f"border: 1px solid {ModernTheme.BORDER_COLOR};"
            f"}}"
        )
        layout.addWidget(text)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn)
        dlg.exec()
