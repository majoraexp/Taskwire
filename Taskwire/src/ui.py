# pylint: disable=E0611
"""
This module contains custom UI widgets for the Modern Linux Task Manager,
built using PyQt6. It includes various gauges, graphs, and a process list
widget with custom drawing and styling.
"""
import math
import time
import re
import html
import subprocess
import shutil
from collections import deque

from PyQt6.QtCore import Qt, QRectF, QSize, QPointF, QPoint, QEvent, QTimer, QProcess
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QPainterPath, QLinearGradient, 
    QPolygonF, QBrush, QRadialGradient, QAction, QPalette
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QFrame, QGridLayout, QTableWidget, 
    QTableWidgetItem, QHeaderView, QAbstractItemView,
    QPushButton, QMessageBox, QLineEdit, QAbstractButton,
    QMenu, QStackedWidget, QDialog, QCheckBox, QDialogButtonBox, QHeaderView,
    QSizePolicy, QPlainTextEdit, QComboBox, QFileDialog
)

from .styles import ModernTheme

def format_time_offset(seconds):
    """
    Formats a time offset (in seconds) into a short string (e.g., "30s", "5m 30s").
    """
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds}s"
    else:
        m = seconds // 60
        s = seconds % 60
        if s > 0:
            return f"{m}m {s}s"
        return f"{m}m"

class GameTooltip(QWidget):
    """
    A custom tooltip widget designed to mimic a game HUD style.
    It displays text with a semi-transparent background and neon border.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.text = ""
        # Use a slightly larger/clearer font
        font = QFont()
        font.setPointSize(10)
        self.setFont(font)

    def update_info(self, text):
        """
        Updates the tooltip's text and resizes it accordingly.

        Args:
            text (str): The new text to display in the tooltip.
        """
        if self.text != text:
            self.text = text
            self.adjustSize()
            self.update()

    def paintEvent(self, event): # pylint: disable=C0103,W0613
        """
        Paints the custom tooltip, including its background, border, and text.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        
        # Semi-transparent Background (Themed)
        bg_color = QColor(ModernTheme.WIDGET_BACKGROUND)
        bg_color.setAlpha(230) # Higher opacity for better readability in light mode
        painter.setBrush(QBrush(bg_color))
        
        # Neon Border
        painter.setPen(QPen(QColor(ModernTheme.ACCENT_PURPLE), 1))
        painter.drawRoundedRect(rect.adjusted(0,0,-1,-1), 5, 5)
        
        # Text
        painter.setPen(QColor(ModernTheme.TEXT_PRIMARY))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text)

    def sizeHint(self):
        """
        Returns the recommended size for the tooltip based on its content.
        """
        fm = self.fontMetrics()
        s = fm.size(0, self.text)
        # Add padding
        return QSize(s.width() + 20, s.height() + 15)

class Card(QFrame):
    """
    A custom QFrame widget that acts as a base card for displaying information.
    It includes a title and a vertical layout.
    """
    def __init__(self, title=""):
        """
        Initializes the Card widget.

        Args:
            title (str): The title to display on the card. Defaults to an empty string.
        """
        super().__init__()
        self.setProperty("class", "card")
        self.layout = QVBoxLayout(self)
        
        if title:
            self.title_label = QLabel(title)
            self.title_label.setProperty("class", "title")
            self.layout.addWidget(self.title_label)
            self.layout.addSpacing(10)

class CircularGauge(QWidget):
    """
    A custom circular gauge widget to display percentage and GiB usage.
    Features hover-sensitive arcs and dynamic text display.
    """
    def __init__(self):
        """
        Initializes the CircularGauge widget.
        """
        super().__init__()
        self.percent = 0
        self.used_gb = 0
        self.total_gb = 0
        self.setMinimumSize(160, 160) # Reduced to 160 for tighter layouts
        self.setMaximumSize(160, 160) # Force fixed size to prevent expansion
        self.setMouseTracking(True)
        self.hover_section = None # 'used', 'free', or None
        self.tooltip_widget = GameTooltip()

    def set_data(self, percent, used_gb, total_gb):
        """
        Sets the data for the circular gauge.

        Args:
            percent (float): The percentage of usage.
            used_gb (float): The amount of used gigabytes.
            total_gb (float): The total amount of gigabytes.
        """
        self.percent = percent
        self.used_gb = used_gb
        self.total_gb = total_gb
        self.update()
    def mouseMoveEvent(self, event): # pylint: disable=C0103
        """
        Handles mouse movement events to detect hover on 'used' or 'free' sections
        of the gauge and display a custom tooltip.
        """
        rect = self.rect()
        # Same size calculation as paintEvent
        size = min(rect.width(), rect.height()) - 20 # Reduced padding
        radius = size / 2
        center = rect.center()
        
        dx = event.pos().x() - center.x()
        dy = event.pos().y() - center.y()
        dist = math.sqrt(dx*dx + dy*dy)
        
        # Check if mouse is roughly on the ring (radius +/- 15px tolerance)
        if abs(dist - radius) < 15:
            # Calculate angle in degrees, 0 at Top, Clockwise
            angle_rad = math.atan2(dy, dx)
            angle_deg = math.degrees(angle_rad)
            
            # Convert to 0-360 Clockwise from Top
            cw_angle = angle_deg + 90
            if cw_angle < 0:
                cw_angle += 360
                
            used_deg = self.percent * 3.6
            
            text_to_show = ""
            if 0 <= cw_angle <= used_deg:
                if self.hover_section != 'used':
                    self.hover_section = 'used'
                    self.update()
                text_to_show = f"Used: {self.percent:.1f}% ({self.used_gb:.1f} GiB)"
            else:
                if self.hover_section != 'free':
                    self.hover_section = 'free'
                    self.update()
                free_gb = max(0.0, self.total_gb - self.used_gb)
                free_pct = max(0.0, 100.0 - self.percent)
                text_to_show = f"Free: {free_pct:.1f}% ({free_gb:.1f} GiB)"
            
            # Show Custom Tooltip
            if text_to_show:
                self.tooltip_widget.update_info(text_to_show)
                # Position tooltip near mouse (offset)
                global_pos = event.globalPosition().toPoint()
                self.tooltip_widget.move(global_pos + QPoint(20, 20))
                self.tooltip_widget.show()
                
        else:
            if self.hover_section is not None:
                self.hover_section = None
                self.update()
            self.tooltip_widget.hide()
        
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):  # pylint: disable=C0103
        if self.hover_section is not None:
            self.hover_section = None
            self.update()
        self.tooltip_widget.hide()
        super().leaveEvent(event)

    def paintEvent(self, event): # pylint: disable=C0103,W0613
        """
        Paints the circular gauge, including arcs for used and free space,
        and displays percentage and GiB values.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        # Keep gauge size consistent with 200x200 widget size
        size = min(rect.width(), rect.height()) - 20
        x = (rect.width() - size) / 2
        y = (rect.height() - size) / 2
        
        stroke_width = 6
        
        # Angles (PyQt uses 1/16th degree)
        # Start at Top (90 degrees)
        start_angle = 90 * 16 
        
        span_angle_used = int(-self.percent * 3.6 * 16) # Negative for clockwise
        span_angle_free = int(-(100 - self.percent) * 3.6 * 16)
        
        # Determine Colors based on hover
        color_used = QColor(ModernTheme.ACCENT_RED)
        color_free = QColor(ModernTheme.ACCENT_GREEN)
        
        if self.hover_section == 'used':
            color_used = color_used.lighter(130) # Brighten
            color_free = color_free.darker(200)  # Darken significantly
        elif self.hover_section == 'free':
            color_free = color_free.lighter(130) # Brighten
            color_used = color_used.darker(200)  # Darken significantly
        
        # Draw Used Arc (Red)
        pen_used = QPen(color_used, stroke_width)
        pen_used.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_used)
        painter.drawArc(int(x), int(y), int(size), int(size), start_angle, span_angle_used)
        
        # Draw Free Arc (Green)
        pen_free = QPen(color_free, stroke_width)
        pen_free.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_free)
        # Start where used ended
        painter.drawArc(int(x), int(y), int(size), int(size), start_angle + span_angle_used, span_angle_free)
        
        # Draw Text (Percentage and Used GiB)
        painter.setPen(QColor(ModernTheme.TEXT_PRIMARY))
        
        # Helper to draw centered text (internal to the gauge)
        def draw_internal_text(text, y_offset, font_size, bold=False, color=None):
            font = QFont()
            font.setPointSize(font_size)
            font.setBold(bold)
            painter.setFont(font)
            if color: painter.setPen(QColor(color))
            else: painter.setPen(QColor(ModernTheme.TEXT_PRIMARY))
            
            metrics = painter.fontMetrics()
            text_rect = metrics.boundingRect(text)
            center_x = rect.center().x()
            center_y = rect.center().y()
            
            painter.drawText(int(center_x - text_rect.width()/2), 
                             int(center_y + y_offset), 
                             text)

        # Percentage (Main, large text in center)
        draw_internal_text(f"{self.percent:.1f}%", -10, 20, bold=True) # Reduced font size
        # Used GiB (Smaller text below percentage)
        draw_internal_text(f"{self.used_gb:.1f} GiB", 25, 12, bold=True) # Reduced font size

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
                f"<span style='color: {ModernTheme.TEXT_PRIMARY};'>{value:.1f}°C</span>"
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
                        tooltip_lines.append(f"{name}: {val:.1f}°C")
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
                            tooltip_lines.append(f"{name}: {val:.1f}°C")
                        
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
            painter.drawText(2, int(y) - 2, f"{t}°C")

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

class MemoryAllocationBar(QWidget):
    """
    A segmented horizontal bar showing memory allocation breakdown:
    App Memory, Buffers, Cache, Free. Hover each segment for a tooltip.
    """
    _SEGS = [
        ("App Memory", "ACCENT_RED"),
        ("Buffers",    "ACCENT_PURPLE"),
        ("Cache",      "ACCENT_BLUE"),
        ("Free",       "ACCENT_GREEN"),
    ]
    _BAR_H    = 16
    _LEGEND_H = 38

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.values = [0, 0, 0, 0]
        self.total  = 1
        self._tooltip = GameTooltip(self)
        self._hover   = None
        self._legend_font = QFont()
        self._legend_font.setPointSize(8)
        self.setMinimumWidth(190)
        total_h = self._BAR_H + self._LEGEND_H
        self.setMinimumHeight(total_h)
        self.setMaximumHeight(total_h)

    def set_data(self, total, used, buffers, cached, free):
        self.total  = max(total, 1)
        self.values = [used, buffers, cached, free]
        self.update()

    def _widths(self):
        w = max(self.width(), 1)
        return [(v / self.total) * w for v in self.values]

    def mouseMoveEvent(self, event):  # pylint: disable=C0103
        px, x, new_hover = event.pos().x(), 0.0, None
        for i, sw in enumerate(self._widths()):
            if x <= px < x + sw:
                new_hover = i
                pct = (self.values[i] / self.total) * 100
                gib = self.values[i] / (1024 ** 3)
                self._tooltip.update_info(f"{self._SEGS[i][0]}: {pct:.1f}% ({gib:.2f} GiB)")
                gp = event.globalPosition().toPoint()
                self._tooltip.move(gp + QPoint(20, 20))
                self._tooltip.show()
                break
            x += sw
        if new_hover is None:
            self._tooltip.hide()
        if new_hover != self._hover:
            self._hover = new_hover
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):  # pylint: disable=C0103
        if self._hover is not None:
            self._hover = None
            self.update()
        self._tooltip.hide()
        super().leaveEvent(event)

    def paintEvent(self, event):  # pylint: disable=C0103,W0613
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect    = self.rect()
        widths  = self._widths()

        # Clip all segments to a rounded bar shape
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, rect.width(), self._BAR_H), 4, 4)
        painter.setClipPath(clip)

        # Background fill handles any gap from slab/overhead not in the four segments
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(ModernTheme.ALTERNATE_TABLE_BG)))
        painter.drawRect(QRectF(0, 0, rect.width(), self._BAR_H))

        x = 0.0
        for i, sw in enumerate(widths):
            if sw < 0.5:
                x += sw
                continue
            color = QColor(getattr(ModernTheme, self._SEGS[i][1]))
            if self._hover is not None:
                color = color.lighter(120) if self._hover == i else color.darker(200)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRect(QRectF(x, 0, sw, self._BAR_H))
            x += sw

        painter.setClipping(False)

        # 2×2 legend grid below the bar
        painter.setFont(self._legend_font)
        fm      = painter.fontMetrics()
        top     = self._BAR_H + 5

        for i, (label, attr) in enumerate(self._SEGS):
            pct   = (self.values[i] / self.total) * 100
            text  = f"{label}: {pct:.0f}%"
            col, row = i % 2, i // 2

            # Left-align column 0, right-align column 1
            if col == 0:
                lx = 0
            else:
                text_width = fm.horizontalAdvance(text)
                lx = rect.width() - (9 + text_width)

            ly = top + row * (fm.height() + 2)
            color = QColor(getattr(ModernTheme, attr))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            dot_y = ly + (fm.height() - 6) / 2
            painter.drawEllipse(QRectF(lx, dot_y, 6, 6))

            painter.setPen(QColor(ModernTheme.TEXT_PRIMARY))
            painter.drawText(int(lx + 9), int(ly + fm.ascent()), text)


class MemoryWidget(Card):
    """
    A widget to display system memory usage using a circular gauge and text labels.
    """
    def __init__(self):
        """
        Initializes the MemoryWidget.
        """
        super().__init__("Memory Usage")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        
        # Labels for text above and below the gauge
        self.used_label_top = QLabel("Used Physical Memory")
        self.used_label_top.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.used_label_top.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY}; font-size: 11px;") # Brighter white
        self.layout.addWidget(self.used_label_top)

        self.gauge = CircularGauge()
        self.layout.addWidget(self.gauge, 0, Qt.AlignmentFlag.AlignHCenter)

        self.total_label_bottom = QLabel("") # Will set text in update_data
        self.total_label_bottom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_label_bottom.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY}; font-size: 11px;") # Brighter white
        self.layout.addWidget(self.total_label_bottom)

        # Memory allocation breakdown bar
        self.alloc_label = QLabel("Memory Allocation")
        self.alloc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.alloc_label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY}; font-size: 10px; margin-top: 6px;")
        self.layout.addWidget(self.alloc_label)

        self.alloc_bar = MemoryAllocationBar()
        self.layout.addWidget(self.alloc_bar)

    def refresh_theme(self):
        """Refreshes the widget's colors based on the current ModernTheme."""
        self.used_label_top.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY}; font-size: 11px;")
        self.total_label_bottom.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY}; font-size: 11px;")
        self.alloc_label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY}; font-size: 10px; margin-top: 6px;")
        self.gauge.update()
        self.alloc_bar.update()

    def update_data(self, stats):
        """
        Updates the memory usage data displayed by the widget.

        Args:
            stats (dict): A dictionary containing memory statistics,
                          e.g., 'total', 'available', 'percent'.
        """
        used_gb = (stats['total'] - stats['available']) / (1024**3)
        total_gb = stats['total'] / (1024**3)
        self.gauge.set_data(stats['percent'], used_gb, total_gb)
        self.used_label_top.setText("Used Physical Memory")
        self.total_label_bottom.setText(f"{total_gb:.1f} GiB Total Physical Memory")
        self.alloc_bar.set_data(
            stats['total'],
            stats['used'],
            stats.get('buffers', 0),
            stats.get('cached', 0),
            stats.get('free', 0),
        )

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

class SortableTableWidgetItem(QTableWidgetItem):
    """
    A custom QTableWidgetItem that supports sorting based on user-defined data
    (Qt.ItemDataRole.UserRole) or falls back to string comparison.
    """
    def __lt__(self, other):
        """
        Compares this item with another for sorting purposes.
        Sorts by UserRole data if available, otherwise falls back to case-insensitive string comparison.
        """
        # Sort by UserRole (numeric/raw value) if available
        my_val = self.data(Qt.ItemDataRole.UserRole)
        other_val = other.data(Qt.ItemDataRole.UserRole)
        
        # Handle None cases safely
        if my_val is None: my_val = 0
        if other_val is None: other_val = 0
            
        try:
            # Case-insensitive string sort
            if isinstance(my_val, str) and isinstance(other_val, str):
                return my_val.lower() < other_val.lower()
            return my_val < other_val
        except TypeError:
            # Fallback to string comparison if types don't match
            return str(my_val).lower() < str(other_val).lower()

class ModernHeader(QHeaderView):
    """
    A custom QHeaderView for QTableWidget, providing themed styling,
    movable/clickable sections, and a drag-and-drop indicator.
    """
    def __init__(self, orientation, parent=None):
        """
        Initializes the ModernHeader.

        Args:
            orientation (Qt.Orientation): The orientation of the header (Horizontal or Vertical).
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(orientation, parent)
        self.setSectionsMovable(True)
        self.setSectionsClickable(True) # Explicitly enable clicking
        self.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.setStretchLastSection(False)
        self.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(True) # Required for move events without click? No, drag implies click.
        
        self.drag_active = False
        self.drop_indicator_x = -1

    def mousePressEvent(self, event): # pylint: disable=C0103
        """
        Handles mouse press events, activating drag functionality for sections.
        """
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            # Only start tracking if we are actually clicking on a movable section
            # For simplicity, assume yes if left click.
            self.drag_active = True

    def mouseMoveEvent(self, event): # pylint: disable=C0103
        """
        Handles mouse move events, updating the drag indicator position during a drag operation.
        """
        super().mouseMoveEvent(event)
        if self.drag_active and (event.buttons() & Qt.MouseButton.LeftButton):
            # Calculate drop position
            pos_x = event.pos().x()
            logical_idx = self.logicalIndexAt(event.pos())
            
            # Find visual rect of this section
            visual_idx = self.visualIndex(logical_idx)
            if visual_idx == -1: return # invalid
            
            # Get geometry
            # This requires converting back to viewport coords sometimes, but let's assume sectionViewportPosition works
            section_x = self.sectionViewportPosition(logical_idx)
            section_w = self.sectionSize(logical_idx)
            
            # Determine if we are closer to left or right edge
            center = section_x + (section_w / 2)
            if pos_x < center:
                self.drop_indicator_x = section_x
            else:
                self.drop_indicator_x = section_x + section_w
                
            self.viewport().update()

    def mouseReleaseEvent(self, event): # pylint: disable=C0103
        """
        Handles mouse release events, deactivating drag and hiding the indicator.
        """
        super().mouseReleaseEvent(event)
        self.drag_active = False
        self.drop_indicator_x = -1
        self.viewport().update()

    def paintEvent(self, event): # pylint: disable=C0103
        """
        Paints the header, including the base painting and an overlay for the drop indicator.
        """
        super().paintEvent(event)
        # Draw Drop Indicator on top
        if self.drag_active and self.drop_indicator_x >= 0:
            painter = QPainter(self.viewport())
            # Red Line
            painter.setPen(QPen(QColor(ModernTheme.ACCENT_RED), 2))
            painter.drawLine(self.drop_indicator_x, 0, self.drop_indicator_x, self.height())

    def paintSection(self, painter, rect, logicalIndex): # pylint: disable=C0103,W0613
        """
        Paints a single section of the header, adding a themed separator.
        """
        painter.save()
        super().paintSection(painter, rect, logicalIndex)
        painter.restore()

        # Draw Visible Themed Separator (Accent Blue)
        painter.save()
        # Draw on the right edge
        # Adjust x by -1 to stay inside rect or on edge
        painter.setPen(QPen(QColor(ModernTheme.ACCENT_BLUE), 1)) 
        painter.drawLine(rect.topRight() - QPoint(1, 0), rect.bottomRight() - QPoint(1, 0))
        painter.restore()

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
            
            # Save scroll position and selection to prevent jumping
            current_scroll = table.verticalScrollBar().value()
            current_row = table.currentRow()
            
            # Clear selection so render_table doesn't follow the process
            table.clearSelection()

            self.update_sort_indicator(table, visible)
            self.refresh_current_view(maintain_selection=False)
            
            # Restore selection to the same row index
            if current_row >= 0 and current_row < table.rowCount():
                table.selectRow(current_row)

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

class ModernGaugeWidget(Card):
    """
    A customizable circular gauge widget that displays a percentage and
    optionally detailed values (e.g., used/total) inside the gauge.
    """
    def __init__(self, title, color_hex=ModernTheme.ACCENT_CYAN):
        """
        Initializes the ModernGaugeWidget.

        Args:
            title (str): The title of the gauge card.
            color_hex (str): The hexadecimal color string for the gauge's progress arc.
                             Defaults to ModernTheme.ACCENT_CYAN.
        """
        super().__init__(title)
        self.percent = 0
        self.text_lines_values = [] # Only for values inside the gauge
        self.color = QColor(color_hex)
        
        # External labels for titles (above and below the gauge area)
        self.label_used_ext = QLabel()
        self.label_used_ext.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_used_ext.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY}; font-size: 11px;") # Brighter white
        self.layout.insertWidget(1, self.label_used_ext) # Insert after title_label
        self.label_used_ext.hide()

        self.gauge_area = QWidget()
        self.gauge_area.setMinimumHeight(140)
        self.gauge_area.paintEvent = self.paint_gauge
        self.layout.addWidget(self.gauge_area, 1)
        
        self.label_total_ext = QLabel()
        self.label_total_ext.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_total_ext.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY}; font-size: 11px;") # Brighter white
        self.layout.addWidget(self.label_total_ext)
        self.label_total_ext.hide()
        
    def set_color(self, color_hex):
        """Sets the gauge color dynamically."""
        self.color = QColor(color_hex)
        self.gauge_area.update()

    def refresh_theme(self):
        """Refreshes the widget's colors based on the current ModernTheme."""
        self.label_used_ext.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY}; font-size: 11px;")
        self.label_total_ext.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY}; font-size: 11px;")
        
        # Update internal text values color
        for line in self.text_lines_values:
            line["color"] = ModernTheme.TEXT_PRIMARY
            
        self.gauge_area.update()
        
    def set_simple_percent(self, percent):
        """
        Sets the gauge to display a simple percentage value.

        Args:
            percent (float): The percentage value to display.
        """
        self.percent = percent
        self.text_lines_values = [
            {"text": f"{percent:.1f}%", "size": 24, "bold": True, "color": ModernTheme.TEXT_PRIMARY}
        ]
        self.label_used_ext.hide()
        self.label_total_ext.hide()
        self.gauge_area.update()
        
    def set_detailed_data(self, percent, used, total, unit="GiB", label_used="Used", label_total="Total"):
        """
        Sets the gauge to display detailed data with used and total values,
        along with custom labels and units.

        Args:
            percent (float): The percentage value for the progress arc.
            used (float): The used amount.
            total (float): The total amount.
            unit (str): The unit for used and total values (e.g., "GiB", "MB").
            label_used (str): The label for the used amount, displayed above the gauge.
            label_total (str): The label for the total amount, displayed below the gauge.
        """
        self.percent = percent
        
        self.label_used_ext.setText(label_used)
        self.label_used_ext.show()
        
        self.text_lines_values = [
            {"text": f"{used:.1f} {unit}", "size": 16, "bold": True, "color": ModernTheme.TEXT_PRIMARY},
            {"text": f"{total:.1f} {unit}", "size": 16, "bold": True, "color": ModernTheme.TEXT_PRIMARY},
        ]
        
        self.label_total_ext.setText(label_total)
        self.label_total_ext.show()

        self.gauge_area.update()

    def paint_gauge(self, event): # pylint: disable=C0103,W0613
        """
        Paints the circular gauge with a track, a progress arc, and centered text values.
        """
        painter = QPainter(self.gauge_area)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.gauge_area.width()
        h = self.gauge_area.height()
        # rect = self.gauge_area.rect() # Unused
        
        # Calculate size (keep square)
        size = min(w, h) - 10 
        x = (w - size) / 2
        y = (h - size) / 2
        
        stroke_width = 6
        
        # 1. Draw Track (Background Ring)
        track_pen = QPen(QColor("#2e2e3e"), 6)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawEllipse(int(x), int(y), int(size), int(size))
        
        # 2. Draw Progress Arc
        # Start at -90 (Top)
        start_angle = 90 * 16
        span_angle = int(-self.percent * 3.6 * 16)
        
        prog_pen = QPen(self.color, 6)
        prog_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(prog_pen)
        painter.drawArc(int(x), int(y), int(size), int(size), start_angle, span_angle)
        
        # 3. Draw Text Values (Centered within gauge area)
        # Center point
        cx = w / 2
        cy = h / 2
        
        if len(self.text_lines_values) == 1:
            # Simple Centered
            line = self.text_lines_values[0]
            font = QFont()
            # Scale font size based on gauge size?
            # Base size 24 for 140px. Ratio ~ 0.17
            dynamic_size = max(12, int(size * 0.18))
            
            font.setPointSize(dynamic_size)
            font.setBold(line["bold"])
            painter.setFont(font)
            painter.setPen(QColor(line["color"]))
            
            fm = painter.fontMetrics()
            t_w = fm.horizontalAdvance(line["text"])
            painter.drawText(int(cx - t_w/2), int(cy + fm.ascent()/2 - 5), line["text"])
            
        elif len(self.text_lines_values) == 2:
            # Stacked detailed values
            # Scale font
            dynamic_size = max(10, int(size * 0.12))
            
            offsets = [-int(size*0.1), int(size*0.1)] # Offset from center
            
            for i, line in enumerate(self.text_lines_values):
                font = QFont()
                font.setPointSize(dynamic_size)
                font.setBold(line["bold"])
                painter.setFont(font)
                painter.setPen(QColor(line["color"]))
                
                fm = painter.fontMetrics()
                t_w = fm.horizontalAdvance(line["text"])
                
                # Draw Line Separator between the two values
                if i == 1: 
                    sep_pen = QPen(QColor(ModernTheme.BORDER_COLOR), 1)
                    painter.setPen(sep_pen)
                    line_len = int(size * 0.4)
                    painter.drawLine(int(cx - line_len), int(cy - 2), int(cx + line_len), int(cy - 2))
                    painter.setPen(QColor(line["color"]))

                painter.drawText(int(cx - t_w/2), int(cy + offsets[i] + fm.ascent()/2 - 5), line["text"])

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

class TopPanelWidget(QWidget):
    """
    A top panel widget that displays key system metrics such as CPU and GPU utilization
    through ModernGaugeWidget, and fan speeds through FanGraphWidget.
    """
    def __init__(self):
        """
        Initializes the TopPanelWidget, setting up CPU, GPU gauges, and fan graph.
        """
        super().__init__()
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(15)

        # CPU Gauge (fixed width so it doesn't expand with the window)
        self.cpu_gauge = ModernGaugeWidget("CPU", ModernTheme.ACCENT_CYAN)
        self.cpu_gauge.setFixedWidth(200)
        self.layout.addWidget(self.cpu_gauge)

        # GPU Gauge (fixed width so it doesn't expand with the window)
        self.gpu_gauge = ModernGaugeWidget("GPU", ModernTheme.ACCENT_BLUE)
        self.gpu_gauge.setFixedWidth(200)
        self.layout.addWidget(self.gpu_gauge)

        # Fan Graph Widget — expands to fill remaining space
        self.fan_widget = FanGraphWidget()
        self.layout.addWidget(self.fan_widget)

        # CPU and GPU stay fixed; Fan Graph stretches to fill remaining width
        self.layout.setStretch(0, 0)
        self.layout.setStretch(1, 0)
        self.layout.setStretch(2, 1)
        
    def refresh_theme(self):
        """Refreshes the theme for all top panel widgets."""
        self.cpu_gauge.set_color(ModernTheme.ACCENT_CYAN)
        self.cpu_gauge.refresh_theme()
        
        self.gpu_gauge.set_color(ModernTheme.ACCENT_BLUE)
        self.gpu_gauge.refresh_theme()
        
        self.fan_widget.refresh_theme()

    def update_cpu(self, overall, *_):
        """
        Updates the CPU utilization gauge.

        Args:
            overall (float): The overall CPU utilization percentage.
            _ (any): Placeholder for additional CPU data not used by this widget.
        """
        self.cpu_gauge.set_simple_percent(overall)
        
    def update_gpu(self, usage):
        """
        Updates the GPU utilization gauge.

        Args:
            usage (float): The GPU utilization percentage.
        """
        self.gpu_gauge.set_simple_percent(usage)
        
    def update_fans(self, fan_data):
        """
        Updates the fan speed graph with new data.

        Args:
            fan_data (dict): A dictionary where keys are fan sensor names (str)
                             and values are their current RPMs (int).
        """
        self.fan_widget.update_data(fan_data)

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
        import os
        
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
            import subprocess
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
        import subprocess
        import os
        import sys
        
        # Determine script path
        # Assuming script is at Taskwire/src/scripts/caps_control.sh relative to app root?
        # Or relative to this file?
        # This file is in Taskwire/src/
        # Script is in Taskwire/src/scripts/
        
        base_path = os.path.dirname(os.path.abspath(__file__)) # Taskwire/src
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
            msg = QLabel("systemctl not found — systemd is not available on this system.")
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
        from PyQt6.QtWidgets import QComboBox
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
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

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
        self._refresh_timer.start(5000)

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

        new_sel_row = -1
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
                new_sel_row = row

        self.table.setSortingEnabled(True)
        self.table.setUpdatesEnabled(True)

        # Restore selection
        if new_sel_row >= 0:
            self.table.selectRow(new_sel_row)

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
        from PyQt6.QtWidgets import QComboBox
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

        new_sel_row = -1
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

            # Local Port
            lp_item = QTableWidgetItem(conn["local_port"])
            lp_item.setFlags(lp_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, lp_item)

            # Peer Address
            pa_item = QTableWidgetItem(conn["peer_addr"])
            pa_item.setFlags(pa_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 4, pa_item)

            # Peer Port
            pp_item = QTableWidgetItem(conn["peer_port"])
            pp_item.setFlags(pp_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 5, pp_item)

            # Process
            proc_item = QTableWidgetItem(conn["process"])
            proc_item.setFlags(proc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 6, proc_item)

            # PID
            pid_item = QTableWidgetItem(conn["pid"])
            pid_item.setFlags(pid_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 7, pid_item)

            if key == selected_key:
                new_sel_row = row

        self.table.setSortingEnabled(True)
        self.table.setUpdatesEnabled(True)

        if new_sel_row >= 0:
            self.table.selectRow(new_sel_row)
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
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            return
        row = sel[0].row()

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


class JournalLogWidget(QWidget):
    """
    Live system log viewer using journalctl.
    Streams logs in real-time via QProcess, with filtering by severity,
    unit/service, boot, and text search with highlighting.
    """

    # journalctl priority levels (0=most severe)
    _PRIORITIES = [
        ("All", None),
        ("Emergency (0)", "0"),
        ("Alert (1)", "1"),
        ("Critical (2)", "2"),
        ("Error (3)", "3"),
        ("Warning (4)", "4"),
        ("Notice (5)", "5"),
        ("Info (6)", "6"),
        ("Debug (7)", "7"),
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
        # Re-highlight search matches with new theme colors
        if self._current_search:
            self._highlight_search(self._current_search)

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

        # Cap buffer during pause to prevent unbounded memory growth
        if self._paused and len(self._line_buffer) > 10000:
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
        """Handle process termination."""
        if exit_code != 0 and not self._paused:
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
