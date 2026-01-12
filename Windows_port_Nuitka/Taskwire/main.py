"""
Application entry point and main window setup for the Modern Linux Task Manager.

This module initializes the QApplication, sets up the MainWindow, manages the UI layout,
and connects the system monitoring backend to the frontend widgets.
"""
# pylint: disable=E0611, R0902, C0103
import sys
import os
import threading
from PyQt6.QtCore import QThread, QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QTabWidget,
    QScrollArea, QInputDialog, QGridLayout, QHBoxLayout, QLabel
)
from PyQt6.QtGui import QIcon # Import QIcon

from src.styles import ModernTheme
from src.ui import (
    CpuWidget, MemoryWidget, ProcessListWidget, NetworkWidget,
    DiskWidget, CpuHistoryWidget, TempGraphWidget, TopPanelWidget,
    DiskIOWidget
)
from src.system_monitor import SystemWorker
from src import lhm_manager

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev, PyInstaller and Nuitka """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Nuitka (OneFile or Standalone) or Dev
        # In Nuitka OneFile, assets are extracted to the temp dir with the script
        base_path = os.path.dirname(os.path.abspath(__file__))

    path = os.path.join(base_path, relative_path)
    
    # Fallback: If not found, check next to the executable (Side-car asset for Standalone)
    if not os.path.exists(path):
        base_path_exe = os.path.dirname(sys.executable)
        path_exe = os.path.join(base_path_exe, relative_path)
        if os.path.exists(path_exe):
            return path_exe
            
    # print(f"DEBUG: Resource Path Request: {relative_path} -> {path}")
    return path

class MainWindow(QMainWindow):
    # pylint: disable=E0611, R0902, C0103
    """
    Main application window for the Modern Linux Task Manager.

    This window sets up the tabbed interface for Dashboard and Processes,
    initializes system monitoring, and manages dynamic layout changes.
    """
    def __init__(self):
        super().__init__()
        print("DEBUG: MainWindow.__init__ started")
        self.setWindowTitle("Taskwire")
        self.resize(1280, 1297)
        
        # Load icon using resource_path
        icon_path = resource_path("app_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.dashboard_columns = 2 # Default view
        self.graph_duration = 90 # Default history duration

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
        
        # Global Duration Label
        self.duration_label = QLabel("Graph History: 90s")
        self.duration_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.duration_label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY}; font-weight: bold; font-size: 12px; margin-bottom: 5px;")

        print("DEBUG: Creating dashboard widgets...")
        self.create_dashboard_widgets()
        
        # Initialize graph duration titles and settings (Default 90s, 1s interval)
        # Note: self.graph_duration is 90 (seconds) by default.
        default_interval = 1
        # Use +1 for maxlen so the range is exactly 0..duration inclusive
        self.cpu_history.set_duration(self.graph_duration + 1, default_interval)
        self.disk_io_widget.set_duration(self.graph_duration + 1, default_interval)
        self.temp_widget.set_duration(self.graph_duration + 1, default_interval)
        self.top_panel.fan_widget.set_duration(self.graph_duration + 1, default_interval)

        self.update_dashboard_layout()

        # Check & Start LibreHardwareMonitor (Dependency for sensors)
        threading.Thread(target=lhm_manager.ensure_lhm_running, daemon=True).start()

        # Start System Monitor
        print("DEBUG: Starting SystemWorker...")
        self.worker = SystemWorker()
        
        # Connect Signals
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
        
        # Start the worker thread (Python threading)
        # Nuitka compatibility: Use standard threading instead of QThread to avoid blocking main loop
        self.worker_thread = threading.Thread(target=self.worker.start_monitoring, daemon=True)
        self.worker_thread.start()
        
        print("DEBUG: MainWindow.__init__ completed")

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
        Opens an input dialog to allow the user to change the history graph duration.
        """
        options = ["60 Seconds", "90 Seconds", "30 Minutes"]
        
        # Determine current index based on self.graph_duration (total seconds)
        if self.graph_duration == 60:
            current_index = 0
        elif self.graph_duration == 90:
            current_index = 1
        elif self.graph_duration >= 1800:
            current_index = 2
        else:
            current_index = 1 # Default 90s

        item, ok = QInputDialog.getItem(self, "Graph Settings", 
                                        "Select History Duration:", options, current_index, False)
        if ok and item:
            if "Minute" in item:
                # 30 Minutes
                total_seconds = 30 * 60
                interval = 10
                maxlen = total_seconds // interval
                time_str = "30m"
            else:
                # Seconds
                total_seconds = int(item.split()[0])
                interval = 1
                maxlen = total_seconds
                time_str = f"{total_seconds}s"
            
            self.graph_duration = total_seconds
            
            # Update Global Label
            self.duration_label.setText(f"Graph History: {time_str}")
            
            # Apply to all graph widgets
            # Use +1 for maxlen so the range is exactly 0..duration inclusive
            new_maxlen = (total_seconds // interval) + 1
            self.cpu_history.set_duration(new_maxlen, interval)
            self.disk_io_widget.set_duration(new_maxlen, interval)
            self.temp_widget.set_duration(new_maxlen, interval)
            self.top_panel.fan_widget.set_duration(new_maxlen, interval)

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
        
        # Row 0: Duration Label
        self.dashboard_layout.addWidget(self.duration_label, 0, 0, 1, width_span)
        
        # Row 1: Top Panel (Always Full Width)
        self.dashboard_layout.addWidget(self.top_panel, 1, 0, 1, width_span)
        
        # Row 2: CPU History (Always Full Width)
        self.dashboard_layout.addWidget(self.cpu_history, 2, 0, 1, width_span)

        if self.dashboard_columns == 1:
            # Vertical Stack (Start at Row 3)
            self.dashboard_layout.addWidget(self.mem_widget, 3, 0)
            self.dashboard_layout.addWidget(self.temp_widget, 4, 0)
            self.dashboard_layout.addWidget(self.disk_io_widget, 5, 0)
            self.dashboard_layout.addWidget(self.net_widget, 6, 0)
            self.dashboard_layout.addWidget(self.disk_widget, 7, 0)
            self.dashboard_layout.addWidget(self.cpu_widget, 8, 0)
        else:
            # 2 Columns Balanced (Start at Row 3)
            # Row 3: Memory | Temp + Disk IO
            self.dashboard_layout.addWidget(self.mem_widget, 3, 0)
            
            # Shared container
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0,0,0,0)
            layout.setSpacing(15)
            # Push everything up
            layout.addWidget(self.temp_widget, 1)
            layout.addWidget(self.disk_io_widget, 1)
            
            self.dashboard_layout.addWidget(container, 3, 1)
            
            # Row 4: Network | Disk
            self.dashboard_layout.addWidget(self.net_widget, 4, 0)
            self.dashboard_layout.addWidget(self.disk_widget, 4, 1)
            
            # Row 5: CPU Cores (Wide)
            self.dashboard_layout.addWidget(self.cpu_widget, 5, 0, 1, 2)
        
        # Adjust row stretch to keep things tight at top?
        # QGridLayout handles it mostly fine. We can add a stretch at the end.
        self.dashboard_layout.setRowStretch(10, 1) # Push everything up

    def closeEvent(self, event):
        """
        Handles the close event for the main window.
        Stops the system worker thread gracefully before the application exits.
        """
        self.worker.stop()
        # We can't join the daemon thread easily, nor do we strictly need to.
        # But if we wanted to wait:
        #    if self.worker_thread.is_alive():
        #       self.worker_thread.join(timeout=1.0)
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Taskwire")
    from src.version import __version__
    app.setApplicationVersion(__version__)
    app.setDesktopFileName("Taskwire")
    
    # Apply Theme
    app.setStyleSheet(ModernTheme.get_stylesheet())
    
    # Set Global App Icon (Important for Taskbar/Window Manager on Linux)
    app_icon_path = resource_path("app_icon.png")
    if os.path.exists(app_icon_path):
        app.setWindowIcon(QIcon(app_icon_path))

    try:
        print(f"DEBUG: Main Thread ID: {int(QThread.currentThreadId())}")
        print("DEBUG: Starting MainWindow initialization...")
        window = MainWindow()
        print("DEBUG: MainWindow initialized. Calling show()...")
        window.show()
        window.raise_()
        window.activateWindow()
        
        print("DEBUG: Application event loop starting...")
        sys.exit(app.exec())
    except Exception as e:
        print(f"DEBUG: Exception caught: {e}")
        import traceback
        with open("crash_log.txt", "w") as f:
            f.write(f"Error: {str(e)}\n")
            f.write(traceback.format_exc())
        sys.exit(1)
