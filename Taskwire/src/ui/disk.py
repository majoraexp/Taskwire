# pylint: disable=E0611
"""
Disk widgets: ModernDriveIcon, DiskWidget, DiskIOWidget.
"""
import time
from collections import deque

from PyQt6.QtCore import Qt, QRectF, QPointF, QPoint, QEvent
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QPainterPath,
    QPolygonF, QBrush, QLinearGradient, QRadialGradient
)
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QProgressBar, QAbstractButton
)

from .base import format_time_offset, GameTooltip, Card
from ..styles import ModernTheme

class ModernDriveIcon(QAbstractButton):
    """
    A custom QAbstractButton widget representing a modern drive icon with
    a pseudo-3D isometric style and an active state indicator (LED).
    """
    def __init__(self, parent=None):
        """
        Initializes the ModernDriveIcon.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setFixedSize(45, 45) # Reduced size
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.is_active = False

    def set_active(self, active):
        """
        Sets the active state of the icon.

        Args:
            active (bool): True if the icon should be active, False otherwise.
        """
        self.is_active = active
        self.update()

    def paintEvent(self, event): # pylint: disable=C0103,W0613
        """
        Paints the isometric drive icon, including its base, highlights,
        label, and LED indicator based on its active state.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Colors
        base_color = QColor("#2e2e3e")
        highlight = QColor("#44475a")
        accent = QColor(ModernTheme.ACCENT_CYAN) if self.is_active else QColor("#6272a4")

        # Isometric Calculation (Pseudo-3D)
        # Front Face
        face_rect = QRectF(7, 10, 23, 30) # Adjusted for smaller size

        # Side Face (Right)
        side_poly = QPolygonF([
            QPointF(30, 10), # TL
            QPointF(38, 5),  # TR (Perspective up)
            QPointF(38, 35), # BR
            QPointF(30, 40)  # BL
        ])

        # Top Face
        top_poly = QPolygonF([
            QPointF(7, 10), # BL
            QPointF(15, 5), # TL
            QPointF(38, 5), # TR
            QPointF(30, 10) # BR
        ])

        # Draw Top (Lightest)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(highlight.lighter(130)))
        painter.drawPolygon(top_poly)

        # Draw Side (Darkest)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(base_color.darker(120)))
        painter.drawPolygon(side_poly)

        # Draw Front (Gradient)
        grad = QLinearGradient(face_rect.topLeft(), face_rect.bottomRight())
        grad.setColorAt(0, highlight)
        grad.setColorAt(1, base_color)
        painter.setBrush(QBrush(grad))
        painter.drawRoundedRect(face_rect, 2, 2)

        # Draw "Sticker/Label" on front
        label_rect = QRectF(10, 14, 17, 10)
        painter.setBrush(QBrush(QColor("#1a1a1a")))
        painter.drawRoundedRect(label_rect, 1, 1)

        # Draw LED
        led_center = QPointF(18, 32)
        if self.is_active:
            glow = QRadialGradient(led_center, 6)
            glow.setColorAt(0, accent)
            glow.setColorAt(1, Qt.GlobalColor.transparent)

            painter.setBrush(QBrush(glow))
            painter.drawEllipse(led_center, 3, 3)

            # Bright core
            painter.setBrush(QBrush(accent.lighter(150)))
            painter.drawEllipse(led_center, 1, 1)
        else:
            # Dim LED
            painter.setBrush(QBrush(QColor("#333")))
            painter.drawEllipse(led_center, 1.5, 1.5)

        # Selection Ring (if active)
        if self.is_active:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(accent, 2))
            painter.drawRoundedRect(2, 2, w-4, h-4, 5, 5)
        elif self.underMouse():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(ModernTheme.BORDER_COLOR), 1))
            painter.drawRoundedRect(2, 2, w-4, h-4, 5, 5)

class DiskWidget(Card):
    """
    A widget to display disk usage information for various drives.
    It shows available drives as icons and detailed usage for the selected drive.
    """
    def __init__(self):
        """
        Initializes the DiskWidget.
        """
        super().__init__("Disk Usage")
        self.current_data = {}
        self.selected_path = None
        self.buttons = {} # path -> ModernDriveIcon

        # Icons Layout
        self.icons_widget = QWidget()
        self.icons_layout = QHBoxLayout(self.icons_widget)
        self.icons_layout.setContentsMargins(0, 0, 0, 0)
        self.icons_layout.setSpacing(10)
        self.icons_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.layout.addWidget(self.icons_widget)

        # Selected Drive Name
        self.model_label = QLabel("Scanning...")
        self.model_label.setStyleSheet(
            f"color: {ModernTheme.ACCENT_CYAN}; font-weight: bold; font-size: 14px;"
        )
        self.model_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.model_label)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {ModernTheme.ACCENT_ORANGE}; }}"
        )
        self.val_label = QLabel("0 / 0 GB")
        self.val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.layout.addWidget(self.bar)
        self.layout.addWidget(self.val_label)
        self.layout.addStretch()

    def refresh_theme(self):
        """Refreshes the widget's colors based on the current ModernTheme."""
        self.model_label.setStyleSheet(
            f"color: {ModernTheme.ACCENT_CYAN}; font-weight: bold; font-size: 14px;"
        )
        self.bar.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {ModernTheme.ACCENT_ORANGE}; }}"
        )
        for btn in self.buttons.values():
            btn.update()

    def update_data(self, disks_dict):
        """
        Updates the displayed disk data and refreshes the drive icons.

        Args:
            disks_dict (dict): A dictionary where keys are disk paths (str)
                               and values are dictionaries of disk statistics.
        """
        self.current_data = disks_dict

        current_keys = set(self.current_data.keys())
        existing_keys = set(self.buttons.keys())

        if current_keys != existing_keys:
            # Clear existing buttons
            for btn in self.buttons.values():
                self.icons_layout.removeWidget(btn)
                btn.deleteLater()
            self.buttons = {}

            # Create new buttons
            # Sort keys to keep order stable
            for path in sorted(list(current_keys)):
                btn = ModernDriveIcon()

                # Tooltip
                data = self.current_data[path]
                btn.setToolTip(f"{data['model']} ({path})")

                # Connect
                btn.clicked.connect(lambda checked, p=path: self.select_drive(p))

                self.icons_layout.addWidget(btn)
                self.buttons[path] = btn

            # Restore or Default Selection
            if self.selected_path in current_keys:
                self.select_drive(self.selected_path)
            elif current_keys:
                # Default to the first available drive if no previous selection or old selection is gone
                self.select_drive(sorted(list(current_keys))[0])

        # Refresh data for currently selected drive
        if self.selected_path and self.selected_path in self.current_data:
            self.refresh_display()

    def select_drive(self, path):
        """
        Selects a drive and updates the display to show its statistics.

        Args:
            path (str): The path of the drive to select.
        """
        self.selected_path = path

        # Update Styles (Highlight selected)
        for p, btn in self.buttons.items():
            btn.set_active(p == path)

        self.refresh_display()

    def refresh_display(self):
        """
        Refreshes the displayed information for the currently selected drive.
        """
        if not self.selected_path or self.selected_path not in self.current_data:
            return

        stats = self.current_data[self.selected_path]

        # Update Model Name Label
        total_gb = stats['size'] / (1024**3)
        if total_gb >= 1000:
            size_str = f"{total_gb/1024:.2f} TiB"
        else:
            size_str = f"{total_gb:.1f} GiB"
        self.model_label.setText(f"{stats['model']} ({size_str})")

        # Update Bar
        self.bar.setValue(int(stats['percent']))

        # Update Value Label
        used_gb = stats['used'] / (1024**3)
        if total_gb >= 1000:
            used_str = f"{used_gb/1024:.2f} TiB"
            total_str = f"{total_gb/1024:.2f} TiB"
        else:
            used_str = f"{used_gb:.1f} GiB"
            total_str = f"{total_gb:.1f} GiB"

        self.val_label.setText(f"{used_str} / {total_str}")

class DiskIOWidget(Card):
    def __init__(self):
        super().__init__("Hard Disk Activity")

        self.maxlen = 90
        self.update_interval = 0
        self.last_update_time = 0
        self.read_history = deque([0]*self.maxlen, maxlen=self.maxlen)
        self.write_history = deque([0]*self.maxlen, maxlen=self.maxlen)

        # Read Rate Row
        read_layout = QHBoxLayout()
        self.read_label = QLabel("Read Rate")
        self.read_val = QLabel("0.0 B/s")
        self.read_val.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.read_bar = QProgressBar()
        self.read_bar.setRange(0, 100)
        self.read_bar.setTextVisible(False)
        self.read_bar.setFixedHeight(8)
        self.read_bar.setStyleSheet(f"""
            QProgressBar::chunk {{ background-color: {ModernTheme.ACCENT_BLUE}; }}
        """)

        # Write Rate Row
        write_layout = QHBoxLayout()
        self.write_label = QLabel("Write Rate")
        self.write_val = QLabel("0.0 B/s")
        self.write_val.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.write_bar = QProgressBar()
        self.write_bar.setRange(0, 100)
        self.write_bar.setTextVisible(False)
        self.write_bar.setFixedHeight(8)
        self.write_bar.setStyleSheet(f"""
            QProgressBar::chunk {{ background-color: {ModernTheme.ACCENT_RED}; }}
        """)

        # Add to layout
        # Read
        read_top = QHBoxLayout()
        read_top.addWidget(self.read_label)
        read_top.addWidget(self.read_val)
        self.layout.addLayout(read_top)
        self.layout.addWidget(self.read_bar)

        self.layout.addSpacing(10)

        # Write
        write_top = QHBoxLayout()
        write_top.addWidget(self.write_label)
        write_top.addWidget(self.write_val)
        self.layout.addLayout(write_top)
        self.layout.addWidget(self.write_bar)

        self.layout.addSpacing(10)

        # Graph Area
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

    def refresh_theme(self):
        """Refreshes the widget's colors based on the current ModernTheme."""
        self.read_bar.setStyleSheet(f"""
            QProgressBar::chunk {{ background-color: {ModernTheme.ACCENT_BLUE}; }}
        """)
        self.write_bar.setStyleSheet(f"""
            QProgressBar::chunk {{ background-color: {ModernTheme.ACCENT_RED}; }}
        """)
        self.graph_area.update()

    def set_duration(self, seconds, interval=0):
        self.maxlen = seconds
        self.update_interval = interval

        # Reset deques to avoid mixed time-scales
        self.read_history = deque([0]*self.maxlen, maxlen=self.maxlen)
        self.write_history = deque([0]*self.maxlen, maxlen=self.maxlen)
        self.graph_area.update()

    def update_data(self, stats):
        read_speed = stats['read']
        write_speed = stats['write']

        self.read_val.setText(self.format_speed(read_speed))
        self.write_val.setText(self.format_speed(write_speed))

        # Scale bars logarithmically or caps?
        # Let's use a cap of 100 MB/s for visual scaling for now, or somewhat dynamic
        # Simple cap at 500 MB/s for modern SSDs
        max_speed = 500 * 1024 * 1024

        r_pct = min(100, (read_speed / max_speed) * 100)
        w_pct = min(100, (write_speed / max_speed) * 100)

        # If speed is low but non-zero, show a little bit
        if read_speed > 0 and r_pct < 1: r_pct = 1
        if write_speed > 0 and w_pct < 1: w_pct = 1

        self.read_bar.setValue(int(r_pct))
        self.write_bar.setValue(int(w_pct))

        # Throttle history update
        now = time.time()
        if self.update_interval > 0 and (now - self.last_update_time) < self.update_interval:
            return

        self.last_update_time = now
        self.read_history.append(read_speed)
        self.write_history.append(write_speed)

        self.graph_area.update()

        # Update tooltip if visible
        if self.tooltip_widget.isVisible() and self.hover_index != -1:
            if self.hover_index < len(self.read_history):
                r_val = self.read_history[self.hover_index]
                w_val = self.write_history[self.hover_index]

                # Calculate Time Offset for Tooltip
                interval = max(1, self.update_interval)
                seconds_ago = (self.maxlen - 1 - self.hover_index) * interval
                time_str = format_time_offset(seconds_ago)

                self.tooltip_widget.update_info(
                    f"Time: -{time_str}\nRead: {self.format_speed(r_val)}\nWrite: {self.format_speed(w_val)}"
                )

    def eventFilter(self, source, event):
        if source == self.graph_area:
            if event.type() == QEvent.Type.MouseMove:
                if len(self.read_history) < 2:
                    return False

                rect = self.graph_area.rect()
                x = event.pos().x()
                width = rect.width()

                step_x = width / (self.maxlen - 1)
                index = int(round(x / step_x))
                index = max(0, min(index, len(self.read_history) - 1))

                self.hover_index = index
                self.hover_pos = event.pos()

                r_val = self.read_history[index]
                w_val = self.write_history[index]

                # Calculate Time Offset for Tooltip
                interval = max(1, self.update_interval)
                seconds_ago = (self.maxlen - 1 - index) * interval
                time_str = format_time_offset(seconds_ago)

                self.tooltip_widget.update_info(
                    f"Time: -{time_str}\nRead: {self.format_speed(r_val)}\nWrite: {self.format_speed(w_val)}"
                )

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

        # Determine Max Y for scaling (local max in history)
        max_val = max(max(self.read_history, default=0), max(self.write_history, default=0))
        if max_val == 0: max_val = 100 # Default scale to avoid div zero

        # Add some headroom (e.g., 20%)
        max_val = max_val * 1.2

        # Draw Grid (3 lines)
        grid_pen = QPen(QColor(ModernTheme.BORDER_COLOR))
        grid_pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(grid_pen)

        for i in range(1, 4):
            y = top_margin + graph_h - (i * (graph_h / 4))
            painter.drawLine(0, int(y), w, int(y))
            # Optional: Draw value text for grid
            val_at_line = max_val * (i / 4)
            painter.drawText(2, int(y) - 2, self.format_speed(val_at_line))

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

        # Helper to draw line
        def draw_line(data_deque, color_hex):
            if len(data_deque) < 2: return

            path = QPainterPath()
            step_x = w / (self.maxlen - 1)

            points = list(data_deque)

            # Start
            start_y = top_margin + graph_h - ((points[0] / max_val) * graph_h)
            path.moveTo(0, start_y)

            for i, val in enumerate(points):
                x = i * step_x
                y = top_margin + graph_h - ((val / max_val) * graph_h)
                path.lineTo(x, y)

            pen = QPen(QColor(color_hex), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

            # Draw Dot if hovered
            if self.hover_index != -1 and self.hover_index < len(points):
                val = points[self.hover_index]
                hx = self.hover_index * step_x
                hy = top_margin + graph_h - ((val / max_val) * graph_h)

                # Draw Vertical Line
                painter.setPen(QPen(QColor(ModernTheme.BORDER_COLOR), 1, Qt.PenStyle.DashLine))
                painter.drawLine(int(hx), 0, int(hx), int(h - bottom_margin))

                painter.setBrush(QBrush(QColor(color_hex)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(hx, hy), 4, 4)

        # Draw Read (Blue)
        draw_line(self.read_history, ModernTheme.ACCENT_BLUE)

        # Draw Write (Red)
        draw_line(self.write_history, ModernTheme.ACCENT_RED)

    def format_speed(self, bytes_sec):
        """
        Formats a given speed in bytes per second into a human-readable string
        (e.g., KB/s, MB/s, GB/s).

        Args:
            bytes_sec (float): The speed in bytes per second.

        Returns:
            str: A formatted string representing the speed.
        """
        if bytes_sec >= 1024**3:
            return f"{bytes_sec / (1024**3):.1f} GB/s"
        elif bytes_sec >= 1024**2:
            return f"{bytes_sec / (1024**2):.1f} MB/s"
        elif bytes_sec >= 1024:
            return f"{bytes_sec / 1024:.1f} KB/s"
        else:
            return f"{bytes_sec:.1f} B/s"
