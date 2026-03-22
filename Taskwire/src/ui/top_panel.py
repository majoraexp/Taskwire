# pylint: disable=E0611
"""
Top panel widget: TopPanelWidget.
"""
from PyQt6.QtWidgets import QWidget, QHBoxLayout

from .gauges import ModernGaugeWidget
from .fans import FanGraphWidget
from ..styles import ModernTheme

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
