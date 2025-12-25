# pylint: disable=E0611
"""
This module contains custom UI widgets for the Modern Linux Task Manager,
built using PyQt6. It includes various gauges, graphs, and a process list
widget with custom drawing and styling.
"""
import math
from collections import deque

from PyQt6.QtCore import Qt, QRectF, QSize, QPointF, QPoint, QEvent
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QPainterPath, QLinearGradient, 
    QPolygonF, QBrush, QRadialGradient, QAction, QPalette
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QFrame, QGridLayout, QTableWidget, 
    QTableWidgetItem, QHeaderView, QAbstractItemView,
    QPushButton, QMessageBox, QLineEdit, QAbstractButton,
    QMenu, QStackedWidget, QDialog, QCheckBox, QDialogButtonBox, QHeaderView
)

from .styles import ModernTheme

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
        self.setMinimumSize(200, 200) # Reverted to a slightly larger size for readability
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
        size = min(rect.width(), rect.height()) - 40 # Increased padding for text
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
        draw_internal_text(f"{self.percent:.1f}%", -10, 24, bold=True)
        # Used GiB (Smaller text below percentage)
        draw_internal_text(f"{self.used_gb:.1f} GiB", 25, 14, bold=True)

class TempGraphWidget(Card):
    """
    A widget to display a graph of temperature sensor history.
    It shows multiple temperature lines with a grid and legend.
    """
    def __init__(self):
        """
        Initializes the TempGraphWidget.
        """
        super().__init__("Motherboard temp sensors")
        self.maxlen = 90
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
        self.graph_area.setMinimumHeight(100) # Reduced height
        self.graph_area.paintEvent = self.paint_graph
        self.graph_area.setMouseTracking(True)
        self.graph_area.installEventFilter(self)
        self.layout.addWidget(self.graph_area)
        
        # Legend / Values area
        self.legend_layout = QGridLayout()
        self.layout.addLayout(self.legend_layout)
        self.legend_labels = {} # {name: (name_label, value_label)}
        
        # Tooltip State
        self.tooltip_widget = GameTooltip(self.graph_area)
        self.hover_index = -1
        self.hover_pos = QPoint()
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

    def update_data(self, temp_data):
        """
        Updates the temperature history and triggers a graph repaint.

        Args:
            temp_data (dict): A dictionary where keys are sensor names (str)
                              and values are their current temperatures (float).
        """
        # Update History
        for name, value in temp_data.items():
            if name not in self.history:
                self.history[name] = deque([30.0]*self.maxlen, maxlen=self.maxlen)
            self.history[name].append(value)
            
        # Update Legend
        # Clear/Rebuild is inefficient, better to update text
        # But names might change (unlikely), so let's just handle updates
        
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

        self.graph_area.update()

        # Update tooltip if visible
        if self.tooltip_widget.isVisible():
            rect = self.graph_area.rect()
            x = self.hover_pos.x()
            width = rect.width()
            step_x = width / (self.maxlen - 1)
            index = int(round(x / step_x))
            index = max(0, min(index, self.maxlen - 1))
            tooltip_lines = []
            for name, points in self.history.items():
                if index < len(points):
                    val = points[index]
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

                # Construct Tooltip
                tooltip_lines = []
                for name, points in self.history.items():
                    if index < len(points):
                        val = points[index]
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
            # y = h - (normalized * h)
            normalized = (t - min_temp) / temp_range
            y = h - (normalized * h)
            painter.drawLine(0, int(y), w, int(y))
            
            # Text label for grid
            painter.drawText(2, int(y) - 2, f"{t}°C")

        # Draw Lines
        step_x = w / (self.maxlen - 1)
        
        for i, (name, points_deque) in enumerate(self.history.items()):
            if len(points_deque) < 2: continue
            
            points = list(points_deque)
            path = QPainterPath()
            
            # Start point
            start_norm = (points[0] - min_temp) / temp_range
            # Clamp to 0-1
            start_norm = max(0.0, min(1.0, start_norm))
            path.moveTo(0, h - (start_norm * h))
            
            for j, val in enumerate(points):
                x = j * step_x
                norm = (val - min_temp) / temp_range
                norm = max(0.0, min(1.0, norm))
                y = h - (norm * h)
                path.lineTo(x, y)
            
            color = self.colors[i % len(self.colors)]
            pen = QPen(color, 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            
            # Draw Hover Dot
            if self.hover_index != -1 and self.hover_index < len(points):
                val = points[self.hover_index]
                
                # Recalculate position
                hx = self.hover_index * step_x
                norm = (val - min_temp) / temp_range
                norm = max(0.0, min(1.0, norm))
                hy = h - (norm * h)
                
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(hx, hy), 4, 4)

class CpuHistoryWidget(Card):
    """
    A widget to display a historical line graph of total CPU utilization.
    """
    def __init__(self, history_duration=90):
        """
        Initializes the CpuHistoryWidget.

        Args:
            history_duration (int): The number of seconds to keep in the history.
        """
        super().__init__("Total CPU History")
        self.maxlen = history_duration
        self.data_points = deque([0]*self.maxlen, maxlen=self.maxlen)
        
        self.graph_area = QWidget()
        self.graph_area.setMinimumHeight(150)
        self.graph_area.paintEvent = self.paint_graph
        self.graph_area.setMouseTracking(True)
        self.graph_area.installEventFilter(self)
        self.layout.addWidget(self.graph_area)
        
        self.val_label = QLabel("0.0%")
        self.val_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.val_label.setProperty("class", "value")
        self.layout.addWidget(self.val_label)

        # Tooltip State
        self.tooltip_widget = GameTooltip(self.graph_area)
        self.hover_index = -1
        self.hover_pos = QPoint()
        
    def set_duration(self, seconds):
        """
        Sets the duration (in seconds) for which CPU history is maintained.
        """
        self.maxlen = seconds
        # Resize deque, keeping recent data
        self.data_points = deque(self.data_points, maxlen=self.maxlen)
        # Pad if needed (optional, but deque handles truncation)
        while len(self.data_points) < self.maxlen:
            self.data_points.appendleft(0)
        self.graph_area.update()
        
    def update_data(self, cpu_percent):
        """
        Updates the CPU history with a new percentage value and triggers a graph repaint.

        Args:
            cpu_percent (float): The current total CPU utilization percentage.
        """
        self.data_points.append(cpu_percent)
        self.val_label.setText(f"{cpu_percent:.1f}%")
        self.graph_area.update()

        # Update tooltip if visible
        if self.tooltip_widget.isVisible():
            rect = self.graph_area.rect()
            x = self.hover_pos.x()
            width = rect.width()
            step_x = width / (self.maxlen - 1)
            index = int(round(x / step_x))
            index = max(0, min(index, len(self.data_points) - 1))
            val = self.data_points[index]
            self.tooltip_widget.update_info(f"CPU: {val:.1f}%")

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
                # step_x = width / (self.maxlen - 1)
                # index = round(x / step_x)
                step_x = width / (self.maxlen - 1)
                index = int(round(x / step_x))
                
                # Clamp index
                index = max(0, min(index, len(self.data_points) - 1))
                
                self.hover_index = index
                self.hover_pos = event.pos()
                
                # Update Tooltip
                val = self.data_points[index]
                self.tooltip_widget.update_info(f"CPU: {val:.1f}%")
                
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
        
        # Draw Background Grid (Subtle)
        grid_pen = QPen(QColor(ModernTheme.BORDER_COLOR))
        grid_pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(grid_pen)
        for i in range(1, 5):
            y = i * (height / 5)
            painter.drawLine(0, int(y), width, int(y))
        
        # Draw Graph
        if len(self.data_points) < 2:
            return

        path = QPainterPath()
        path.moveTo(0, height) # Start bottom-left
        
        points = list(self.data_points)
        step_x = width / (self.maxlen - 1)
        
        for i, val in enumerate(points):
            x = i * step_x
            y = height - (val / 100 * height)
            path.lineTo(x, y)
            
        path.lineTo(width, height) # Bottom-right
        path.closeSubpath()
        
        # Fill
        fill_color = QColor(ModernTheme.ACCENT_CYAN)
        fill_color.setAlpha(50)
        painter.fillPath(path, fill_color)
        
        # Stroke
        pen = QPen(QColor(ModernTheme.ACCENT_CYAN), 2)
        painter.setPen(pen)
        painter.drawPath(path)
        
        # Draw Hover Dot
        if self.hover_index != -1 and self.hover_index < len(points):
            val = points[self.hover_index]
            hx = self.hover_index * step_x
            hy = height - (val / 100 * height)
            
            painter.setBrush(QBrush(QColor(ModernTheme.ACCENT_CYAN)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(hx, hy), 4, 4)

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

class MemoryWidget(Card):
    """
    A widget to display system memory usage using a circular gauge and text labels.
    """
    def __init__(self):
        """
        Initializes the MemoryWidget.
        """
        super().__init__("Memory Usage")
        
        # Labels for text above and below the gauge
        self.used_label_top = QLabel("Used Physical Memory")
        self.used_label_top.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.used_label_top.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY}; font-size: 11px;") # Brighter white
        self.layout.addWidget(self.used_label_top)

        self.gauge = CircularGauge()
        self.layout.addWidget(self.gauge)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter) # Center the gauge visually

        self.total_label_bottom = QLabel("") # Will set text in update_data
        self.total_label_bottom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_label_bottom.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY}; font-size: 11px;") # Brighter white
        self.layout.addWidget(self.total_label_bottom)

    def refresh_theme(self):
        """Refreshes the widget's colors based on the current ModernTheme."""
        self.used_label_top.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY}; font-size: 11px;")
        self.total_label_bottom.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY}; font-size: 11px;")
        self.gauge.update()

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
        self.graph_area.setMinimumHeight(100)
        self.graph_area.paintEvent = self.paint_graph
        self.graph_area.setMouseTracking(True)
        self.graph_area.installEventFilter(self)
        self.layout.addWidget(self.graph_area)
        
        self.layout.addStretch()

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

    def set_duration(self, seconds):
        self.maxlen = seconds
        self.read_history = deque(self.read_history, maxlen=self.maxlen)
        self.write_history = deque(self.write_history, maxlen=self.maxlen)
        # Pad if needed
        while len(self.read_history) < self.maxlen:
            self.read_history.appendleft(0)
        while len(self.write_history) < self.maxlen:
            self.write_history.appendleft(0)
        self.graph_area.update()

    def update_data(self, stats):
        read_speed = stats['read']
        write_speed = stats['write']
        
        self.read_history.append(read_speed)
        self.write_history.append(write_speed)

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

        self.graph_area.update()

        # Update tooltip if visible
        if self.tooltip_widget.isVisible():
            rect = self.graph_area.rect()
            x = self.hover_pos.x()
            width = rect.width()
            step_x = width / (self.maxlen - 1)
            index = int(round(x / step_x))
            index = max(0, min(index, len(self.read_history) - 1))
            r_val = self.read_history[index]
            w_val = self.write_history[index]
            self.tooltip_widget.update_info(
                f"Read: {self.format_speed(r_val)}\nWrite: {self.format_speed(w_val)}"
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
                
                self.tooltip_widget.update_info(
                    f"Read: {self.format_speed(r_val)}\nWrite: {self.format_speed(w_val)}"
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
            y = h - (i * (h / 4))
            painter.drawLine(0, int(y), w, int(y))
            # Optional: Draw value text for grid
            val_at_line = max_val * (i / 4)
            painter.drawText(2, int(y) - 2, self.format_speed(val_at_line))

        # Helper to draw line
        def draw_line(data_deque, color_hex):
            if len(data_deque) < 2: return
            
            path = QPainterPath()
            step_x = w / (self.maxlen - 1)
            
            points = list(data_deque)
            
            # Start
            start_y = h - ((points[0] / max_val) * h)
            path.moveTo(0, start_y)
            
            for i, val in enumerate(points):
                x = i * step_x
                y = h - ((val / max_val) * h)
                path.lineTo(x, y)
                
            pen = QPen(QColor(color_hex), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            
            # Draw Dot if hovered
            if self.hover_index != -1 and self.hover_index < len(points):
                val = points[self.hover_index]
                hx = self.hover_index * step_x
                hy = h - ((val / max_val) * h)
                
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
    def __init__(self):
        """
        Initializes the NetworkWidget.
        """
        super().__init__("Network Speed")
        self.up_label = QLabel("Upload: 0 KB/s")
        self.down_label = QLabel("Download: 0 KB/s")
        
        # Style
        font = QFont()
        font.setPointSize(12) # Reduced size
        font.setBold(True)
        self.up_label.setFont(font)
        self.down_label.setFont(font)
        
        self.up_label.setStyleSheet(f"color: {ModernTheme.ACCENT_CYAN}; ")
        self.down_label.setStyleSheet(f"color: {ModernTheme.ACCENT_GREEN}; ")
        
        self.layout.addWidget(self.up_label)
        self.layout.addWidget(self.down_label)
        self.layout.addStretch()

    def refresh_theme(self):
        """Refreshes the widget's colors based on the current ModernTheme."""
        self.up_label.setStyleSheet(f"color: {ModernTheme.ACCENT_CYAN}; ")
        self.down_label.setStyleSheet(f"color: {ModernTheme.ACCENT_GREEN}; ")

    def update_data(self, stats):
        """
        Updates the displayed upload and download speeds.

        Args:
            stats (dict): A dictionary containing network statistics,
                          e.g., 'upload' and 'download' in bytes per second.
        """
        def format_speed(bytes_sec):
            if bytes_sec > 1024**2:
                return f"{bytes_sec / (1024**2):.1f} MB/s"
            else:
                return f"{bytes_sec / 1024:.1f} KB/s"
        
        self.up_label.setText(f"Upload: {format_speed(stats['upload'])}")
        self.down_label.setText(f"Download: {format_speed(stats['download'])}")

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
            """
            QTableWidget {{
                background-color: {background_color};
                alternate-background-color: {alternate_color};
                gridline-color: {gridline_color};
                border: none;
            }}
            QHeaderView::section {{
                background-color: {background_color};
                color: {text_primary};
                padding: 5px;
                border: none;
                border-bottom: 1px solid {border_color};
                /* Custom paintSection handles the vertical separator */
            }}
            QTableWidget::item {{
                padding: 5px;
            }}
            QTableWidget::item:selected {{
                background-color: {accent_blue};
                color: white;
            }}
            """.format(
                background_color=ModernTheme.WIDGET_BACKGROUND,
                alternate_color=ModernTheme.ALTERNATE_TABLE_BG,
                gridline_color=ModernTheme.BORDER_COLOR,
                text_primary=ModernTheme.TEXT_PRIMARY,
                border_color=ModernTheme.BORDER_COLOR,
                accent_blue=ModernTheme.ACCENT_BLUE
            )
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
            """
            QDialog {{ background-color: "{app_background}"; color: "{text_primary}"; }}
            QCheckBox {{ color: "{text_primary}"; padding: 5px; }}
            QPushButton {{ background-color: "{widget_background}"; color: "{text_primary}"; border: 1px solid "{border_color}"; padding: 5px 15px; }}
            """.format(
                app_background=ModernTheme.APP_BACKGROUND,
                text_primary=ModernTheme.TEXT_PRIMARY,
                widget_background=ModernTheme.WIDGET_BACKGROUND,
                border_color=ModernTheme.BORDER_COLOR,
            )
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
            maintain_selection (bool): Whether to preserve selection of specific items. Defaults to True.
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

        Args:
            pid (int): The PID of the parent process to terminate.
            name (str): The name of the parent process for display in the confirmation dialog.
        """
        confirm = QMessageBox.question(self, "Confirm End Tree", 
                                     f"Are you sure you want to end the process tree for '{name}' (PID: {pid})?\nThis will terminate the process and all its children.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                import psutil
                parent = psutil.Process(pid)
                children = parent.children(recursive=True)
                for child in children:
                    self._kill_pid(child.pid, silent=True)
                self._kill_pid(pid)
                QMessageBox.information(self, "Success", f"Process tree for '{name}' terminated.")
            except psutil.NoSuchProcess:
                QMessageBox.warning(self, "Error", "Process no longer exists.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to kill tree: {e}")

    def kill_group(self, name):
        """
        Prompts for confirmation and attempts to terminate all processes with a given name.

        Args:
            name (str): The name of the processes to terminate.
        """
        confirm = QMessageBox.question(self, "Confirm End Group", 
                                     f"Are you sure you want to end ALL processes named '{name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            count = 0
            for p in self.process_data:
                if p['name'] == name:
                    self._kill_pid(p['pid'], silent=True)
                    count += 1
            QMessageBox.information(self, "Success", f"Terminated {count} instances of '{name}'.")

    def _kill_pid(self, pid, silent=False):
        """
        Attempts to terminate a process by its PID.

        Args:
            pid (int): The PID of the process to terminate.
            silent (bool): If True, suppresses QMessageBox pop-ups for success/failure.
                           Defaults to False.
        """
        try:
            import psutil
            p = psutil.Process(pid)
            p.terminate()
            if not silent:
                QMessageBox.information(self, "Success", f"Process {pid} terminated.")
        except psutil.NoSuchProcess:
            if not silent: QMessageBox.warning(self, "Error", "Process no longer exists.")
        except psutil.AccessDenied:
            if not silent: QMessageBox.critical(self, "Error", "Access Denied.")
        except Exception as e:
            if not silent: QMessageBox.critical(self, "Error", f"Could not terminate: {e}")

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
        self.gauge_area.setMinimumHeight(140) # Reverted height, text is now outside
        self.gauge_area.paintEvent = self.paint_gauge
        self.layout.addWidget(self.gauge_area)
        
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
        rect = self.gauge_area.rect()
        
        # Calculate size (keep square)
        size = min(w, h) - 20 # Leave some padding for the circle
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
            font.setPointSize(line["size"])
            font.setBold(line["bold"])
            painter.setFont(font)
            painter.setPen(QColor(line["color"]))
            
            fm = painter.fontMetrics()
            t_w = fm.horizontalAdvance(line["text"])
            painter.drawText(int(cx - t_w/2), int(cy + fm.ascent()/2 - 5), line["text"])
            
        elif len(self.text_lines_values) == 2:
            # Stacked detailed values (e.g., Used GiB, Total GiB)
            offsets = [-15, 15] # Offset from center
            
            for i, line in enumerate(self.text_lines_values):
                font = QFont()
                font.setPointSize(line["size"])
                font.setBold(line["bold"])
                painter.setFont(font)
                painter.setPen(QColor(line["color"]))
                
                fm = painter.fontMetrics()
                t_w = fm.horizontalAdvance(line["text"])
                
                # Draw Line Separator between the two values
                if i == 1: # Draw line BEFORE the second value
                    sep_pen = QPen(QColor(ModernTheme.BORDER_COLOR), 1)
                    painter.setPen(sep_pen)
                    painter.drawLine(int(cx - 30), int(cy - 2), int(cx + 30), int(cy - 2))
                    painter.setPen(QColor(line["color"]))

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
        self.history = {}
        
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
        self.layout.addWidget(self.graph_area)
        
        # Legend
        self.legend_layout = QHBoxLayout()
        self.legend_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
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

    def update_data(self, fan_data):
        """
        Updates the fan speed history and triggers a graph repaint.

        Args:
            fan_data (dict): A dictionary where keys are fan sensor names (str)
                             and values are their current RPMs (int).
        """
        # Update History
        for name, value in fan_data.items():
            if name not in self.history:
                self.history[name] = deque([0]*self.maxlen, maxlen=self.maxlen)
            self.history[name].append(value)
            
        # Update Legend
        for i, (name, value) in enumerate(fan_data.items()):
            color = self.colors[i % len(self.colors)]
            color_hex = color.name()
            
            display_text = f"<span style='color: {color_hex}; font-weight: bold;'>|</span> {name}: <span style='color: {ModernTheme.TEXT_PRIMARY}; font-weight: bold;'>{value} RPM</span>"
            
            if name not in self.legend_labels:
                lbl = QLabel(display_text)
                lbl.setTextFormat(Qt.TextFormat.RichText)
                lbl.setStyleSheet("font-size: 12px; margin-right: 15px;")
                self.legend_layout.addWidget(lbl)
                self.legend_labels[name] = lbl
            else:
                self.legend_labels[name].setText(display_text)

        self.graph_area.update()

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
                tooltip_lines = []
                for name, points in self.history.items():
                    if index < len(points):
                        val = points[index]
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
                # Since deques might be different lengths during startup (though unlikely if synced),
                # we'll assume they grow to maxlen.
                # Just clamp to the shortest history for safety or maxlen-1.
                # Actually, safest is to clamp to 0..maxlen-1
                index = max(0, min(index, self.maxlen - 1))
                
                self.hover_index = index
                self.hover_pos = event.pos()

                # Construct Tooltip
                tooltip_lines = []
                for name, points in self.history.items():
                    if index < len(points):
                        val = points[index]
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
        
        # Determine Max RPM for scaling
        max_rpm = 2000 # Default min max
        for points in self.history.values():
            if points:
                m = max(points)
                if m > max_rpm: max_rpm = m
        
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
            y = h - (val / max_rpm * h)
            
            # Grid line
            painter.setPen(grid_pen)
            painter.drawLine(40, int(y), w, int(y)) # Offset x by 40 for text
            
            # Label
            painter.setPen(QColor(ModernTheme.TEXT_SECONDARY))
            painter.drawText(0, int(y) + 4, 35, 10, Qt.AlignmentFlag.AlignRight, f"{int(val)}")

        # Draw Lines
        step_x = (w - 40) / (self.maxlen - 1)
        
        for i, (name, points_deque) in enumerate(self.history.items()):
            if len(points_deque) < 2: continue
            
            points = list(points_deque)
            path = QPainterPath()
            
            # Start
            start_y = h - (points[0] / max_rpm * h)
            path.moveTo(40, start_y)
            
            for j, val in enumerate(points):
                x = 40 + j * step_x
                y = h - (val / max_rpm * h)
                path.lineTo(x, y)
            
            color = self.colors[i % len(self.colors)]
            pen = QPen(color, 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            
            # Draw Dot if hovered
            if self.hover_index != -1 and self.hover_index < len(points):
                val = points[self.hover_index]
                hx = 40 + self.hover_index * step_x
                hy = h - (val / max_rpm * h)
                
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
        
        # CPU Gauge
        self.cpu_gauge = ModernGaugeWidget("CPU", ModernTheme.ACCENT_CYAN)
        self.layout.addWidget(self.cpu_gauge)
        
        # GPU Gauge
        self.gpu_gauge = ModernGaugeWidget("GPU", ModernTheme.ACCENT_BLUE)
        self.layout.addWidget(self.gpu_gauge)
        
        # Fan Graph Widget (Replaces Memory/Swap)
        self.fan_widget = FanGraphWidget()
        self.layout.addWidget(self.fan_widget)
        
        # Set stretch factors to make Fan Graph take up more space (half the width)
        # CPU: 1, GPU: 1, Fan: 2
        self.layout.setStretch(0, 1)
        self.layout.setStretch(1, 1)
        self.layout.setStretch(2, 2)
        
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
