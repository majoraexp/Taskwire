# pylint: disable=E0611
"""
Active network connections and ports viewer: ConnectionsWidget.
"""
import re
import subprocess
import shutil

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QPushButton, QMessageBox, QLineEdit, QMenu,
    QComboBox
)

from .base import ModernHeader, SortableTableWidgetItem
from ..styles import ModernTheme


class ConnectionsWidget(QWidget):
    """
    A tab widget for viewing active network connections and listening ports.
    Frontend for 'ss -tupna' showing protocols, addresses, ports, and owning processes.
    """

    _PROTO_RE = re.compile(
        r'users:\(\("([^"]+)",pid=(\d+),fd=\d+\)\)'
    )

    def __init__(self):
        super().__init__()
        self._connections = []
        self._filter_text = ""
        self._proto_filter = "All"
        self._state_filter = "All"
        self._sort_col = 0
        self._sort_order = Qt.SortOrder.AscendingOrder
        self._has_ss = shutil.which("ss") is not None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Header
        header = QLabel("Active Connections")
        header.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {ModernTheme.ACCENT_CYAN};")
        main_layout.addWidget(header)

        if not self._has_ss:
            msg = QLabel("ss command not found — iproute2 is not installed.")
            msg.setStyleSheet(f"font-size: 16px; color: {ModernTheme.ACCENT_RED};")
            main_layout.addWidget(msg)
            main_layout.addStretch()
            return

        # Toolbar
        toolbar = QHBoxLayout()

        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search connections...")
        self._apply_search_style()
        self.search_input.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_input, 1)

        # Protocol filter
        self.proto_combo = QComboBox()
        self.proto_combo.addItems(["All", "TCP", "UDP"])
        self.proto_combo.setFixedWidth(90)
        self.proto_combo.currentTextChanged.connect(self._on_proto_filter_changed)
        toolbar.addWidget(self.proto_combo)

        # State filter
        self.state_combo = QComboBox()
        self.state_combo.addItems(["All", "LISTEN", "ESTAB", "UNCONN", "CLOSE-WAIT", "TIME-WAIT"])
        self.state_combo.setFixedWidth(130)
        self.state_combo.currentTextChanged.connect(self._on_state_filter_changed)
        toolbar.addWidget(self.state_combo)

        # Refresh button
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
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setStyleSheet(btn_style)
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.clicked.connect(self._refresh_connections)
        toolbar.addWidget(self.btn_refresh)

        main_layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Protocol", "State", "Local Address", "Port",
            "Peer Address", "Peer Port", "Process", "PID"
        ])
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

        # Column sizing — use Interactive + fixed widths instead of ResizeToContents
        # to avoid expensive per-cell measurement on every refresh
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)   # Protocol
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)   # State
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)       # Local Address
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)   # Port
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)       # Peer Address
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)   # Peer Port
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)   # Process
        h.setSectionResizeMode(7, QHeaderView.ResizeMode.Interactive)   # PID
        self.table.setColumnWidth(0, 70)   # Protocol
        self.table.setColumnWidth(1, 100)  # State
        self.table.setColumnWidth(3, 60)   # Port
        self.table.setColumnWidth(5, 70)   # Peer Port
        self.table.setColumnWidth(6, 120)  # Process
        self.table.setColumnWidth(7, 60)   # PID

        self._apply_table_theme()

        # Context menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        main_layout.addWidget(self.table)

        # Status bar
        self.status_label = QLabel("Loading connections...")
        self.status_label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY}; font-size: 12px;")
        main_layout.addWidget(self.status_label)

        # Auto-refresh timer (3 seconds)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_connections)
        self._refresh_timer.start(3000)

        # Initial load
        self._refresh_connections()

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
        if not self._has_ss:
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
        self.btn_refresh.setStyleSheet(btn_style)
        self.status_label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY}; font-size: 12px;")
        self._populate_table()

    @staticmethod
    def _parse_address(addr_port):
        """Split an address:port string, handling IPv6 brackets."""
        if addr_port.startswith("["):
            # IPv6: [::1]:80 or [::]:*
            bracket_end = addr_port.rfind("]")
            if bracket_end != -1 and bracket_end + 1 < len(addr_port) and addr_port[bracket_end + 1] == ":":
                return addr_port[1:bracket_end], addr_port[bracket_end + 2:]
            return addr_port[1:bracket_end] if bracket_end != -1 else addr_port, "*"
        # IPv4 or wildcard: 0.0.0.0:80 or *:*
        idx = addr_port.rfind(":")
        if idx != -1:
            return addr_port[:idx], addr_port[idx + 1:]
        return addr_port, "*"

    def _refresh_connections(self):
        """Fetch connections from ss and update the table."""
        try:
            result = subprocess.run(
                ["ss", "-tupna", "--no-header"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                self.status_label.setText(f"ss error: {result.stderr.strip()}")
                return

            connections = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) < 6:
                    continue

                proto = parts[0]  # tcp or udp
                state = parts[1]
                local_full = parts[4]
                peer_full = parts[5]

                local_addr, local_port = self._parse_address(local_full)
                peer_addr, peer_port = self._parse_address(peer_full)

                # Extract process info from remaining fields
                process_name = ""
                pid = ""
                rest = " ".join(parts[6:])
                m = self._PROTO_RE.search(rest)
                if m:
                    process_name = m.group(1)
                    pid = m.group(2)

                connections.append({
                    "proto": proto,
                    "state": state,
                    "local_addr": local_addr,
                    "local_port": local_port,
                    "peer_addr": peer_addr,
                    "peer_port": peer_port,
                    "process": process_name,
                    "pid": pid,
                })

            self._connections = connections
            self._populate_table()
            self.status_label.setText(f"{len(connections)} connections")

        except subprocess.TimeoutExpired:
            self.status_label.setText("ss timed out")
        except Exception as e:
            self.status_label.setText(f"Error: {e}")

    def _populate_table(self):
        """Filter and populate the table from cached connection data."""
        # Save selection
        selected_key = None
        sel_rows = self.table.selectionModel().selectedRows()
        if sel_rows:
            row = sel_rows[0].row()
            item = self.table.item(row, 0)
            if item:
                selected_key = item.data(Qt.ItemDataRole.UserRole)

        scroll_pos = self.table.verticalScrollBar().value()

        # Filter
        filtered = self._connections
        if self._filter_text:
            ft = self._filter_text.lower()
            filtered = [c for c in filtered if any(
                ft in str(v).lower() for v in c.values()
            )]
        if self._proto_filter != "All":
            pf = self._proto_filter.lower()
            filtered = [c for c in filtered if c["proto"] == pf]
        if self._state_filter != "All":
            filtered = [c for c in filtered if c["state"] == self._state_filter]

        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(filtered))

        sel_item = None
        for row, conn in enumerate(filtered):
            # Unique key for selection preservation
            key = f"{conn['proto']}:{conn['local_addr']}:{conn['local_port']}:{conn['peer_addr']}:{conn['peer_port']}:{conn['pid']}"

            # Protocol (color-coded)
            proto_item = QTableWidgetItem(conn["proto"].upper())
            proto_item.setData(Qt.ItemDataRole.UserRole, key)
            proto_item.setFlags(proto_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            proto_color = ModernTheme.ACCENT_CYAN if conn["proto"] == "tcp" else ModernTheme.ACCENT_ORANGE
            proto_item.setForeground(QColor(proto_color))
            self.table.setItem(row, 0, proto_item)

            # State (color-coded)
            state_item = QTableWidgetItem(conn["state"])
            state_item.setFlags(state_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            state_item.setForeground(QColor(self._state_color(conn["state"])))
            self.table.setItem(row, 1, state_item)

            # Local Address
            la_item = QTableWidgetItem(conn["local_addr"])
            la_item.setFlags(la_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, la_item)

            # Local Port (numeric sort via SortableTableWidgetItem)
            lp_item = SortableTableWidgetItem()
            lp_item.setText(conn["local_port"])
            try:
                lp_item.setData(Qt.ItemDataRole.UserRole, int(conn["local_port"]))
            except ValueError:
                lp_item.setData(Qt.ItemDataRole.UserRole, 0)
            lp_item.setFlags(lp_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, lp_item)

            # Peer Address
            pa_item = QTableWidgetItem(conn["peer_addr"])
            pa_item.setFlags(pa_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 4, pa_item)

            # Peer Port (numeric sort via SortableTableWidgetItem)
            pp_item = SortableTableWidgetItem()
            pp_item.setText(conn["peer_port"])
            try:
                pp_item.setData(Qt.ItemDataRole.UserRole, int(conn["peer_port"]))
            except ValueError:
                pp_item.setData(Qt.ItemDataRole.UserRole, 0)
            pp_item.setFlags(pp_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 5, pp_item)

            # Process
            proc_item = QTableWidgetItem(conn["process"])
            proc_item.setFlags(proc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 6, proc_item)

            # PID (numeric sort via SortableTableWidgetItem)
            pid_item = SortableTableWidgetItem()
            pid_item.setText(conn["pid"])
            try:
                pid_item.setData(Qt.ItemDataRole.UserRole, int(conn["pid"]) if conn["pid"] else 0)
            except ValueError:
                pid_item.setData(Qt.ItemDataRole.UserRole, 0)
            pid_item.setFlags(pid_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 7, pid_item)

            if key == selected_key:
                sel_item = proto_item  # save pointer for sort-safe restoration

        self.table.setSortingEnabled(True)
        self.table.setUpdatesEnabled(True)

        # Restore selection — query row() AFTER setSortingEnabled(True) re-sorts
        if selected_key and sel_item is not None:
            self.table.selectRow(sel_item.row())
        self.table.verticalScrollBar().setValue(scroll_pos)

    def _state_color(self, state):
        if state == "LISTEN":
            return ModernTheme.ACCENT_GREEN
        elif state == "ESTAB":
            return ModernTheme.ACCENT_CYAN
        elif state in ("CLOSE-WAIT", "TIME-WAIT", "FIN-WAIT-1", "FIN-WAIT-2"):
            return ModernTheme.ACCENT_ORANGE
        elif state == "UNCONN":
            return ModernTheme.TEXT_SECONDARY
        return ModernTheme.TEXT_PRIMARY

    def _on_search_changed(self, text):
        self._filter_text = text
        self._populate_table()

    def _on_proto_filter_changed(self, text):
        self._proto_filter = text
        self._populate_table()

    def _on_state_filter_changed(self, text):
        self._state_filter = text
        self._populate_table()

    def _show_context_menu(self, pos):
        """Right-click context menu."""
        # Use itemAt(pos) to target the right-clicked row, not the previously
        # selected row — right-click doesn't auto-select in Qt
        clicked_item = self.table.itemAt(pos)
        if not clicked_item:
            return
        self.table.selectRow(clicked_item.row())
        row = clicked_item.row()

        conn_pid = self.table.item(row, 7)
        pid_text = conn_pid.text() if conn_pid else ""

        menu = QMenu(self)

        # Copy row
        copy_act = menu.addAction("Copy Connection Info")
        copy_act.triggered.connect(lambda: self._copy_row(row))

        if pid_text:
            menu.addSeparator()
            kill_act = menu.addAction(f"Kill Process (PID {pid_text})")
            kill_act.triggered.connect(lambda: self._kill_process(int(pid_text)))

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

    def _copy_row(self, row):
        """Copy connection info to clipboard."""
        parts = []
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                parts.append(item.text())
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText("  ".join(parts))
        self.status_label.setText("Copied to clipboard")

    def _kill_process(self, pid):
        """Kill the owning process (with escalation)."""
        import psutil
        try:
            p = psutil.Process(pid)
            name = p.name()
        except psutil.NoSuchProcess:
            QMessageBox.information(self, "Process Gone", f"PID {pid} no longer exists.")
            return

        reply = QMessageBox.question(
            self, "Kill Process",
            f"Kill {name} (PID {pid})?\nThis will close all connections owned by this process.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            p.terminate()
            p.wait(timeout=2)
            self.status_label.setText(f"Terminated {name} (PID {pid})")
        except psutil.TimeoutExpired:
            try:
                p.kill()
                self.status_label.setText(f"Killed {name} (PID {pid})")
            except psutil.AccessDenied:
                self._escalated_kill(pid, name)
        except psutil.AccessDenied:
            self._escalated_kill(pid, name)

        self._refresh_connections()

    def _escalated_kill(self, pid, name):
        """Kill via pkexec when access is denied."""
        if not shutil.which("pkexec"):
            QMessageBox.critical(self, "Error",
                "pkexec is not installed on this system.\n\n"
                f"You can manually kill this process from a terminal:\n  sudo kill -9 {pid}")
            return
        kill_bin = shutil.which("kill")
        if not kill_bin:
            QMessageBox.critical(self, "Error", "kill command not found.")
            return
        try:
            result = subprocess.run(
                ["pkexec", kill_bin, "-9", str(pid)],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                self.status_label.setText(f"Admin-killed {name} (PID {pid})")
            elif result.returncode in (126, 127):
                self.status_label.setText("Authentication cancelled or denied.")
            else:
                QMessageBox.warning(self, "Kill Failed", result.stderr.strip())
        except subprocess.TimeoutExpired:
            QMessageBox.warning(self, "Timeout", "pkexec timed out.")
