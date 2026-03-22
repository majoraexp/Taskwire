# pylint: disable=E0611
"""
Base UI widgets: format_time_offset, GameTooltip, Card, SortableTableWidgetItem, ModernHeader.
"""
import math

from PyQt6.QtCore import Qt, QSize, QPoint
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QBrush
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame,
    QTableWidgetItem, QHeaderView
)

from ..styles import ModernTheme

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
