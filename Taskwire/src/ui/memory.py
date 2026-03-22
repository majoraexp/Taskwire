# pylint: disable=E0611
"""
Memory widgets: MemoryAllocationBar, MemoryWidget.
"""
from PyQt6.QtCore import Qt, QRectF, QPoint
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QPainterPath, QBrush
)
from PyQt6.QtWidgets import (
    QWidget, QLabel, QSizePolicy
)

from .base import GameTooltip, Card
from .gauges import CircularGauge
from ..styles import ModernTheme

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

        # 2x2 legend grid below the bar
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
