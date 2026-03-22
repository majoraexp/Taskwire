# pylint: disable=E0611
"""
Network widget: NetworkWidget.
"""
import time
from collections import deque

from PyQt6.QtCore import Qt, QRectF, QPointF, QPoint, QEvent
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QPainterPath, QBrush
)
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel

from .base import format_time_offset, GameTooltip, Card
from ..styles import ModernTheme

class NetworkWidget(Card):
    """
    A widget to display network usage history (Upload/Download).
    """
    def __init__(self):
        super().__init__("Network Speed")

        self.maxlen = 90
        self.update_interval = 0
        self.last_update_time = 0
        self.up_history = deque([None]*self.maxlen, maxlen=self.maxlen)
        self.down_history = deque([None]*self.maxlen, maxlen=self.maxlen)

        # Labels Layout (Top - Left Aligned)
        labels_layout = QHBoxLayout()
        labels_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        labels_layout.setSpacing(20)

        self.up_label = QLabel("Upload: 0 KB/s")
        self.down_label = QLabel("Download: 0 KB/s")

        # Fixed width to prevent jitter
        self.up_label.setFixedWidth(160)
        self.down_label.setFixedWidth(160)

        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.up_label.setFont(font)
        self.down_label.setFont(font)

        # Colors: Upload (Green), Download (Red)
        self.up_label.setStyleSheet(f"color: {ModernTheme.ACCENT_GREEN};")
        self.down_label.setStyleSheet(f"color: {ModernTheme.ACCENT_RED};")

        labels_layout.addWidget(self.up_label)
        labels_layout.addWidget(self.down_label)

        self.layout.addLayout(labels_layout)

        # Graph Area (Compact)
        self.graph_area = QWidget()
        self.graph_area.setMinimumHeight(75)
        self.graph_area.paintEvent = self.paint_graph
        self.graph_area.setMouseTracking(True)
        self.graph_area.installEventFilter(self)
        self.layout.addWidget(self.graph_area, 1)

        # Tooltip
        self.tooltip_widget = GameTooltip(self.graph_area)
        self.hover_index = -1
        self.hover_pos = QPoint()

    def refresh_theme(self):
        """Refreshes the widget's colors based on the current ModernTheme."""
        self.up_label.setStyleSheet(f"color: {ModernTheme.ACCENT_GREEN};")
        self.down_label.setStyleSheet(f"color: {ModernTheme.ACCENT_RED};")
        self.graph_area.update()

    def set_duration(self, seconds, interval=0):
        self.maxlen = seconds
        self.update_interval = interval
        self.up_history = deque([None]*self.maxlen, maxlen=self.maxlen)
        self.down_history = deque([None]*self.maxlen, maxlen=self.maxlen)
        self.graph_area.update()

    def update_data(self, stats):
        up_speed = stats['upload']
        down_speed = stats['download']

        self.up_label.setText(f"Upload: {self.format_speed(up_speed)}")
        self.down_label.setText(f"Download: {self.format_speed(down_speed)}")

        # Throttle
        now = time.time()
        if self.update_interval > 0 and (now - self.last_update_time) < self.update_interval:
            return

        self.last_update_time = now
        self.up_history.append(up_speed)
        self.down_history.append(down_speed)

        self.graph_area.update()

        # Update Tooltip
        if self.tooltip_widget.isVisible() and self.hover_index != -1:
            screen_idx = self.hover_index
            offset = (self.maxlen - 1) - screen_idx
            data_idx = (len(self.up_history) - 1) - offset

            interval = max(1, self.update_interval)
            seconds_ago = (self.maxlen - 1 - self.hover_index) * interval
            time_str = format_time_offset(seconds_ago)

            if 0 <= data_idx < len(self.up_history):
                u_val = self.up_history[data_idx]
                d_val = self.down_history[data_idx]

                u_str = self.format_speed(u_val) if u_val is not None else "NA"
                d_str = self.format_speed(d_val) if d_val is not None else "NA"

                self.tooltip_widget.update_info(
                    f"Time: -{time_str}\nUp: {u_str}\nDown: {d_str}"
                )
            else:
                self.tooltip_widget.update_info(f"Time: -{time_str}\nUp: NA\nDown: NA")

    def eventFilter(self, source, event):
        if source == self.graph_area:
            if event.type() == QEvent.Type.MouseMove:
                if not self.up_history: return False

                rect = self.graph_area.rect()
                x = event.pos().x()
                width = rect.width()

                step_x = width / (self.maxlen - 1)
                index = int(round(x / step_x))
                index = max(0, min(index, self.maxlen - 1))

                self.hover_index = index
                self.hover_pos = event.pos()

                # Update Tooltip Logic (Same as update_data)
                screen_idx = self.hover_index
                offset = (self.maxlen - 1) - screen_idx
                data_idx = (len(self.up_history) - 1) - offset

                interval = max(1, self.update_interval)
                seconds_ago = (self.maxlen - 1 - index) * interval
                time_str = format_time_offset(seconds_ago)

                if 0 <= data_idx < len(self.up_history):
                    u_val = self.up_history[data_idx]
                    d_val = self.down_history[data_idx]
                    u_str = self.format_speed(u_val) if u_val is not None else "NA"
                    d_str = self.format_speed(d_val) if d_val is not None else "NA"
                    self.tooltip_widget.update_info(f"Time: -{time_str}\nUp: {u_str}\nDown: {d_str}")
                else:
                    self.tooltip_widget.update_info(f"Time: -{time_str}\nUp: NA\nDown: NA")

                global_pos = self.graph_area.mapToGlobal(event.pos())
                self.tooltip_widget.move(global_pos + QPoint(15, 15))
                self.tooltip_widget.show()
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
        top_margin = 10
        graph_h = h - bottom_margin - top_margin

        # Scaling
        max_u = max((v for v in self.up_history if v is not None), default=0)
        max_d = max((v for v in self.down_history if v is not None), default=0)
        max_val = max(max_u, max_d)
        if max_val == 0: max_val = 1024 * 10 # 10 KB/s min

        max_val = max_val * 1.2

        # Grid
        grid_pen = QPen(QColor(ModernTheme.BORDER_COLOR))
        grid_pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(grid_pen)

        for i in range(1, 4):
            y = top_margin + graph_h - (i * (graph_h / 4))
            painter.drawLine(0, int(y), w, int(y))
            val_at_line = max_val * (i / 4)
            painter.drawText(2, int(y) - 2, self.format_speed(val_at_line))

        # Time Axis
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

            flags = Qt.AlignmentFlag.AlignCenter
            if i == 0: flags = Qt.AlignmentFlag.AlignLeft
            elif i == num_ticks - 1: flags = Qt.AlignmentFlag.AlignRight

            text_rect = QRectF(x - 25, h - bottom_margin + 2, 50, 15)
            if i == 0: text_rect = QRectF(0, h - bottom_margin + 2, 50, 15)
            elif i == num_ticks - 1: text_rect = QRectF(w - 50, h - bottom_margin + 2, 50, 15)

            painter.drawText(text_rect, flags, time_str)

        # Draw Lines
        # Upload (Green)
        self.draw_line(painter, self.up_history, ModernTheme.ACCENT_GREEN, max_val, w, top_margin, graph_h, h)
        # Download (Red)
        self.draw_line(painter, self.down_history, ModernTheme.ACCENT_RED, max_val, w, top_margin, graph_h, h)

    def draw_line(self, painter, data_deque, color_hex, max_val, w, top_margin, graph_h, h):
        if len(data_deque) < 2: return

        path = QPainterPath()
        step_x = w / (self.maxlen - 1)
        points = list(data_deque)
        num_points = len(points)
        start_x = w - (num_points - 1) * step_x

        start_val = 0.0 if points[0] is None else points[0]
        start_y = top_margin + graph_h - ((start_val / max_val) * graph_h)
        path.moveTo(start_x, start_y)

        for i, val in enumerate(points):
            draw_val = 0.0 if val is None else val
            x = start_x + i * step_x
            y = top_margin + graph_h - ((draw_val / max_val) * graph_h)
            path.lineTo(x, y)

        pen = QPen(QColor(color_hex), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # Hover Dot
        if self.hover_index != -1:
            screen_idx = self.hover_index
            offset = (self.maxlen - 1) - screen_idx
            data_idx = (len(points) - 1) - offset

            if 0 <= data_idx < len(points):
                val = points[data_idx]
                draw_val = 0.0 if val is None else val

                hx = screen_idx * step_x
                hy = top_margin + graph_h - ((draw_val / max_val) * graph_h)

                painter.setPen(QPen(QColor(ModernTheme.BORDER_COLOR), 1, Qt.PenStyle.DashLine))
                painter.drawLine(int(hx), 0, int(hx), int(h - 20)) # 20 is bottom margin

                painter.setBrush(QBrush(QColor(color_hex)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(hx, hy), 4, 4)

    def format_speed(self, bytes_sec):
        if bytes_sec >= 1024**3: return f"{bytes_sec / (1024**3):.1f} GB/s"
        elif bytes_sec >= 1024**2: return f"{bytes_sec / (1024**2):.1f} MB/s"
        elif bytes_sec >= 1024: return f"{bytes_sec / 1024:.1f} KB/s"
        else: return f"{bytes_sec:.1f} B/s"
