# pylint: disable=E0611
"""
Taskwire UI package — re-exports all public widget classes.

This package was split from a single ui.py module for maintainability.
All imports from src.ui continue to work unchanged.
"""
from .base import format_time_offset, GameTooltip, Card, SortableTableWidgetItem, ModernHeader
from .gauges import CircularGauge, ModernGaugeWidget
from .cpu import CpuWidget, CpuHistoryWidget
from .memory import MemoryAllocationBar, MemoryWidget
from .disk import ModernDriveIcon, DiskWidget, DiskIOWidget
from .network import NetworkWidget
from .temperature import TempGraphWidget
from .fans import FanGraphWidget
from .top_panel import TopPanelWidget
from .processes import ProcessListWidget
from .services import ServicesWidget
from .connections import ConnectionsWidget
from .journal import JournalLogWidget
from .tools import ToolsWidget

__all__ = [
    'format_time_offset', 'GameTooltip', 'Card', 'SortableTableWidgetItem', 'ModernHeader',
    'CircularGauge', 'ModernGaugeWidget',
    'CpuWidget', 'CpuHistoryWidget',
    'MemoryAllocationBar', 'MemoryWidget',
    'ModernDriveIcon', 'DiskWidget', 'DiskIOWidget',
    'NetworkWidget',
    'TempGraphWidget',
    'FanGraphWidget',
    'TopPanelWidget',
    'ProcessListWidget',
    'ServicesWidget',
    'ConnectionsWidget',
    'JournalLogWidget',
    'ToolsWidget',
]
