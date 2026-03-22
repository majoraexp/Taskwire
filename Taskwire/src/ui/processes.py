# pylint: disable=E0611
"""
Process list widget: ProcessListWidget.
"""
import subprocess
import shutil

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QAction
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QPushButton, QMessageBox, QLineEdit,
    QMenu, QStackedWidget, QDialog, QCheckBox, QDialogButtonBox
)

from .base import Card, SortableTableWidgetItem, ModernHeader
from ..styles import ModernTheme

class ProcessListWidget(Card):
    """
    A widget to display a list of processes, supporting grouped and detailed views,
    filtering, and sorting. It also provides functionality to terminate processes.
    """
    def __init__(self):
        """
        Initializes the ProcessListWidget.
        """
        super().__init__("Processes")
        self.process_data = [] # Store raw data
        self.view_mode = "grouped" # or "details"
        self.filter_text = ""

        # Sort State
        self.sort_col_id = "mem"
        self.sort_descending = True
        self.auto_sized_views = set()

        # Column Metadata: id -> (Label, Available in Group, Available in Detail)
        self.column_defs = {
            "pid": ("PID", False, True),
            "name": ("Name", True, True),
            "ppid": ("PPID", False, True),
            "count": ("Count", True, False),
            "cpu": ("CPU %", True, True),
            "mem": ("Memory %", True, True),
            "mem_mb": ("Resident (MB)", True, True),
            "mem_shared": ("Shared (MB)", True, True),
            "mem_swap": ("Swap (MB)", True, True),
            "read_bytes": ("Read Bytes", True, True),
            "write_bytes": ("Write Bytes", True, True),
            "threads": ("Threads", True, True),
            "user": ("User", False, True),
            "status": ("Status", False, True)
        }

        # Default Visible Columns
        self.visible_grouped = ["name", "cpu", "mem", "mem_mb", "mem_swap", "count"]
        self.visible_detail = ["pid", "name", "cpu", "mem", "mem_mb", "mem_shared", "mem_swap"]

        # Note: Delegates (ProgressDelegate) were removed to ensure clean text rendering
        # and avoid visual artifacts in the process list. Standard QTableWidgetItem
        # rendering is now used for all columns.

        # Action Bar
        action_layout = QHBoxLayout()

        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search Process...")
        self.search_input.setStyleSheet(
            f"QLineEdit {{"
            f"background-color: {ModernTheme.APP_BACKGROUND};"
            f"color: {ModernTheme.TEXT_PRIMARY};"
            f"border: 1px solid {ModernTheme.BORDER_COLOR};"
            f"border-radius: 5px;"
            f"padding: 5px;"
            f"}}"
        )
        self.search_input.textChanged.connect(self.on_search_changed)
        action_layout.addWidget(self.search_input)

        # View Toggle
        self.view_btn = QPushButton("View: Grouped")
        self.view_btn.setFixedSize(120, 30)
        self.view_btn.setStyleSheet(  # pylint: disable=C0301
            f"QPushButton {{"
            f"background-color: {ModernTheme.WIDGET_BACKGROUND};"
            f"color: {ModernTheme.ACCENT_CYAN};"
            f"border: 1px solid {ModernTheme.ACCENT_CYAN};"
            f"border-radius: 5px;"
            f"font-weight: bold;"
            f"}}"
            f"QPushButton:hover {{"
            f"background-color: {ModernTheme.ACCENT_CYAN};"
            f"color: {ModernTheme.APP_BACKGROUND};"
            f"}}"
        )
        self.view_btn.clicked.connect(self.toggle_view)
        action_layout.addWidget(self.view_btn)

        self.layout.addLayout(action_layout)

        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)

        # View 1: Grouped Overview
        self.group_table = QTableWidget()
        self.setup_table_style(self.group_table)
        self.update_columns("grouped")

        self.group_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.group_table.customContextMenuRequested.connect(self.show_group_context_menu)

        g_header = self.group_table.horizontalHeader()
        g_header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        g_header.customContextMenuRequested.connect(lambda pos: self.show_header_context_menu(pos, "grouped"))
        g_header.sectionClicked.connect(lambda idx: self.on_header_clicked(idx, "grouped"))

        self.stack.addWidget(self.group_table)

        # View 2: Detailed List
        self.detail_table = QTableWidget()
        self.setup_table_style(self.detail_table)
        self.update_columns("details")

        self.detail_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.detail_table.customContextMenuRequested.connect(self.show_detail_context_menu)

        d_header = self.detail_table.horizontalHeader()
        d_header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        d_header.customContextMenuRequested.connect(lambda pos: self.show_header_context_menu(pos, "details"))
        d_header.sectionClicked.connect(lambda idx: self.on_header_clicked(idx, "details"))

        self.stack.addWidget(self.detail_table)

    def refresh_theme(self):
        """Refreshes the widget's colors based on the current ModernTheme."""
        self.apply_table_theme(self.group_table)
        self.apply_table_theme(self.detail_table)

        self.search_input.setStyleSheet(
            f"QLineEdit {{"
            f"background-color: {ModernTheme.APP_BACKGROUND};"
            f"color: {ModernTheme.TEXT_PRIMARY};"
            f"border: 1px solid {ModernTheme.BORDER_COLOR};"
            f"border-radius: 5px;"
            f"padding: 5px;"
            f"}}"
        )

        self.view_btn.setStyleSheet(  # pylint: disable=C0301
            f"QPushButton {{"
            f"background-color: {ModernTheme.WIDGET_BACKGROUND};"
            f"color: {ModernTheme.ACCENT_CYAN};"
            f"border: 1px solid {ModernTheme.ACCENT_CYAN};"
            f"border-radius: 5px;"
            f"font-weight: bold;"
            f"}}"
            f"QPushButton:hover {{"
            f"background-color: {ModernTheme.ACCENT_CYAN};"
            f"color: {ModernTheme.APP_BACKGROUND};"
            f"}}"
        )

    def setup_table_style(self, table):
        """
        Applies common style settings to a QTableWidget, including headers and selection behavior.

        Args:
            table (QTableWidget): The table widget to style.
        """
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setSortingEnabled(False)

        # Set Custom Header
        header = ModernHeader(Qt.Orientation.Horizontal, table)
        table.setHorizontalHeader(header)

        self.apply_table_theme(table)

    def apply_table_theme(self, table):
        """Applies the current theme stylesheet to the table."""
        table.setStyleSheet(
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
                /* Custom paintSection handles the vertical separator */
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

    def update_columns(self, mode):
        """
        Updates the columns displayed in the table based on the specified view mode.

        Args:
            mode (str): The current view mode ('grouped' or 'details').
        """
        table = self.group_table if mode == "grouped" else self.detail_table
        visible = self.visible_grouped if mode == "grouped" else self.visible_detail

        labels = [self.column_defs[col_id][0] for col_id in visible]
        table.setColumnCount(len(labels))
        table.setHorizontalHeaderLabels(labels)



    def update_sort_indicator(self, table, visible_cols):
        """
        Updates the sort indicator on the table header to reflect the current sorting.

        Args:
            table (QTableWidget): The table widget whose header needs updating.
            visible_cols (list): List of currently visible column IDs.
        """
        if self.sort_col_id in visible_cols:
            idx = visible_cols.index(self.sort_col_id)
            order = Qt.SortOrder.DescendingOrder if self.sort_descending else Qt.SortOrder.AscendingOrder
            table.horizontalHeader().setSortIndicatorShown(True)
            table.horizontalHeader().setSortIndicator(idx, order)

    def on_header_clicked(self, logical_index, mode):
        """
        Handles clicks on the table header to change sorting order.

        Args:
            logical_index (int): The logical index of the clicked header section.
            mode (str): The current view mode ('grouped' or 'details').
        """
        visible = self.visible_grouped if mode == "grouped" else self.visible_detail
        if logical_index < len(visible):
            col_id = visible[logical_index]

            if col_id == self.sort_col_id:
                self.sort_descending = not self.sort_descending
            else:
                self.sort_col_id = col_id
                if col_id in ["name", "user", "status", "pid"]:
                    self.sort_descending = False
                else:
                    self.sort_descending = True

            table = self.group_table if mode == "grouped" else self.detail_table

            # Save scroll position
            current_scroll = table.verticalScrollBar().value()

            self.update_sort_indicator(table, visible)
            self.refresh_current_view(maintain_selection=False)

            # Clear selection — row indices changed after sort, restoring
            # the old index would select a different process
            table.clearSelection()

            # Restore scroll position
            table.verticalScrollBar().setValue(current_scroll)

    def show_header_context_menu(self, pos, mode):
        """
        Displays a context menu when the table header is right-clicked.

        Args:
            pos (QPoint): The position where the context menu was requested.
            mode (str): The current view mode ('grouped' or 'details').
        """
        table = self.group_table if mode == "grouped" else self.detail_table

        menu = QMenu(self)
        menu.setStyleSheet(f"background-color: {ModernTheme.WIDGET_BACKGROUND}; color: {ModernTheme.TEXT_PRIMARY}; border: 1px solid {ModernTheme.BORDER_COLOR};")

        customize_action = QAction("Customize Columns...", self)
        customize_action.triggered.connect(lambda: self.open_column_dialog(mode))
        menu.addAction(customize_action)

        menu.exec(table.horizontalHeader().mapToGlobal(pos))

    def open_column_dialog(self, mode):
        """
        Opens a dialog to allow the user to customize visible columns.

        Args:
            mode (str): The current view mode ('grouped' or 'details').
        """
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Select Metrics ({mode.capitalize()})")
        dialog.setStyleSheet(
            f"""
            QDialog {{ background-color: "{ModernTheme.APP_BACKGROUND}"; color: "{ModernTheme.TEXT_PRIMARY}"; }}
            QCheckBox {{ color: "{ModernTheme.TEXT_PRIMARY}"; padding: 5px; }}
            QPushButton {{ background-color: "{ModernTheme.WIDGET_BACKGROUND}"; color: "{ModernTheme.TEXT_PRIMARY}"; border: 1px solid "{ModernTheme.BORDER_COLOR}"; padding: 5px 15px; }}
            """
        )

        layout = QVBoxLayout(dialog)
        checkboxes = {}

        current_visible = self.visible_grouped if mode == "grouped" else self.visible_detail

        # Show all available columns for this mode
        for col_id, (label, allow_group, allow_detail) in self.column_defs.items():  # pylint: disable=C0301  # pylint: disable=C0301
            if mode == "grouped" and not allow_group: continue
            if mode == "details" and not allow_detail: continue

            cb = QCheckBox(label)
            cb.setChecked(col_id in current_visible)
            checkboxes[col_id] = cb
            layout.addWidget(cb)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_visible = []
            # Preserve order based on definition order
            for col_id in self.column_defs:
                if col_id in checkboxes and checkboxes[col_id].isChecked():
                    new_visible.append(col_id)

            if not new_visible:
                QMessageBox.warning(self, "Invalid Selection", "You must select at least one column.")
                return

            if mode == "grouped":
                self.visible_grouped = new_visible
            else:
                self.visible_detail = new_visible

            self.update_columns(mode)
            self.refresh_current_view()

    def on_search_changed(self, text):
        """
        Filters the process list based on the search text.

        Args:
            text (str): The search text entered by the user.
        """
        self.filter_text = text.lower()
        self.refresh_current_view()

    def toggle_view(self):
        """
        Toggles between grouped and detailed views of the process list.
        """
        if self.view_mode == "grouped":
            self.switch_to_details()
        else:
            self.view_mode = "grouped"
            self.view_btn.setText("View: Grouped")
            self.stack.setCurrentIndex(0)
            self.refresh_current_view()

    def switch_to_details(self, filter_name=None):
        """
        Switches the view to detailed mode, optionally filtering by process name.

        Args:
            filter_name (str, optional): A process name to pre-fill the search bar with.
                                         Defaults to None.
        """
        self.view_mode = "details"
        self.view_btn.setText("View: Details")
        self.stack.setCurrentIndex(1)
        if filter_name:
            self.search_input.setText(filter_name)
        self.refresh_current_view()

    def update_data(self, process_list):
        """
        Updates the internal process data and refreshes the current view.

        Args:
            process_list (list): A list of dictionaries, each representing a process.
        """
        self.process_data = process_list
        self.refresh_current_view()

    def refresh_current_view(self, maintain_selection=True):
        """
        Refreshes the currently active table view (grouped or detailed) with the latest data.

        Args:
            maintain_selection (bool): Whether to preserve selection of specific items.
        """
        if self.view_mode == "grouped":
            self.update_grouped_table(maintain_selection)
        else:
            self.update_detail_table(maintain_selection)

    def get_sort_key(self, data_dict):
        """Helper to extract sort value from a data dictionary (flat or grouped)"""
        col = self.sort_col_id

        # Direct key access if available (Grouped stats usually have keys matching col_id)
        if col in data_dict:
            return data_dict[col]

        # Fallback for Detail/Raw Process objects where structure differs
        if col == "pid":
            pid = data_dict.get('pid', 0)
            if isinstance(pid, str):
                return 999999  # Sort summary last
            return pid
        if col == "ppid": return data_dict.get('ppid', 0)
        if col == "cpu": return data_dict.get('cpu_percent', 0.0)
        if col == "mem": return data_dict.get('memory_percent', 0.0)
        if col == "mem_mb":
            m = data_dict.get('memory_info')
            return m.rss if m else 0
        if col == "mem_shared": return data_dict.get('mem_shared', 0)
        if col == "mem_swap": return data_dict.get('mem_swap', 0)
        if col == "read_bytes":
            io = data_dict.get('io_counters')
            return io.read_bytes if io else 0
        if col == "write_bytes":
            io = data_dict.get('io_counters')
            return io.write_bytes if io else 0
        if col == "threads": return data_dict.get('num_threads', 0)
        if col == "user": return data_dict.get('username', "")
        if col == "status": return data_dict.get('status', "")

        return 0

    def update_grouped_table(self, maintain_selection=True):
        """
        Aggregates process data and populates the grouped view table.

        Args:
            maintain_selection (bool): Whether to preserve selection.
        """
        # 1. Aggregate Data
        groups = {}

        def init_stats():
            return {
                'count': 0, 'cpu_percent': 0.0, 'memory_percent': 0.0,
                'num_threads': 0, 'read_bytes': 0, 'write_bytes': 0,
                'rss': 0, 'shared': 0, 'swap': 0
            }

        for p in self.process_data:
            name = p['name']
            if self.filter_text and self.filter_text not in name.lower():
                continue

            if name not in groups:
                groups[name] = init_stats()

            s = groups[name]
            s['count'] += 1
            if p.get('cpu_percent'): s['cpu_percent'] += p['cpu_percent']
            if p.get('memory_percent'): s['memory_percent'] += p['memory_percent']
            if p.get('num_threads'): s['num_threads'] += p['num_threads']

            mem = p.get('memory_info')
            if mem:
                # Use PSS if available, else RSS
                val = getattr(mem, 'pss', mem.rss)
                s['rss'] += val
                s['shared'] += getattr(mem, 'shared', 0)

            s['swap'] += p.get('mem_swap', 0)

            io = p.get('io_counters')
            if io:
                s['read_bytes'] += io.read_bytes
                s['write_bytes'] += io.write_bytes

        # 2. Format for Table (Flatten first)
        display_data = []
        for name, stats in groups.items():
            row_data = {
                'name': name,
                'count': stats['count'],
                'cpu_percent': stats['cpu_percent'],
                'memory_percent': stats['memory_percent'],
                'num_threads': stats['num_threads'],
                'mem_mb': stats['rss'], # Reuse RSS for MB column
                'mem_shared': stats['shared'],
                'mem_swap': stats['swap'],
                'read_bytes': stats['read_bytes'],
                'write_bytes': stats['write_bytes']
            }
            display_data.append(row_data)

        # 3. Sort
        display_data.sort(key=lambda x: self.get_sort_key(x), reverse=self.sort_descending)

        self.render_table(self.group_table, display_data, self.visible_grouped, maintain_selection)

    def update_detail_table(self, maintain_selection=True):
        """
        Filters and populates the detailed view table with process data.

        Args:
            maintain_selection (bool): Whether to preserve selection.
        """
        filtered = [p for p in self.process_data if not self.filter_text or self.filter_text in p['name'].lower()]

        # Sort
        filtered.sort(key=lambda x: self.get_sort_key(x), reverse=self.sort_descending)

        self.render_table(self.detail_table, filtered, self.visible_detail, maintain_selection)

    def render_table(self, table, data, visible_cols, maintain_selection=True):
        """
        Renders data into a given QTableWidget with specified visible columns.

        Args:
            table (QTableWidget): The table widget to render into.
            data (list): A list of dictionaries, each representing a row of data.
            visible_cols (list): A list of column IDs to display.
            maintain_selection (bool): Whether to attempt to preserve selection of specific items (by PID/Name)
                                       across updates. Defaults to True.
        """
        def format_bytes(b):
            if b is None: return "0 B"
            if b > 1024**3: return f"{b/1024**3:.1f} GiB"
            if b > 1024**2: return f"{b/1024**2:.1f} MiB"
            if b > 1024: return f"{b/1024:.1f} KiB"
            return f"{b} B"

        # Save Scroll Position
        current_scroll = table.verticalScrollBar().value()

        selected_val = None
        key_col_idx = -1

        if maintain_selection:
            key_id = "pid" if "pid" in visible_cols else "name"
            if key_id in visible_cols:
                key_col_idx = visible_cols.index(key_id)

            selected_items = table.selectedItems()
            if selected_items and key_col_idx != -1:
                row = selected_items[0].row()
                item = table.item(row, key_col_idx)
                if item:
                    selected_val = item.data(Qt.ItemDataRole.DisplayRole)

        table.setRowCount(len(data))

        found_selection = False

        for row, p in enumerate(data):
            for col_idx, col_id in enumerate(visible_cols):
                item = SortableTableWidgetItem()

                val = None
                display = ""

                if col_id == "pid":
                    val = p.get('pid')
                    display = str(val)
                elif col_id == "name":
                    val = p.get('name')
                    display = str(val)
                elif col_id == "ppid":
                    val = p.get('ppid', 0)
                    display = str(val)
                elif col_id == "count":
                    val = p.get('count', 1)
                    display = str(val)
                elif col_id == "cpu":
                    val = p.get('cpu_percent', 0.0)
                    display = f"{val:.1f}%"
                elif col_id == "mem":
                    val = p.get('memory_percent', 0.0)
                    display = f"{val:.1f}%"
                elif col_id == "mem_mb":
                    if 'mem_mb' in p: val = p['mem_mb']
                    else:
                        mem = p.get('memory_info')
                        val = mem.rss if mem else 0
                    display = format_bytes(val)
                elif col_id == "mem_shared":
                    val = p.get('mem_shared', 0)
                    display = format_bytes(val)
                elif col_id == "mem_swap":
                    val = p.get('mem_swap', 0)
                    display = format_bytes(val)
                elif col_id == "read_bytes":
                    if 'read_bytes' in p: val = p['read_bytes']
                    else:
                        io = p.get('io_counters')
                        val = io.read_bytes if io else 0
                    display = format_bytes(val)
                elif col_id == "write_bytes":
                    if 'write_bytes' in p: val = p['write_bytes']
                    else:
                        io = p.get('io_counters')
                        val = io.write_bytes if io else 0
                    display = format_bytes(val)
                elif col_id == "threads":
                    val = p.get('num_threads', 0)
                    display = str(val)
                elif col_id == "user":
                    val = p.get('username', '')
                    display = str(val)
                elif col_id == "status":
                    val = p.get('status', '')
                    display = str(val)

                item.setData(Qt.ItemDataRole.UserRole, val) # For sorting
                item.setText(display)

                # Align Name Left, others Center
                if col_id == "name":
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                table.setItem(row, col_idx, item)

            if selected_val is not None and key_col_idx != -1:
                key_item = table.item(row, key_col_idx)
                if key_item and key_item.data(Qt.ItemDataRole.DisplayRole) == selected_val:
                    table.selectRow(row)
                    found_selection = True

        if not found_selection:
            table.clearSelection()

        # Auto-size columns once per view
        mode = "grouped" if table == self.group_table else "details"
        if mode not in self.auto_sized_views and len(data) > 0:
            table.resizeColumnsToContents()
            self.auto_sized_views.add(mode)

        # Restore Scroll Position
        table.verticalScrollBar().setValue(current_scroll)

    def show_group_context_menu(self, pos):
        """
        Displays a context menu for grouped process entries.

        Args:
            pos (QPoint): The position where the context menu was requested.
        """
        item = self.group_table.itemAt(pos)
        if not item: return

        row = item.row()
        if "name" not in self.visible_grouped: return
        name_idx = self.visible_grouped.index("name")
        name = self.group_table.item(row, name_idx).text()

        menu = QMenu(self)
        menu.setStyleSheet(f"background-color: {ModernTheme.WIDGET_BACKGROUND}; color: {ModernTheme.TEXT_PRIMARY}; border: 1px solid {ModernTheme.BORDER_COLOR};")

        details_action = QAction(f"Show Details for '{name}'", self)
        details_action.triggered.connect(lambda: self.switch_to_details(name))
        menu.addAction(details_action)

        menu.addSeparator()

        end_task_action = QAction("End Task (All Instances)", self)
        end_task_action.triggered.connect(lambda: self.kill_group(name))
        menu.addAction(end_task_action)

        force_kill_action = QAction("Force Kill (Admin)", self)
        force_kill_action.triggered.connect(lambda: self.force_kill_group(name))
        menu.addAction(force_kill_action)

        menu.exec(self.group_table.viewport().mapToGlobal(pos))

    def show_detail_context_menu(self, pos):
        """
        Displays a context menu for detailed process entries.

        Args:
            pos (QPoint): The position where the context menu was requested.
        """
        item = self.detail_table.itemAt(pos)
        if not item: return

        row = item.row()

        pid = -1
        name = "Unknown"

        if "pid" in self.visible_detail:
            pid_idx = self.visible_detail.index("pid")
            pid = int(self.detail_table.item(row, pid_idx).data(Qt.ItemDataRole.DisplayRole))
        if "name" in self.visible_detail:
            name_idx = self.visible_detail.index("name")
            name = self.detail_table.item(row, name_idx).text()

        if pid == -1: return

        menu = QMenu(self)
        menu.setStyleSheet(f"background-color: {ModernTheme.WIDGET_BACKGROUND}; color: {ModernTheme.TEXT_PRIMARY}; border: 1px solid {ModernTheme.BORDER_COLOR};")

        end_proc_action = QAction(f"End Process ({pid})", self)
        end_proc_action.triggered.connect(lambda: self.kill_process(pid, name))
        menu.addAction(end_proc_action)

        end_tree_action = QAction("End Process Tree", self)
        end_tree_action.triggered.connect(lambda: self.kill_process_tree(pid, name))
        menu.addAction(end_tree_action)

        menu.addSeparator()

        force_kill_action = QAction("Force Kill (Admin)", self)
        force_kill_action.triggered.connect(lambda: self.force_kill_process(pid, name))
        menu.addAction(force_kill_action)

        menu.exec(self.detail_table.viewport().mapToGlobal(pos))

    def kill_process(self, pid, name):
        """
        Prompts for confirmation and attempts to terminate a single process.

        Args:
            pid (int): The PID of the process to terminate.
            name (str): The name of the process for display in the confirmation dialog.
        """
        confirm = QMessageBox.question(self, "Confirm End Process",
                                     f"Are you sure you want to end process '{name}' (PID: {pid})?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self._kill_pid(pid)

    def kill_process_tree(self, pid, name):
        """
        Prompts for confirmation and attempts to terminate a process and all its children.
        Collects any AccessDenied PIDs and offers a single batched pkexec escalation.

        Args:
            pid (int): The PID of the parent process to terminate.
            name (str): The name of the parent process for display in the confirmation dialog.
        """
        confirm = QMessageBox.question(self, "Confirm End Tree",
                                     f"Are you sure you want to end the process tree for '{name}' (PID: {pid})?\nThis will terminate the process and all its children.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            import psutil
            try:
                parent = psutil.Process(pid)
                all_pids = [child.pid for child in parent.children(recursive=True)] + [pid]
            except psutil.NoSuchProcess:
                QMessageBox.warning(self, "Error", "Process no longer exists.")
                return
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to kill tree: {e}")
                return

            killed = 0
            denied_pids = []
            for p in all_pids:
                try:
                    proc = psutil.Process(p)
                    proc.terminate()
                    try:
                        proc.wait(timeout=1.5)
                    except psutil.TimeoutExpired:
                        proc.kill()
                    killed += 1
                except psutil.NoSuchProcess:
                    pass
                except psutil.AccessDenied:
                    denied_pids.append(int(p))
                except Exception:
                    pass

            if denied_pids:
                escalate = QMessageBox.question(
                    self, "Access Denied",
                    f"Terminated {killed} process(es) in tree, but {len(denied_pids)} require admin privileges.\n\n"
                    "Do you want to force kill them as admin?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if escalate == QMessageBox.StandardButton.Yes:
                    if self._force_kill_pids(denied_pids):
                        killed += len(denied_pids)

            QMessageBox.information(self, "Success", f"Process tree for '{name}' terminated ({killed} processes).")

    def kill_group(self, name):
        """
        Prompts for confirmation and attempts to terminate all processes with a given name.
        Collects any AccessDenied PIDs and offers a single batched pkexec escalation.

        Args:
            name (str): The name of the processes to terminate.
        """
        confirm = QMessageBox.question(self, "Confirm End Group",
                                     f"Are you sure you want to end ALL processes named '{name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            import psutil
            killed = 0
            denied_pids = []
            for p in self.process_data:
                if p['name'] == name:
                    try:
                        proc = psutil.Process(p['pid'])
                        proc.terminate()
                        try:
                            proc.wait(timeout=1.5)
                        except psutil.TimeoutExpired:
                            proc.kill()
                        killed += 1
                    except psutil.NoSuchProcess:
                        pass
                    except psutil.AccessDenied:
                        denied_pids.append(int(p['pid']))
                    except Exception:
                        pass

            if denied_pids:
                escalate = QMessageBox.question(
                    self, "Access Denied",
                    f"Terminated {killed} process(es), but {len(denied_pids)} require admin privileges.\n\n"
                    "Do you want to force kill them as admin?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if escalate == QMessageBox.StandardButton.Yes:
                    if self._force_kill_pids(denied_pids):
                        killed += len(denied_pids)
            QMessageBox.information(self, "Success", f"Terminated {killed} instances of '{name}'.")

    def force_kill_process(self, pid, name):
        """
        Prompts for confirmation and force kills a single process via pkexec.

        Args:
            pid (int): The PID of the process to force kill.
            name (str): The name of the process for the confirmation dialog.
        """
        confirm = QMessageBox.question(
            self, "Confirm Force Kill",
            f"Are you sure you want to force kill '{name}' (PID: {pid}) as admin?\n\n"
            "This will prompt for your password and send SIGKILL.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self._force_kill_pid(int(pid))

    def force_kill_group(self, name):
        """
        Prompts for confirmation and force kills all processes with a given name via pkexec.
        Batches all PIDs into a single pkexec call so the user only authenticates once.

        Args:
            name (str): The name of the processes to force kill.
        """
        pids = [int(p['pid']) for p in self.process_data if p['name'] == name]
        if not pids:
            QMessageBox.warning(self, "Error", f"No processes named '{name}' found.")
            return

        confirm = QMessageBox.question(
            self, "Confirm Force Kill Group",
            f"Are you sure you want to force kill ALL {len(pids)} processes named '{name}' as admin?\n\n"
            "This will prompt for your password.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self._force_kill_pids(pids)

    def _kill_pid(self, pid, silent=False):
        """
        Attempts to terminate a process by its PID with escalation.

        Escalation order:
        1. SIGTERM (graceful)
        2. SIGKILL after 1.5s timeout (forceful)
        3. On AccessDenied, prompt user for admin kill via pkexec

        Args:
            pid (int): The PID of the process to terminate.
            silent (bool): If True, suppresses QMessageBox pop-ups for success/failure.
                           Defaults to False.
        """
        import psutil
        try:
            p = psutil.Process(pid)
            p.terminate()
            try:
                p.wait(timeout=1.5)
            except psutil.TimeoutExpired:
                p.kill()
            if not silent:
                QMessageBox.information(self, "Success", f"Process {pid} terminated.")
        except psutil.NoSuchProcess:
            if not silent: QMessageBox.warning(self, "Error", "Process no longer exists.")
        except psutil.AccessDenied:
            if not silent:
                confirm = QMessageBox.question(
                    self, "Access Denied",
                    f"Process {pid} requires administrator privileges to terminate.\n\n"
                    "Do you want to force kill it as admin?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if confirm == QMessageBox.StandardButton.Yes:
                    self._force_kill_pid(int(pid))
        except Exception as e:
            if not silent: QMessageBox.critical(self, "Error", f"Could not terminate: {e}")

    def _force_kill_pid(self, pid, silent=False):
        """
        Force kills a single process using pkexec for privilege escalation.

        Args:
            pid (int): The PID of the process to kill.
            silent (bool): If True, suppresses QMessageBox pop-ups.

        Returns:
            bool: True if the process was successfully killed, False otherwise.
        """
        return self._force_kill_pids([int(pid)], silent=silent)

    def _force_kill_pids(self, pids, silent=False):
        """
        Force kills one or more processes using a single pkexec call.
        Batches all PIDs into one command so the user only authenticates once.

        Args:
            pids (list[int]): List of PIDs to kill.
            silent (bool): If True, suppresses QMessageBox pop-ups.

        Returns:
            bool: True if pkexec returned success, False otherwise.
        """
        if not pids:
            return False

        pids = [int(p) for p in pids]

        if not shutil.which("pkexec"):
            if not silent:
                QMessageBox.critical(
                    self, "Error",
                    "pkexec is not installed on this system.\n\n"
                    "You can manually kill these processes from a terminal:\n"
                    f"  sudo kill -9 {' '.join(str(p) for p in pids)}")
            return False

        kill_bin = shutil.which("kill") or "/usr/bin/kill"

        try:
            result = subprocess.run(
                ["pkexec", kill_bin, "-9"] + [str(p) for p in pids],
                capture_output=True, timeout=60)

            if result.returncode == 0:
                if not silent:
                    QMessageBox.information(self, "Success",
                        f"Force killed {len(pids)} process(es).")
                return True
            elif result.returncode == 126:
                return False  # User dismissed the password dialog
            elif result.returncode == 127:
                if not silent:
                    QMessageBox.warning(self, "Error", "Authentication was not granted.")
                return False
            else:
                stderr = result.stderr.decode().strip()
                if "No such process" in stderr or "no process found" in stderr.lower():
                    if not silent:
                        QMessageBox.warning(self, "Error", "Process no longer exists.")
                elif not silent:
                    QMessageBox.critical(
                        self, "Error", f"Failed to kill process(es).\n{stderr}")
                return False
        except subprocess.TimeoutExpired:
            if not silent:
                QMessageBox.warning(self, "Timeout", "The authentication dialog timed out.")
            return False
        except Exception as e:
            if not silent:
                QMessageBox.critical(self, "Error", f"Failed to force kill: {e}")
            return False

    # Kept for compatibility if called externally, though not used by internal buttons anymore
    def kill_selected_process(self):
        """
        Kept for compatibility if called externally, though not used by internal buttons anymore.
        """
        pass
