"""
Application entry point and main window setup for the Modern Linux Task Manager.

This module initializes the QApplication, sets up the MainWindow, manages the UI layout,
and connects the system monitoring backend to the frontend widgets.
"""
# pylint: disable=E0611, R0902, C0103
import sys
import os
from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QTabWidget,
    QScrollArea, QInputDialog, QGridLayout, QHBoxLayout
)
from PyQt6.QtGui import QIcon # Import QIcon

from src.styles import ModernTheme
from src.ui import (
    CpuWidget, MemoryWidget, ProcessListWidget, NetworkWidget,
    DiskWidget, CpuHistoryWidget, TempGraphWidget, TopPanelWidget,
    DiskIOWidget
)
from src.system_monitor import SystemWorker

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # In dev mode, use the directory of the script
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

class MainWindow(QMainWindow):
    # pylint: disable=E0611, R0902, C0103
    """
    Main application window for the Modern Linux Task Manager.

    This window sets up the tabbed interface for Dashboard and Processes,
    initializes system monitoring, and manages dynamic layout changes.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Taskwire")
        self.resize(1200, 900)
        
        # Load icon using resource_path
        icon_path = resource_path("app_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.dashboard_columns = 2 # Default view

        # Menu Bar
        self.create_menu()

        # Main Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        # Tabs
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

        # Dashboard Tab
        self.dashboard_tab = QWidget()
        self.dashboard_layout = QGridLayout(self.dashboard_tab)
        self.dashboard_layout.setSpacing(15)

        # Scroll Area for Dashboard
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.dashboard_tab)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self.tabs.addTab(scroll, "Dashboard")

        # Processes Tab
        self.process_widget = ProcessListWidget()
        self.tabs.addTab(self.process_widget, "Processes")

        # Initialize Widgets (Created once)
        self.top_panel = TopPanelWidget() # Created here to ensure availability
        self.cpu_history = CpuHistoryWidget()
        self.cpu_history.setMaximumHeight(200)

        self.create_dashboard_widgets()
        self.update_dashboard_layout()

        # Start System Monitor
        self.worker = SystemWorker()
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.start_monitoring)
        self.worker.cpu_update.connect(self.cpu_widget.update_data)
        # Connect History Graph
        self.worker.cpu_update.connect(lambda overall, *_: self.cpu_history.update_data(overall))
        # Connect Top Panel
        self.worker.cpu_update.connect(self.top_panel.update_cpu)
        self.worker.gpu_update.connect(self.top_panel.update_gpu)
        self.worker.fan_update.connect(self.top_panel.update_fans)

        self.worker.memory_update.connect(self.mem_widget.update_data)
        self.worker.process_update.connect(self.process_widget.update_data)
        self.worker.network_update.connect(self.net_widget.update_data)
        self.worker.disk_update.connect(self.disk_widget.update_data)
        self.worker.temp_update.connect(self.temp_widget.update_data)
        self.worker.disk_io_update.connect(self.disk_io_widget.update_data)
        
        self.worker_thread.start()

    def create_menu(self):
        """
        Creates the application's menu bar and populates it with settings options,
        including graph duration and dashboard layout toggles.
        """
        menu_bar = self.menuBar()
        settings_menu = menu_bar.addMenu("Settings")
        
        # Graph Duration
        duration_action = settings_menu.addAction("Graph Duration...")
        duration_action.triggered.connect(self.change_graph_duration)
        
        settings_menu.addSeparator()
        # Layout Options
        layout_menu = settings_menu.addMenu("Dashboard Layout")
        col1_action = layout_menu.addAction("1 Column")
        col1_action.triggered.connect(lambda: self.set_layout_columns(1))
        
        col2_action = layout_menu.addAction("2 Columns")
        col2_action.triggered.connect(lambda: self.set_layout_columns(2))
        
        settings_menu.addSeparator()
        
        # Theme Options
        theme_menu = settings_menu.addMenu("Theme")
        self.dark_action = theme_menu.addAction("Dark Mode")
        self.dark_action.setCheckable(True)
        self.dark_action.setChecked(True)
        self.dark_action.triggered.connect(lambda: self.switch_theme("dark"))
        
        self.light_action = theme_menu.addAction("Light Mode")
        self.light_action.setCheckable(True)
        self.light_action.setChecked(False)
        self.light_action.triggered.connect(lambda: self.switch_theme("light"))

    def switch_theme(self, mode):
        """
        Switches the application theme and refreshes all widgets.
        """
        if mode == "dark":
            self.dark_action.setChecked(True)
            self.light_action.setChecked(False)
        else:
            self.dark_action.setChecked(False)
            self.light_action.setChecked(True)
            
        # Apply Theme
        ModernTheme.set_theme(mode)
        
        # Update App Stylesheet
        QApplication.instance().setStyleSheet(ModernTheme.get_stylesheet())
        
        # Refresh Widgets
        self.cpu_history.refresh_theme()
        self.cpu_widget.refresh_theme()
        self.mem_widget.refresh_theme()
        self.net_widget.refresh_theme()
        self.disk_widget.refresh_theme()
        self.temp_widget.refresh_theme()
        self.disk_io_widget.refresh_theme()
        self.top_panel.refresh_theme()
        self.process_widget.refresh_theme()

    def change_graph_duration(self):
        """
        Opens an input dialog to allow the user to change the CPU history graph duration.
        """
        options = ["60 Seconds", "90 Seconds"]
        item, ok = QInputDialog.getItem(self, "Graph Settings", 
                                        "Select History Duration:", options, 0, False)
        if ok and item:
            seconds = int(item.split()[0])
            self.cpu_history.set_duration(seconds)
            self.disk_io_widget.set_duration(seconds)

    def set_layout_columns(self, cols):
        """
        Sets the number of columns for the dashboard layout and updates the layout.

        Args:
            cols (int): The desired number of columns (1 or 2).
        """
        self.dashboard_columns = cols
        self.update_dashboard_layout()

    def create_dashboard_widgets(self):
        """
        Initializes all the dashboard widgets (memory, network, disk, temperature, and CPU cores).
        These widgets are created once and then reused when the layout changes.
        """
        self.mem_widget = MemoryWidget()
        self.net_widget = NetworkWidget()
        self.disk_widget = DiskWidget()
        self.temp_widget = TempGraphWidget()
        self.cpu_widget = CpuWidget()
        self.disk_io_widget = DiskIOWidget()

    def update_dashboard_layout(self):
        """
        Clears the current dashboard layout and repopulates it based on the
        `self.dashboard_columns` setting (1-column or 2-column).
        Widgets are removed from the layout but not destroyed, allowing for reuse.
        """
        # Rescue widgets to avoid deletion when container is removed
        self.temp_widget.setParent(None)
        self.disk_io_widget.setParent(None)

        # Clear existing layout
        while self.dashboard_layout.count():
            item = self.dashboard_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None) # Remove from layout but object persists (refs held by self)
                
        
        # Determine span for wide widgets
        width_span = 1 if self.dashboard_columns == 1 else 2
        
        # Row 0: Top Panel (Always Full Width)
        self.dashboard_layout.addWidget(self.top_panel, 0, 0, 1, width_span)
        
        # Row 1: CPU History (Always Full Width)
        self.dashboard_layout.addWidget(self.cpu_history, 1, 0, 1, width_span)

        if self.dashboard_columns == 1:
            # Vertical Stack (Start at Row 2)
            self.dashboard_layout.addWidget(self.mem_widget, 2, 0)
            self.dashboard_layout.addWidget(self.temp_widget, 3, 0)
            self.dashboard_layout.addWidget(self.disk_io_widget, 4, 0)
            self.dashboard_layout.addWidget(self.net_widget, 5, 0)
            self.dashboard_layout.addWidget(self.disk_widget, 6, 0)
            self.dashboard_layout.addWidget(self.cpu_widget, 7, 0)
        else:
            # 2 Columns Balanced (Start at Row 2)
            # Row 2: Memory | Temp + Disk IO
            self.dashboard_layout.addWidget(self.mem_widget, 2, 0)
            
            # Shared container
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0,0,0,0)
            layout.setSpacing(15)
            # Push everything up
            layout.addWidget(self.temp_widget, 1)
            layout.addWidget(self.disk_io_widget, 1)
            
            self.dashboard_layout.addWidget(container, 2, 1)
            
            # Row 3: Network | Disk
            self.dashboard_layout.addWidget(self.net_widget, 3, 0)
            self.dashboard_layout.addWidget(self.disk_widget, 3, 1)
            
            # Row 4: CPU Cores (Wide)
            self.dashboard_layout.addWidget(self.cpu_widget, 4, 0, 1, 2)
        
        # Adjust row stretch to keep things tight at top?
        # QGridLayout handles it mostly fine. We can add a stretch at the end.
        self.dashboard_layout.setRowStretch(10, 1) # Push everything up

    def closeEvent(self, event):
        """
        Handles the close event for the main window.
        Stops the system worker thread gracefully before the application exits.
        """
        self.worker.stop()
        self.worker_thread.quit()
        self.worker_thread.wait()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Apply Theme
    app.setStyleSheet(ModernTheme.get_stylesheet())
    
    # Set Global App Icon (Important for Taskbar/Window Manager on Linux)
    app_icon_path = resource_path("app_icon.png")
    if os.path.exists(app_icon_path):
        app.setWindowIcon(QIcon(app_icon_path))

    try:
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        import traceback
        with open("crash_log.txt", "w") as f:
            f.write(f"Error: {str(e)}\n")
            f.write(traceback.format_exc())
        sys.exit(1)