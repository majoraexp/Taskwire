# pylint: disable=E0611
"""
Gauge widgets: CircularGauge, ModernGaugeWidget.
"""
import math

from PyQt6.QtCore import Qt, QPoint, QRectF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QBrush
)
from PyQt6.QtWidgets import QWidget, QLabel

from .base import GameTooltip, Card
from ..styles import ModernTheme

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
