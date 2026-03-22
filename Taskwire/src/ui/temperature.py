# pylint: disable=E0611
"""
Temperature graph widget: TempGraphWidget.
"""
import time
from collections import deque

from PyQt6.QtCore import Qt, QRectF, QPointF, QPoint, QEvent
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QPainterPath, QBrush
)
from PyQt6.QtWidgets import QWidget, QLabel, QGridLayout

from .base import format_time_offset, GameTooltip, Card
from ..styles import ModernTheme

class TempGraphWidget(Card):
    """
    A widget to display a graph of temperature sensor history.
    It shows multiple temperature lines with a grid and legend.
    """
    def __init__(self):
        """
        Initializes the TempGraphWidget.
        """
        super().__init__("Temperatures")
        self.maxlen = 90
        self.update_interval = 0
        self.last_update_time = 0
        self.history = {}

        # Colors from the Theme
        self.colors = [
            QColor(ModernTheme.ACCENT_PURPLE),
            QColor(ModernTheme.ACCENT_BLUE),
            QColor(ModernTheme.ACCENT_RED),
            QColor(ModernTheme.ACCENT_GREEN),
            QColor(ModernTheme.ACCENT_ORANGE)
        ]

        self.graph_area = QWidget()
        self.graph_area.setMinimumHeight(150)
        self.graph_area.paintEvent = self.paint_graph
        self.graph_area.setMouseTracking(True)
        self.graph_area.installEventFilter(self)
        self.layout.addWidget(self.graph_area, 1)

        # Legend / Values area
        self.legend_layout = QGridLayout()
        self.legend_layout.setContentsMargins(0, 5, 0, 0)
        self.layout.addLayout(self.legend_layout)
        self.legend_labels = {} # {name: (name_label, value_label)}

        # Tooltip State
        self.tooltip_widget = GameTooltip(self.graph_area)
        self.hover_index = -1
        self.hover_pos = QPoint()

    def refresh_theme(self):
        """
        Refreshes the widget's colors based on the current ModernTheme.
        """
        # Re-fetch colors
        self.colors = [
            QColor(ModernTheme.ACCENT_PURPLE),
            QColor(ModernTheme.ACCENT_BLUE),
            QColor(ModernTheme.ACCENT_RED),
            QColor(ModernTheme.ACCENT_GREEN),
            QColor(ModernTheme.ACCENT_ORANGE)
        ]

        # Clear Legend so it rebuilds with new text colors
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

    def update_data(self, temp_data):
        """
        Updates the temperature history and triggers a graph repaint.

        Args:
            temp_data (dict): A dictionary where keys are sensor names (str)
                              and values are their current temperatures (float).
        """
        # Update Legend
        for i, (name, value) in enumerate(temp_data.items()):
            color = self.colors[i % len(self.colors)]
            color_hex = color.name()

            # Combine name and value into a single QLabel
            display_text = (  # pylint: disable=C0301
                f"<span style='color: {color_hex}; font-weight: bold;'>{name}:</span> "
                f"<span style='color: {ModernTheme.TEXT_PRIMARY};'>{value:.1f}\u00b0C</span>"
            )

            if name not in self.legend_labels:
                combined_lbl = QLabel(display_text)
                combined_lbl.setTextFormat(Qt.TextFormat.RichText) # Enable HTML-like formatting
                combined_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)

                row = i // 2
                col = (i % 2) * 2 # Place it on the left column in its group

                self.legend_layout.addWidget(combined_lbl, row, col, 1, 2) # Span 2 columns
                self.legend_labels[name] = combined_lbl
            else:
                self.legend_labels[name].setText(display_text)

        # Throttle history update
        now = time.time()
        if self.update_interval > 0 and (now - self.last_update_time) < self.update_interval:
            return

        self.last_update_time = now

        # Update History
        for name, value in temp_data.items():
            if name not in self.history:
                self.history[name] = deque([None]*self.maxlen, maxlen=self.maxlen)
            self.history[name].append(value)

        self.graph_area.update()

        # Update tooltip if visible
        if self.tooltip_widget.isVisible():
            rect = self.graph_area.rect()
            x = self.hover_pos.x()
            width = rect.width()
            step_x = width / (self.maxlen - 1)
            index = int(round(x / step_x))
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
                        tooltip_lines.append(f"{name}: {val:.1f}\u00b0C")
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
                width = rect.width()

                step_x = width / (self.maxlen - 1)
                index = int(round(x / step_x))

                # Clamp index
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
                            tooltip_lines.append(f"{name}: {val:.1f}\u00b0C")

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

    def paint_graph(self, event): # pylint: disable=C0103,W0613
        """
        Paints the temperature graph for the TempGraphWidget.
        It draws a background grid, labels, and plots temperature history lines.
        """
        painter = QPainter(self.graph_area)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.graph_area.width()
        h = self.graph_area.height()
        bottom_margin = 20
        top_margin = 10
        graph_h = h - bottom_margin - top_margin

        # Draw Background & Grid
        # Range 30 - 100
        min_temp = 30
        max_temp = 100
        temp_range = max_temp - min_temp

        grid_pen = QPen(QColor(ModernTheme.BORDER_COLOR))
        grid_pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(grid_pen)

        # Draw grid lines for 40, 60, 80, 100
        for t in [40, 60, 80, 100]:
            # Normalize t to 0-1 (0 is bottom, 1 is top)
            # y = top_margin + graph_h - (normalized * graph_h)
            normalized = (t - min_temp) / temp_range
            y = top_margin + graph_h - (normalized * graph_h)
            painter.drawLine(0, int(y), w, int(y))

            # Text label for grid
            painter.drawText(2, int(y) - 2, f"{t}\u00b0C")

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
            x = ratio * w
            seconds_ago = total_seconds * (1 - ratio)
            time_str = format_time_offset(seconds_ago)

            # Align center, except first and last
            flags = Qt.AlignmentFlag.AlignCenter
            if i == 0: flags = Qt.AlignmentFlag.AlignLeft
            elif i == num_ticks - 1: flags = Qt.AlignmentFlag.AlignRight

            # Draw text at bottom
            text_rect = QRectF(x - 25, h - bottom_margin + 2, 50, 15)
            if i == 0: text_rect = QRectF(0, h - bottom_margin + 2, 50, 15)
            elif i == num_ticks - 1: text_rect = QRectF(w - 50, h - bottom_margin + 2, 50, 15)

            painter.drawText(text_rect, flags, time_str)

        # Draw Lines
        step_x = w / (self.maxlen - 1)

        # Find the transition index and draw a multicolored vertical line
        # Each segment matches the sensor color, ordered from lowest to highest value
        transition_idx = None
        transition_sensors = []  # list of (value, color)
        for idx, (name, points_deque) in enumerate(self.history.items()):
            points = list(points_deque)
            for j, val in enumerate(points):
                if val is not None:
                    if transition_idx is None or j < transition_idx:
                        transition_idx = j
                    color = self.colors[idx % len(self.colors)]
                    transition_sensors.append((val, color))
                    break
        if transition_idx is not None and transition_idx > 0 and transition_sensors:
            tx = transition_idx * step_x
            baseline_y = top_margin + graph_h
            # Sort by value so lowest color is at bottom, highest at top
            transition_sensors.sort(key=lambda x: x[0])
            prev_y = baseline_y
            for val, color in transition_sensors:
                norm = (val - min_temp) / temp_range
                norm = max(0.0, min(1.0, norm))
                cur_y = top_margin + graph_h - (norm * graph_h)
                painter.setPen(QPen(color, 2))
                painter.drawLine(int(tx), int(prev_y), int(tx), int(cur_y))
                prev_y = cur_y

        for i, (name, points_deque) in enumerate(self.history.items()):
            if len(points_deque) < 2: continue

            points = list(points_deque)
            color = self.colors[i % len(self.colors)]

            # Build separate paths for unfilled (None) and real data segments
            unfilled_path = QPainterPath()
            real_path = QPainterPath()
            prev_was_none = True
            prev_was_real = True

            for j, val in enumerate(points):
                x = j * step_x
                v = val if val is not None else 0
                norm = (v - min_temp) / temp_range
                norm = max(0.0, min(1.0, norm))
                y = top_margin + graph_h - (norm * graph_h)

                if val is None:
                    if prev_was_none:
                        unfilled_path.lineTo(x, y) if j > 0 else unfilled_path.moveTo(x, y)
                    else:
                        unfilled_path.moveTo(x, y)
                    prev_was_none = True
                    prev_was_real = False
                else:
                    if prev_was_real:
                        real_path.lineTo(x, y) if j > 0 else real_path.moveTo(x, y)
                    else:
                        # Start from baseline at this x so it flows from the vertical line
                        baseline_y = top_margin + graph_h
                        real_path.moveTo(x, baseline_y)
                        real_path.lineTo(x, y)
                    prev_was_real = True
                    prev_was_none = False

            # Draw unfilled segments in cyan (matching CPU history graph)
            painter.setPen(QPen(QColor(ModernTheme.ACCENT_CYAN), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(unfilled_path)

            # Draw real data segments in sensor color
            painter.setPen(QPen(color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(real_path)

            # Draw Hover Dot
            if self.hover_index != -1 and self.hover_index < len(points):
                val = points[self.hover_index]
                v = val if val is not None else 0
                hx = self.hover_index * step_x
                norm = (v - min_temp) / temp_range
                norm = max(0.0, min(1.0, norm))
                hy = top_margin + graph_h - (norm * graph_h)

                # Draw Vertical Line
                painter.setPen(QPen(QColor(ModernTheme.BORDER_COLOR), 1, Qt.PenStyle.DashLine))
                painter.drawLine(int(hx), 0, int(hx), int(h - bottom_margin))

                painter.setBrush(QBrush(color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(hx, hy), 4, 4)
