# pylint: disable=E0611
"""
CPU widgets: CpuWidget, CpuHistoryWidget.
"""
import time
from collections import deque

from PyQt6.QtCore import Qt, QRectF, QPointF, QPoint, QEvent
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QPainterPath, QBrush
)
from PyQt6.QtWidgets import (
    QWidget, QLabel, QProgressBar, QGridLayout
)

from .base import format_time_offset, GameTooltip, Card
from ..styles import ModernTheme

class CpuHistoryWidget(Card):
    """
    A generic widget to display a historical line graph of a utilization metric.
    Used for CPU, GPU, or any 0-100% time-series data.
    """
    def __init__(self, history_duration=90, title="CPU History",
                 accent_color=None, label="CPU"):
        """
        Initializes the history graph widget.

        Args:
            history_duration (int): The number of seconds to keep in the history.
            title (str): The card title displayed above the graph.
            accent_color (str): Hex color for the graph line/fill. Defaults to ACCENT_CYAN.
            label (str): Label used in tooltips and overlay (e.g. "CPU", "GPU").
        """
        super().__init__(title)
        self.accent_color = accent_color or ModernTheme.ACCENT_CYAN
        self.label = label
        self.maxlen = history_duration
        self.update_interval = 0
        self.last_update_time = 0
        self.data_points = deque([None]*self.maxlen, maxlen=self.maxlen)

        self.graph_area = QWidget()
        self.graph_area.setMinimumHeight(150)
        self.graph_area.paintEvent = self.paint_graph
        self.graph_area.setMouseTracking(True)
        self.graph_area.installEventFilter(self)
        self.layout.addWidget(self.graph_area, 1)

        # Tooltip State
        self.tooltip_widget = GameTooltip(self.graph_area)
        self.hover_index = -1
        self.hover_pos = QPoint()

    def set_duration(self, seconds, interval=0):
        """
        Sets the duration (in seconds) for which CPU history is maintained.

        Args:
            seconds (int): Max number of data points to store.
            interval (int): Minimum seconds between updates. 0 = no throttle.
        """
        self.maxlen = seconds
        self.update_interval = interval

        # Reset deque to avoid mixed time-scales
        self.data_points = deque([None]*self.maxlen, maxlen=self.maxlen)
        self.graph_area.update()

    def update_data(self, cpu_percent):
        """
        Updates the CPU history with a new percentage value and triggers a graph repaint.

        Args:
            cpu_percent (float): The current total CPU utilization percentage.
        """
        # Throttle history update
        now = time.time()
        if self.update_interval > 0 and (now - self.last_update_time) < self.update_interval:
            return

        self.last_update_time = now
        self.data_points.append(cpu_percent)
        self.graph_area.update()

        # Update tooltip if visible
        if self.tooltip_widget.isVisible() and self.hover_index != -1:
            # Re-calculate index logic or clamp?
            # Since data shifts, the same hover_index now points to newer data?
            # Actually, data_points is a deque. append() adds to the RIGHT.
            # So index 0 is oldest. Index max is newest.
            # If I hover at index 10. That slot stays index 10.
            # But the *time* associated with index 10 changes relative to "now".
            # No, wait. "Now" is always at index max.
            # Index 10 is always "max - 10" steps ago.
            # So the time offset for a physical pixel X is constant!
            # BUT the *value* at that pixel shifts left as new data arrives.
            # data_points[10] becomes old data_points[11].

            # So we just need to re-read the value at self.hover_index.

            if self.hover_index < len(self.data_points):
                # Calculate Time Offset for Tooltip
                interval = max(1, self.update_interval)
                seconds_ago = (self.maxlen - 1 - self.hover_index) * interval
                time_str = format_time_offset(seconds_ago)

                val = self.data_points[self.hover_index]
                if val is None:
                    self.tooltip_widget.update_info(f"Time: -{time_str}\n{self.label}: NA")
                else:
                    self.tooltip_widget.update_info(f"Time: -{time_str}\n{self.label}: {val:.1f}%")

    def refresh_theme(self):
        """Refreshes the widget's colors based on the current ModernTheme."""
        self.graph_area.update()

    def eventFilter(self, source, event):
        """
        Handles mouse events for the graph area to display tooltips.
        """
        if source == self.graph_area:
            if event.type() == QEvent.Type.MouseMove:
                if len(self.data_points) < 2:
                    return False

                rect = self.graph_area.rect()
                x = event.pos().x()
                width = rect.width()

                # Calculate index based on X
                step_x = width / (self.maxlen - 1)
                index = int(round(x / step_x))

                # Clamp index
                index = max(0, min(index, len(self.data_points) - 1))

                self.hover_index = index
                self.hover_pos = event.pos()

                # Calculate Time Offset for Tooltip
                interval = max(1, self.update_interval)
                seconds_ago = (self.maxlen - 1 - index) * interval
                time_str = format_time_offset(seconds_ago)

                # Update Tooltip
                val = self.data_points[index]
                if val is None:
                    self.tooltip_widget.update_info(f"Time: -{time_str}\n{self.label}: NA")
                else:
                    self.tooltip_widget.update_info(f"Time: -{time_str}\n{self.label}: {val:.1f}%")

                # Position Tooltip (Global Coords)
                global_pos = self.graph_area.mapToGlobal(event.pos())
                self.tooltip_widget.move(global_pos + QPoint(15, 15))
                self.tooltip_widget.show()

                self.graph_area.update()

            elif event.type() == QEvent.Type.Leave:
                self.hover_index = -1
                self.tooltip_widget.hide()
                self.graph_area.update()

        return super().eventFilter(source, event)

    def paint_graph(self, event): # pylint: disable=C0103,W0613
        """
        Paints the CPU history graph, including background grid and filled area graph.
        """
        painter = QPainter(self.graph_area)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.graph_area.width()
        height = self.graph_area.height()
        bottom_margin = 20
        graph_h = height - bottom_margin

        # Draw Background Grid (Subtle)
        grid_pen = QPen(QColor(ModernTheme.BORDER_COLOR))
        grid_pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(grid_pen)
        for i in range(1, 5):
            y = i * (graph_h / 5)
            painter.drawLine(0, int(y), width, int(y))

        # Draw Time Axis (X-Axis)
        total_seconds = (self.maxlen - 1) * max(1, self.update_interval)
        num_ticks = 6
        tick_pen = QPen(QColor(ModernTheme.TEXT_SECONDARY))
        painter.setPen(tick_pen)
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)

        for i in range(num_ticks):
            ratio = i / (num_ticks - 1)
            x = ratio * width
            seconds_ago = total_seconds * (1 - ratio)
            time_str = format_time_offset(seconds_ago)

            # Align center, except first and last
            flags = Qt.AlignmentFlag.AlignCenter
            if i == 0: flags = Qt.AlignmentFlag.AlignLeft
            elif i == num_ticks - 1: flags = Qt.AlignmentFlag.AlignRight

            # Draw text at bottom
            text_rect = QRectF(x - 25, height - bottom_margin + 2, 50, 15)
            if i == 0: text_rect = QRectF(0, height - bottom_margin + 2, 50, 15)
            elif i == num_ticks - 1: text_rect = QRectF(width - 50, height - bottom_margin + 2, 50, 15)

            painter.drawText(text_rect, flags, time_str)

        # Draw Graph
        if len(self.data_points) < 2:
            return

        path = QPainterPath()
        path.moveTo(0, graph_h) # Start bottom-left

        points = list(self.data_points)
        step_x = width / (self.maxlen - 1)

        for i, val in enumerate(points):
            x = i * step_x
            v = val if val is not None else 0
            y = graph_h - (v / 100 * graph_h)
            path.lineTo(x, y)

        path.lineTo(width, graph_h) # Bottom-right
        path.closeSubpath()

        # Fill
        fill_color = QColor(self.accent_color)
        fill_color.setAlpha(50)
        painter.fillPath(path, fill_color)

        # Stroke
        pen = QPen(QColor(self.accent_color), 2)
        painter.setPen(pen)
        painter.drawPath(path)

        # Draw Hover Dot
        if self.hover_index != -1 and self.hover_index < len(points):
            val = points[self.hover_index]
            v = val if val is not None else 0
            hx = self.hover_index * step_x
            hy = graph_h - (v / 100 * graph_h)

            # Draw Vertical Line
            painter.setPen(QPen(QColor(ModernTheme.BORDER_COLOR), 1, Qt.PenStyle.DashLine))
            painter.drawLine(int(hx), 0, int(hx), int(graph_h))

            painter.setBrush(QBrush(QColor(self.accent_color)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(hx, hy), 4, 4)

        # Draw Current Value Text (Overlay at Bottom Right)
        current_val = points[-1]
        text = f"{current_val:.1f}%" if current_val is not None else "NA"

        font = QFont()
        font.setPointSize(24)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(ModernTheme.TEXT_PRIMARY))

        # Position: Bottom Right, above the time axis margin
        # Align Right | Bottom relative to the graph area (minus margins)
        # Add slight padding from right edge (10px) and bottom of graph area (5px)
        text_rect = QRectF(width - 150, graph_h - 40, 140, 40)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, text)

class CpuWidget(Card):
    """
    A widget to display CPU utilization and frequency per thread using progress bars.
    """
    def __init__(self):
        """
        Initializes the CpuWidget.
        """
        super().__init__("CPU Utilization (Per Thread)")
        self.grid = QGridLayout()
        self.layout.addLayout(self.grid)
        self.bars = []

    def refresh_theme(self):
        """Refreshes the widget's colors by clearing the grid so it rebuilds on next update."""
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.bars = []

    def update_data(self, overall, per_core, freqs=None):
        """
        Updates the CPU utilization bars and frequency for each core.

        Args:
            overall (float): Overall CPU utilization.
            per_core (list): A list of float values representing CPU utilization for each core.
            freqs (list): A list of float values representing CPU frequency (MHz) for each core.
        """
        if freqs is None: freqs = []

        # Initialize bars if not created
        if not self.bars:
            for i, _ in enumerate(per_core):
                label = QLabel(f"Core {i+1}")
                label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY}; font-size: 11px;")

                bar = QProgressBar()
                bar.setRange(0, 100)
                bar.setTextVisible(False)
                bar.setFixedHeight(6) # Smaller height

                colors = [ModernTheme.ACCENT_PURPLE, ModernTheme.ACCENT_CYAN,
                          ModernTheme.ACCENT_GREEN, ModernTheme.ACCENT_ORANGE]
                color = colors[i % len(colors)]

                bar.setStyleSheet(f"""
                    QProgressBar::chunk {{ background-color: {color}; border-radius: 2px; }}
                    QProgressBar {{ background-color: {ModernTheme.ALTERNATE_TABLE_BG}; border: none; border-radius: 2px; }}
                """)

                # Frequency Label
                freq_label = QLabel("0 MHz")
                freq_label.setStyleSheet(f"color: {ModernTheme.ACCENT_CYAN}; font-size: 10px;")
                freq_label.setAlignment(Qt.AlignmentFlag.AlignRight)

                # Value label
                val_label = QLabel("0%")
                val_label.setFixedWidth(45)
                val_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
                val_label.setStyleSheet("font-size: 12px;")

                row = i // 4  # 4 cores per row
                col_group = (i % 4)

                # 4 items + spacing = 5 columns per group stride
                base_col = col_group * 5

                self.grid.addWidget(label, row, base_col)
                self.grid.addWidget(bar, row, base_col + 1)
                self.grid.addWidget(freq_label, row, base_col + 2)
                self.grid.addWidget(val_label, row, base_col + 3)

                # Spacer column
                if col_group < 3:
                    self.grid.setColumnMinimumWidth(base_col + 4, 10)

                self.bars.append((bar, val_label, freq_label))

        # Update values
        for i, val in enumerate(per_core):
            if i < len(self.bars):
                bar, val_lbl, freq_lbl = self.bars[i]
                bar.setValue(int(val))
                val_lbl.setText(f"{val:.0f}%")

                if i < len(freqs):
                    f = freqs[i]
                    if f >= 1000:
                        freq_lbl.setText(f"{f/1000:.1f} GHz")
                    else:
                        freq_lbl.setText(f"{int(f)} MHz")
                else:
                    freq_lbl.setText("")
