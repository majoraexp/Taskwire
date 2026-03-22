# pylint: disable=E0611
"""
Live system log viewer: JournalLogWidget.
"""
import subprocess
import shutil

from PyQt6.QtCore import Qt, QTimer, QProcess
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QMessageBox, QLineEdit,
    QPlainTextEdit, QComboBox, QFileDialog
)

from ..styles import ModernTheme


class JournalLogWidget(QWidget):
    """
    Live system log viewer using journalctl.
    Streams logs in real-time via QProcess, with filtering by severity,
    unit/service, boot, and text search with highlighting.
    """

    # journalctl priority levels (0=most severe)
    _PRIORITIES = [
        ("All", None),
        ("Emergency", "0"),
        ("Alert", "1"),
        ("Critical", "2"),
        ("Error", "3"),
        ("Warning", "4"),
        ("Notice", "5"),
        ("Info", "6"),
        ("Debug", "7"),
    ]

    # Colors for each priority level
    _PRIORITY_COLORS = {
        "0": "ACCENT_RED",      # emergency
        "1": "ACCENT_RED",      # alert
        "2": "ACCENT_RED",      # critical
        "3": "ACCENT_RED",      # error
        "4": "ACCENT_ORANGE",   # warning
        "5": "ACCENT_CYAN",     # notice
        "6": "ACCENT_GREEN",    # info
        "7": "TEXT_SECONDARY",  # debug
    }

    def __init__(self):
        super().__init__()
        self._has_journalctl = shutil.which("journalctl") is not None
        self._process = None
        self._line_buffer = []       # lines waiting to be flushed
        self._partial_line = ""      # incomplete line from QProcess reads
        self._auto_scroll = True
        self._paused = False
        self._current_search = ""
        self._max_lines = 5000
        self._boots = []             # list of (boot_id, boot_index) from --list-boots

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Header
        header = QLabel("System Logs")
        header.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {ModernTheme.ACCENT_CYAN};")
        main_layout.addWidget(header)

        if not self._has_journalctl:
            msg = QLabel("journalctl not found — systemd journal is not available on this system.")
            msg.setStyleSheet(f"font-size: 16px; color: {ModernTheme.ACCENT_RED};")
            main_layout.addWidget(msg)
            main_layout.addStretch()
            return

        # --- Toolbar Row 1: Filters ---
        toolbar1 = QHBoxLayout()

        # Severity filter
        sev_label = QLabel("Priority:")
        sev_label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY}; font-weight: bold;")
        toolbar1.addWidget(sev_label)
        self.severity_combo = QComboBox()
        for label, _ in self._PRIORITIES:
            self.severity_combo.addItem(label)
        self.severity_combo.setFixedWidth(160)
        self.severity_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar1.addWidget(self.severity_combo)

        # Unit filter
        unit_label = QLabel("Unit:")
        unit_label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY}; font-weight: bold;")
        toolbar1.addWidget(unit_label)
        self.unit_input = QLineEdit()
        self.unit_input.setPlaceholderText("e.g. docker.service, sshd...")
        self._apply_input_style(self.unit_input)
        self.unit_input.setFixedWidth(220)
        self.unit_input.editingFinished.connect(self._on_filter_changed)
        toolbar1.addWidget(self.unit_input)

        # Boot selector
        boot_label = QLabel("Boot:")
        boot_label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY}; font-weight: bold;")
        toolbar1.addWidget(boot_label)
        self.boot_combo = QComboBox()
        self.boot_combo.setFixedWidth(180)
        self.boot_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar1.addWidget(self.boot_combo)

        toolbar1.addStretch()
        main_layout.addLayout(toolbar1)

        # --- Toolbar Row 2: Search + Controls ---
        toolbar2 = QHBoxLayout()

        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search logs...")
        self._apply_input_style(self.search_input)
        self.search_input.textChanged.connect(self._on_search_changed)
        toolbar2.addWidget(self.search_input, 1)

        # Button style
        btn_style = self._get_btn_style()

        # Pause/Resume
        self.btn_pause = QPushButton("Pause")
        self.btn_pause.setStyleSheet(btn_style)
        self.btn_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pause.setCheckable(True)
        self.btn_pause.clicked.connect(self._toggle_pause)
        toolbar2.addWidget(self.btn_pause)

        # Word wrap toggle
        self.btn_wrap = QPushButton("Wrap")
        self.btn_wrap.setStyleSheet(btn_style)
        self.btn_wrap.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_wrap.setCheckable(True)
        self.btn_wrap.setChecked(True)
        self.btn_wrap.clicked.connect(self._toggle_wrap)
        toolbar2.addWidget(self.btn_wrap)

        # Clear
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setStyleSheet(btn_style)
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.clicked.connect(self._clear_logs)
        toolbar2.addWidget(self.btn_clear)

        # Jump to bottom
        self.btn_bottom = QPushButton("Bottom")
        self.btn_bottom.setStyleSheet(btn_style)
        self.btn_bottom.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_bottom.clicked.connect(self._jump_to_bottom)
        toolbar2.addWidget(self.btn_bottom)

        # Export
        self.btn_export = QPushButton("Export")
        self.btn_export.setStyleSheet(btn_style)
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.setToolTip("Save current logs to a file")
        self.btn_export.clicked.connect(self._export_logs)
        toolbar2.addWidget(self.btn_export)

        main_layout.addLayout(toolbar2)

        # --- Log Output ---
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(self._max_lines)
        self.log_view.setUndoRedoEnabled(False)
        self.log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._apply_log_style()

        # Auto-scroll detection: when user scrolls up, pause auto-scroll
        self.log_view.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)

        main_layout.addWidget(self.log_view)

        # --- Status Bar ---
        status_row = QHBoxLayout()
        self.status_label = QLabel("Starting...")
        self.status_label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY}; font-size: 12px;")
        status_row.addWidget(self.status_label)

        self.line_count_label = QLabel("0 lines")
        self.line_count_label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY}; font-size: 12px;")
        self.line_count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        status_row.addWidget(self.line_count_label)

        main_layout.addLayout(status_row)

        # --- Flush timer (batch appends at 100ms) ---
        self._flush_timer = QTimer(self)
        self._flush_timer.timeout.connect(self._flush_buffer)
        self._flush_timer.start(100)

        # --- Search debounce timer (200ms) ---
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_search)

        # --- Populate boots and start ---
        self._load_boots()
        self._start_journalctl()

    def _get_btn_style(self):
        return (
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
            f"QPushButton:checked {{"
            f"background-color: {ModernTheme.ACCENT_PURPLE};"
            f"color: {ModernTheme.APP_BACKGROUND};"
            f"}}"
        )

    def _apply_input_style(self, widget):
        widget.setStyleSheet(
            f"QLineEdit {{"
            f"background-color: {ModernTheme.APP_BACKGROUND};"
            f"color: {ModernTheme.TEXT_PRIMARY};"
            f"border: 1px solid {ModernTheme.BORDER_COLOR};"
            f"border-radius: 5px;"
            f"padding: 5px;"
            f"}}"
        )

    def _apply_log_style(self):
        self.log_view.setStyleSheet(
            f"QPlainTextEdit {{"
            f"background-color: {ModernTheme.APP_BACKGROUND};"
            f"color: {ModernTheme.TEXT_PRIMARY};"
            f"font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;"
            f"font-size: 12px;"
            f"border: 1px solid {ModernTheme.BORDER_COLOR};"
            f"border-radius: 5px;"
            f"padding: 5px;"
            f"}}"
        )

    def refresh_theme(self):
        """Refresh all styles on theme change."""
        if not self._has_journalctl:
            return
        self._apply_input_style(self.search_input)
        self._apply_input_style(self.unit_input)
        self._apply_log_style()
        btn_style = self._get_btn_style()
        for btn in (self.btn_pause, self.btn_wrap, self.btn_clear, self.btn_bottom, self.btn_export):
            btn.setStyleSheet(btn_style)
        self.status_label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY}; font-size: 12px;")
        self.line_count_label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY}; font-size: 12px;")
        # Reapply severity colors to existing text (baked-in QTextCharFormat
        # doesn't update automatically when theme colors change)
        self._reapply_theme_to_document()
        # Re-highlight search matches with new theme colors
        if self._current_search:
            self._highlight_search(self._current_search)

    def _reapply_theme_to_document(self):
        """Walk all existing blocks and reapply severity colors for new theme."""
        doc = self.log_view.document()
        if not doc or doc.blockCount() <= 1:
            return
        cursor = self.log_view.textCursor()
        cursor.beginEditBlock()
        block = doc.begin()
        while block.isValid():
            text = block.text()
            if text:
                block_cursor = self.log_view.textCursor()
                block_cursor.setPosition(block.position())
                block_cursor.movePosition(block_cursor.MoveOperation.EndOfBlock,
                                          block_cursor.MoveMode.KeepAnchor)
                fmt = block_cursor.charFormat()
                fmt.setForeground(QColor(self._detect_line_color(text)))
                block_cursor.setCharFormat(fmt)
            block = block.next()
        cursor.endEditBlock()

    # --- Boot Management ---

    def _load_boots(self):
        """Populate boot selector from journalctl --list-boots."""
        try:
            result = subprocess.run(
                ["journalctl", "--list-boots", "--no-pager"],
                capture_output=True, text=True, timeout=10
            )
            self._boots = []
            self.boot_combo.blockSignals(True)
            self.boot_combo.clear()
            self.boot_combo.addItem("Current Boot", "0")

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    parts = line.split()
                    if len(parts) >= 2:
                        idx = parts[0]
                        boot_id = parts[1]
                        if idx != "0":
                            short_id = boot_id[:12]
                            self.boot_combo.addItem(f"Boot {idx} ({short_id}...)", idx)
                            self._boots.append((boot_id, idx))

            self.boot_combo.blockSignals(False)
        except Exception:
            self.boot_combo.blockSignals(True)
            self.boot_combo.clear()
            self.boot_combo.addItem("Current Boot", "0")
            self.boot_combo.blockSignals(False)

    # --- QProcess Management ---

    def _build_command(self):
        """Build the journalctl command args based on current filters."""
        args = [
            "--follow",
            "--no-pager",
            "--output=short-precise",
            "--no-hostname",
            "-n", "200",
        ]

        # Boot
        boot_idx = self.boot_combo.currentData()
        if boot_idx is not None:
            args.extend(["-b", str(boot_idx)])

        # Priority
        sev_idx = self.severity_combo.currentIndex()
        if sev_idx > 0:
            _, priority = self._PRIORITIES[sev_idx]
            if priority is not None:
                args.extend(["-p", priority])

        # Unit
        unit_text = self.unit_input.text().strip()
        if unit_text:
            for unit in unit_text.split(","):
                u = unit.strip()
                if u:
                    args.extend(["-u", u])

        return args

    def _start_journalctl(self):
        """Start (or restart) the journalctl QProcess."""
        self._stop_journalctl()
        self._partial_line = ""

        journalctl_bin = shutil.which("journalctl")
        if not journalctl_bin:
            self.status_label.setText("journalctl not found")
            return

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_stdout_ready)
        self._process.errorOccurred.connect(self._on_process_error)
        self._process.finished.connect(self._on_process_finished)

        args = self._build_command()
        self._process.start(journalctl_bin, args)

        self.status_label.setText("Streaming...")
        self._paused = False
        self.btn_pause.setChecked(False)
        self.btn_pause.setText("Pause")

    def _stop_journalctl(self):
        """Stop the running QProcess if any."""
        if self._process is not None:
            self._process.readyReadStandardOutput.disconnect()
            try:
                self._process.errorOccurred.disconnect()
            except TypeError:
                pass
            try:
                self._process.finished.disconnect()
            except TypeError:
                pass
            if self._process.state() != QProcess.ProcessState.NotRunning:
                self._process.kill()
                self._process.waitForFinished(3000)
            self._process.deleteLater()
            self._process = None

    def _on_stdout_ready(self):
        """Read available output and buffer complete lines."""
        if self._process is None:
            return
        data = self._process.readAllStandardOutput()
        if not data:
            return

        self._partial_line += bytes(data).decode("utf-8", errors="replace")

        if "\n" in self._partial_line:
            parts = self._partial_line.split("\n")
            # All parts except the last are complete lines
            for i in range(len(parts) - 1):
                self._line_buffer.append(parts[i])
            # Last part is the next incomplete line (or empty)
            self._partial_line = parts[-1]

        # Cap buffer to prevent unbounded memory growth (regardless of pause state)
        if len(self._line_buffer) > 10000:
            excess = len(self._line_buffer) - 10000
            if self._paused:
                self._pause_dropped = getattr(self, '_pause_dropped', 0) + excess
            self._line_buffer = self._line_buffer[-10000:]

    def _on_process_error(self, error):
        """Handle QProcess errors."""
        error_map = {
            QProcess.ProcessError.FailedToStart: "Failed to start journalctl",
            QProcess.ProcessError.Crashed: "journalctl process crashed",
            QProcess.ProcessError.Timedout: "journalctl timed out",
            QProcess.ProcessError.WriteError: "Write error",
            QProcess.ProcessError.ReadError: "Read error",
        }
        msg = error_map.get(error, f"Unknown error ({error})")

        # Check for permission issues
        if error == QProcess.ProcessError.FailedToStart:
            msg += " — you may need to be in the 'systemd-journal' group"

        self.status_label.setText(msg)

    def _on_process_finished(self, exit_code, _exit_status):
        """Handle process termination — any exit is unexpected for --follow."""
        if exit_code == 0:
            self.status_label.setText("journalctl exited unexpectedly")
        else:
            self.status_label.setText(f"journalctl exited with code {exit_code}")

    # --- Buffer Flush & Display ---

    def _flush_buffer(self):
        """Append buffered lines to the log view (called every 100ms)."""
        if not self._line_buffer or self._paused:
            return

        lines = self._line_buffer
        self._line_buffer = []

        # Detect severity from short-precise format and colorize
        cursor = self.log_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        for line in lines:
            color = self._detect_line_color(line)
            fmt = cursor.charFormat()
            fmt.setForeground(QColor(color))
            cursor.setCharFormat(fmt)
            cursor.insertText(line + "\n")

        # Update line count
        block_count = self.log_view.document().blockCount()
        self.line_count_label.setText(f"{block_count} lines")

        # Auto-scroll
        if self._auto_scroll:
            self.log_view.verticalScrollBar().setValue(
                self.log_view.verticalScrollBar().maximum()
            )

    def _detect_line_color(self, line):
        """Detect severity from journalctl short-precise output and return color."""
        # short-precise format: "Mar 14 22:30:01.123456 hostname kernel: ..."
        # After hostname, the identifier may contain severity hints
        # A more reliable approach: check for common patterns
        line_lower = line.lower()

        # Check for severity keywords in the line
        if any(k in line_lower for k in ("emerg", "panic")):
            return getattr(ModernTheme, "ACCENT_RED")
        elif any(k in line_lower for k in ("alert",)):
            # Be careful — "alert" can appear in normal text
            # Only match if it looks like a syslog-style priority marker
            if "alert" in line_lower.split(":")[0] if ":" in line_lower else False:
                return getattr(ModernTheme, "ACCENT_RED")
        if any(k in line_lower for k in (" crit:", " critical:", " crit[")):
            return getattr(ModernTheme, "ACCENT_RED")
        elif any(k in line_lower for k in (" err:", " error:", " error[", " err[")):
            return getattr(ModernTheme, "ACCENT_RED")
        elif any(k in line_lower for k in (" warn:", " warning:", " warn[", " warning[")):
            return getattr(ModernTheme, "ACCENT_ORANGE")
        elif any(k in line_lower for k in (" notice:", " notice[")):
            return getattr(ModernTheme, "ACCENT_CYAN")
        elif any(k in line_lower for k in (" debug:", " debug[")):
            return getattr(ModernTheme, "TEXT_SECONDARY")
        # Kernel messages often have severity
        if "kernel:" in line_lower:
            if any(k in line_lower for k in ("error", "fail", "critical", "panic", "oops")):
                return getattr(ModernTheme, "ACCENT_RED")
            elif "warn" in line_lower:
                return getattr(ModernTheme, "ACCENT_ORANGE")

        return getattr(ModernTheme, "TEXT_PRIMARY")

    # --- Scroll Management ---

    def _on_scroll_changed(self, value):
        """Detect when user scrolls away from bottom."""
        scrollbar = self.log_view.verticalScrollBar()
        # If user is within 5 lines of bottom, re-enable auto-scroll
        at_bottom = value >= scrollbar.maximum() - 50
        self._auto_scroll = at_bottom

    def _jump_to_bottom(self):
        """Scroll to bottom and re-enable auto-scroll."""
        self._auto_scroll = True
        self.log_view.verticalScrollBar().setValue(
            self.log_view.verticalScrollBar().maximum()
        )

    # --- Controls ---

    def _toggle_pause(self, checked):
        """Pause or resume log streaming."""
        self._paused = checked
        if checked:
            self.btn_pause.setText("Resume")
            self.status_label.setText("Paused")
        else:
            self.btn_pause.setText("Pause")
            self.status_label.setText("Streaming...")
            # Flush any lines that accumulated while paused
            self._flush_buffer()

    def _toggle_wrap(self, checked):
        """Toggle word wrap on the log view."""
        if checked:
            self.log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        else:
            self.log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

    def _clear_logs(self):
        """Clear the log view."""
        self.log_view.clear()
        self._line_buffer.clear()
        self._partial_line = ""
        self.log_view.setExtraSelections([])
        self.line_count_label.setText("0 lines")

    def _on_filter_changed(self, _=None):
        """Restart journalctl with new filter settings."""
        self._clear_logs()
        self._start_journalctl()

    # --- Search ---

    def _on_search_changed(self, text):
        """Update search highlighting with debounce."""
        self._current_search = text
        self._search_timer.start(200)

    def _apply_search(self):
        """Apply search highlights after debounce."""
        self._clear_highlights()
        if self._current_search:
            self._highlight_search(self._current_search)

    def _highlight_search(self, text):
        """Highlight all occurrences of text using ExtraSelections."""
        if not text:
            self.log_view.setExtraSelections([])
            return

        selections = []
        doc = self.log_view.document()
        highlight_color = QColor(ModernTheme.ACCENT_YELLOW)
        highlight_color.setAlpha(80)
        text_color = QColor(ModernTheme.TEXT_PRIMARY)

        cursor = doc.find(text)
        seen = 0
        while not cursor.isNull() and seen < 5000:
            sel = QPlainTextEdit.ExtraSelection()  # type: ignore
            sel.cursor = cursor
            fmt = sel.format
            fmt.setBackground(highlight_color)
            fmt.setForeground(text_color)
            sel.format = fmt
            selections.append(sel)
            cursor = doc.find(text, cursor)
            seen += 1

        self.log_view.setExtraSelections(selections)

    def _clear_highlights(self):
        """Remove all search highlights."""
        self.log_view.setExtraSelections([])

    # --- Export ---

    def _export_logs(self):
        """Export displayed log content to a file."""
        content = self.log_view.toPlainText()
        if not content.strip():
            QMessageBox.warning(self, "Export Logs", "No logs to export — the log view is empty.")
            return

        from datetime import datetime
        default_name = datetime.now().strftime("taskwire_logs_%Y%m%d_%H%M.log")

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Logs", default_name,
            "Log Files (*.log);;Text Files (*.txt);;All Files (*)"
        )
        if not filepath:
            return

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            QMessageBox.information(self, "Export Logs", f"Logs saved to:\n{filepath}")
        except PermissionError:
            QMessageBox.critical(self, "Export Logs", f"Permission denied — cannot write to:\n{filepath}")
        except OSError as e:
            QMessageBox.critical(self, "Export Logs", f"Failed to save logs:\n{e}")

    # --- Cleanup ---

    def stop(self):
        """Stop the QProcess. Called on app shutdown."""
        self._flush_timer.stop()
        self._search_timer.stop()
        self._stop_journalctl()

    def __del__(self):
        """Ensure QProcess is cleaned up."""
        try:
            self._flush_timer.stop()
            self._stop_journalctl()
        except (RuntimeError, AttributeError):
            pass
