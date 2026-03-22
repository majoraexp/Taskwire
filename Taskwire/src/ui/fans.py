# pylint: disable=E0611
"""
Fan speed graph widget: FanGraphWidget.
"""
import time
from collections import deque

from PyQt6.QtCore import Qt, QRectF, QPointF, QPoint, QEvent
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QPainterPath, QBrush
)
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout

from .base import format_time_offset, GameTooltip, Card
from ..styles import ModernTheme

class FanGraphWidget(Card):
    """
    A widget to display a historical line graph of fan speeds.
    It includes a legend for multiple fan sensors.
    """
    def __init__(self):
        """
        Initializes the FanGraphWidget.
        """
        super().__init__("Fan Speeds")
        self.maxlen = 90
        self.update_interval = 0
        self.last_update_time = 0
        self.history = {}
        self.sensor_states = {} # name -> bool

        # Colors: Red, Blue, Cyan, Orange
        self.colors = [
            QColor(ModernTheme.ACCENT_RED),
            QColor(ModernTheme.ACCENT_CYAN),
            QColor(ModernTheme.ACCENT_ORANGE),
            QColor(ModernTheme.ACCENT_PURPLE)
        ]

        self.graph_area = QWidget()
        # Same height as the gauges to align nicely
        self.graph_area.setMinimumHeight(100)
        self.graph_area.paintEvent = self.paint_graph
        self.graph_area.setMouseTracking(True)
        self.graph_area.installEventFilter(self)
        self.layout.addWidget(self.graph_area, 1)

        # Add No Data Label
        self.no_data_label = QLabel("No Fans Detected")
        self.no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_data_label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY}; font-style: italic;")
        self.no_data_label.hide()

        # Position it in the center of the graph area (overlay)
        layout_overlay = QVBoxLayout(self.graph_area)
        layout_overlay.addWidget(self.no_data_label)
        layout_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Legend
        self.legend_layout = QGridLayout()
        self.legend_layout.setContentsMargins(0, 5, 0, 0)
        self.layout.addLayout(self.legend_layout)
        self.legend_labels = {}

        # Tooltip State
        self.tooltip_widget = GameTooltip(self.graph_area)
        self.hover_index = -1
        self.hover_pos = QPoint()

    def refresh_theme(self):
        """Refreshes the widget's colors based on the current ModernTheme."""
        self.colors = [
            QColor(ModernTheme.ACCENT_RED),
            QColor(ModernTheme.ACCENT_CYAN),
            QColor(ModernTheme.ACCENT_ORANGE),
            QColor(ModernTheme.ACCENT_PURPLE)
        ]

        while self.legend_layout.count():
            item = self.legend_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.legend_labels = {}

        self.graph_area.update()

    def set_duration(self, seconds, interval=0):
        self.maxlen = seconds
        self.update_interval = interval

        # Reset history to avoid mixed time-scales
        self.history.clear()
        self.graph_area.update()

    def update_data(self, fan_data):
        """
        Updates the fan speed history and triggers a graph repaint.

        Args:
            fan_data (dict): A dictionary where keys are fan sensor names (str)
                             and values are their current RPMs (int).
        """
        if not fan_data:
            self.no_data_label.show()
        else:
            self.no_data_label.hide()

        # Update Legend
        for i, (name, value) in enumerate(fan_data.items()):
            # Default logic: Hide if 0
            if name not in self.sensor_states:
                self.sensor_states[name] = (value > 0)

            color = self.colors[i % len(self.colors)]
            color_hex = color.name()

            display_text = f"<span style='color: {color_hex}; font-weight: bold;'>|</span> {name}: <span style='color: {ModernTheme.TEXT_PRIMARY}; font-weight: bold;'>{int(value)} RPM</span>"

            if name not in self.legend_labels:
                lbl = QLabel(display_text)
                lbl.setTextFormat(Qt.TextFormat.RichText)
                lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)

                row = i // 2
                col = (i % 2) * 2

                self.legend_layout.addWidget(lbl, row, col, 1, 2)
                self.legend_labels[name] = lbl
            else:
                self.legend_labels[name].setText(display_text)

        # Throttle history update
        now = time.time()
        if self.update_interval > 0 and (now - self.last_update_time) < self.update_interval:
            return

        self.last_update_time = now

        # Update History
        for name, value in fan_data.items():
            if name not in self.history:
                self.history[name] = deque([None]*self.maxlen, maxlen=self.maxlen)
            self.history[name].append(value)

        self.graph_area.update()
        self.update_tooltip()

    def update_tooltip(self):
        # Update tooltip if visible
        if self.tooltip_widget.isVisible():
            rect = self.graph_area.rect()
            x = self.hover_pos.x()
            w = rect.width()
            if x < 40:
                self.tooltip_widget.hide()
            else:
                step_x = (w - 40) / (self.maxlen - 1)
                index = int(round((x - 40) / step_x))
                index = max(0, min(index, self.maxlen - 1))

                # Calculate Time Offset for Tooltip
                interval = max(1, self.update_interval)
                seconds_ago = (self.maxlen - 1 - index) * interval
                time_str = format_time_offset(seconds_ago)

                tooltip_lines = []
                tooltip_lines.append(f"Time: -{time_str}")

                for name, points in self.history.items():
                    if index < len(points):
                        val = points[index]
                        if val is None:
                            tooltip_lines.append(f"{name}: NA")
                        else:
                            tooltip_lines.append(f"{name}: {val} RPM")
                if tooltip_lines:
                    self.tooltip_widget.update_info("\n".join(tooltip_lines))
                else:
                    self.tooltip_widget.hide()

    def eventFilter(self, source, event):
        if source == self.graph_area:
            if event.type() == QEvent.Type.MouseMove:
                if not self.history:
                    return False

                rect = self.graph_area.rect()
                x = event.pos().x()
                w = rect.width()

                # Check bounds (left margin 40)
                if x < 40:
                    self.hover_index = -1
                    self.tooltip_widget.hide()
                    self.graph_area.update()
                    return False

                step_x = (w - 40) / (self.maxlen - 1)
                index = int(round((x - 40) / step_x))

                # Check if we have valid data length
                index = max(0, min(index, self.maxlen - 1))

                self.hover_index = index
                self.hover_pos = event.pos()

                # Calculate Time Offset for Tooltip
                interval = max(1, self.update_interval)
                seconds_ago = (self.maxlen - 1 - index) * interval
                time_str = format_time_offset(seconds_ago)

                # Construct Tooltip
                tooltip_lines = []
                # Header
                tooltip_lines.append(f"Time: -{time_str}")

                for name, points in self.history.items():
                    if index < len(points):
                        val = points[index]
                        if val is None:
                            tooltip_lines.append(f"{name}: NA")
                        else:
                            tooltip_lines.append(f"{name}: {val} RPM")

                if tooltip_lines:
                    self.tooltip_widget.update_info("\n".join(tooltip_lines))
                    global_pos = self.graph_area.mapToGlobal(event.pos())
                    self.tooltip_widget.move(global_pos + QPoint(15, 15))
                    self.tooltip_widget.show()
                else:
                    self.tooltip_widget.hide()

                self.graph_area.update()

            elif event.type() == QEvent.Type.Leave:
                self.hover_index = -1
                self.tooltip_widget.hide()
                self.graph_area.update()

        return super().eventFilter(source, event)

    def paint_graph(self, event):
        painter = QPainter(self.graph_area)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.graph_area.width()
        h = self.graph_area.height()
        bottom_margin = 20
        graph_h = h - bottom_margin

        # Determine Max RPM for scaling
        max_rpm = 2000 # Default min max
        for name, points in self.history.items():
            if points:
                # Handle None
                valid_points = [p for p in points if p is not None]
                if valid_points:
                    m = max(valid_points)
                    if m > max_rpm:
                        max_rpm = m

        # Add headroom
        max_rpm = int(max_rpm * 1.1)

        # Draw Grid Lines & Labels
        grid_pen = QPen(QColor(ModernTheme.BORDER_COLOR))
        grid_pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(grid_pen)

        # Draw 4 grid lines
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)

        steps = 4
        for i in range(steps + 1):
            val = i * (max_rpm / steps)
            y = graph_h - (val / max_rpm * graph_h)

            # Grid line
            painter.setPen(grid_pen)
            painter.drawLine(40, int(y), w, int(y)) # Offset x by 40 for text

            # Label
            painter.setPen(QColor(ModernTheme.TEXT_SECONDARY))
            painter.drawText(0, int(y) + 4, 35, 10, Qt.AlignmentFlag.AlignRight, f"{int(val)}")

        # Draw Time Axis (X-Axis)
        total_seconds = (self.maxlen - 1) * max(1, self.update_interval)
        num_ticks = 6
        tick_pen = QPen(QColor(ModernTheme.TEXT_SECONDARY))
        painter.setPen(tick_pen)

        for i in range(num_ticks):
            ratio = i / (num_ticks - 1)
            # Map ratio to 40..w
            x = 40 + ratio * (w - 40)

            seconds_ago = total_seconds * (1 - ratio)
            time_str = format_time_offset(seconds_ago)

            # Align center, except first and last
            flags = Qt.AlignmentFlag.AlignCenter
            if i == 0: flags = Qt.AlignmentFlag.AlignLeft
            elif i == num_ticks - 1: flags = Qt.AlignmentFlag.AlignRight

            # Draw text at bottom
            text_rect = QRectF(x - 25, graph_h + 2, 50, 15)
            if i == 0: text_rect = QRectF(40, graph_h + 2, 50, 15)
            elif i == num_ticks - 1: text_rect = QRectF(w - 50, graph_h + 2, 50, 15)

            painter.drawText(text_rect, flags, time_str)

        # Draw Lines
        step_x = (w - 40) / (self.maxlen - 1)

        for i, (name, points_deque) in enumerate(self.history.items()):
            if not self.sensor_states.get(name, False): continue

            if len(points_deque) < 2: continue

            points = list(points_deque)
            num_points = len(points)
            step_x = (w - 40) / (self.maxlen - 1)
            start_x = w - (num_points - 1) * step_x

            path = QPainterPath()

            # Start
            start_val = 0.0 if points[0] is None else points[0]
            start_y = graph_h - (start_val / max_rpm * graph_h)
            path.moveTo(40, start_y)

            for j, val in enumerate(points):
                # Treat None as 0
                draw_val = 0.0 if val is None else val

                x = start_x + j * step_x
                y = graph_h - (draw_val / max_rpm * graph_h)
                path.lineTo(x, y)

            color = self.colors[i % len(self.colors)]
            pen = QPen(color, 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

            # Draw Dot if hovered
            if self.hover_index != -1:
                screen_idx = self.hover_index
                offset = (self.maxlen - 1) - screen_idx
                data_idx = (len(points) - 1) - offset

                if 0 <= data_idx < len(points):
                    val = points[data_idx]
                    # Treat None as 0
                    draw_val = 0.0 if val is None else val

                    hx = 40 + screen_idx * step_x
                    hy = graph_h - (draw_val / max_rpm * graph_h)

                    # Draw Vertical Line
                    painter.setPen(QPen(QColor(ModernTheme.BORDER_COLOR), 1, Qt.PenStyle.DashLine))
                    painter.drawLine(int(hx), 0, int(hx), int(graph_h))

                    painter.setBrush(QBrush(color))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(QPointF(hx, hy), 4, 4)
