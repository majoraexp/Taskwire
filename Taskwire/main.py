"""
Application entry point and main window setup for the Modern Linux Task Manager.

This module initializes the QApplication, sets up the MainWindow, manages the UI layout,
and connects the system monitoring backend to the frontend widgets.
"""
# pylint: disable=E0611, R0902, C0103
import sys
import os
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
    DiskIOWidget, ToolsWidget
)
from src.system_monitor import SystemWorker

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev, PyInstaller and Nuitka """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Nuitka Standalone or Dev
        if "__compiled__" in globals():
            # In Nuitka standalone, resources are often next to the executable
            base_path = os.path.dirname(sys.executable)
        else:
            # In dev mode, use the directory of the script
            base_path = os.path.dirname(os.path.abspath(__file__))

    path = os.path.join(base_path, relative_path)
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
        self.dashboard_layout = QVBoxLayout(self.dashboard_tab)
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

        # Tools Tab
        self.tools_widget = ToolsWidget()
        self.tabs.addTab(self.tools_widget, "Tools")

        # Initialize Widgets (Created once)
        self.top_panel = TopPanelWidget() # Created here to ensure availability
        self.cpu_history = CpuHistoryWidget()
        
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
        self.net_widget.set_duration(self.graph_duration + 1, default_interval)
        self.top_panel.fan_widget.set_duration(self.graph_duration + 1, default_interval)

        self.update_dashboard_layout()

        # Start System Monitor
        print("DEBUG: Starting SystemWorker...")
        self.worker = SystemWorker()
        
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
        
        self.worker.start()
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
        self.tools_widget.refresh_theme()

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
            self.net_widget.set_duration(new_maxlen, interval)
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
                item.widget().setParent(None)
            elif item.layout():
                # Recursively clear nested layouts if any (though takeAt removes the item)
                # But item.layout() item needs deletion? 
                # In PyQt, taking a layout item doesn't destroy it. 
                # We need to be careful. Ideally we just unparent widgets.
                # Since we are rebuilding from scratch, safe to let Python GC handle old layout objects 
                # IF widgets are reparented.
                while item.layout().count():
                    sub_item = item.layout().takeAt(0)
                    if sub_item.widget():
                        sub_item.widget().setParent(None)
        
        # Row 0: Duration Label
        self.dashboard_layout.addWidget(self.duration_label)
        
        # Row 1: Top Panel
        self.dashboard_layout.addWidget(self.top_panel)
        
        # Row 2: CPU History
        self.dashboard_layout.addWidget(self.cpu_history)

        if self.dashboard_columns == 1:
            # Vertical Stack
            self.dashboard_layout.addWidget(self.mem_widget)
            self.dashboard_layout.addWidget(self.temp_widget)
            self.dashboard_layout.addWidget(self.disk_io_widget)
            self.dashboard_layout.addWidget(self.net_widget)
            self.dashboard_layout.addWidget(self.disk_widget)
            self.dashboard_layout.addWidget(self.cpu_widget)
        else:
            # 2 Columns - Decoupled Rows
            
            # Row 3: Memory (Auto) | Temp + Disk IO (Expanded)
            row3_layout = QHBoxLayout()
            row3_layout.setSpacing(15)
            
            # Memory Widget (Stretch 0)
            row3_layout.addWidget(self.mem_widget, 0)
            
            # Shared container for Temp and DiskIO
            # To fill remaining width, we give this container Stretch 1
            container_row3 = QWidget()
            layout_row3 = QHBoxLayout(container_row3)
            layout_row3.setContentsMargins(0,0,0,0)
            layout_row3.setSpacing(15)
            
            # Inside the container, Temp and DiskIO split 50/50
            layout_row3.addWidget(self.temp_widget, 1)
            layout_row3.addWidget(self.disk_io_widget, 1)
            
            row3_layout.addWidget(container_row3, 1)
            
            self.dashboard_layout.addLayout(row3_layout)
            
            # Row 4: Network | Disk (Independent Widths)
            row4_layout = QHBoxLayout()
            row4_layout.setSpacing(15)
            
            # Currently 50/50 split (1:1 stretch)
            row4_layout.addWidget(self.net_widget, 1)
            row4_layout.addWidget(self.disk_widget, 1)
            
            self.dashboard_layout.addLayout(row4_layout)
            
            # Row 5: CPU Cores
            self.dashboard_layout.addWidget(self.cpu_widget)
        
        # Add stretch to push everything up
        self.dashboard_layout.addStretch()

    def closeEvent(self, event):
        """
        Handles the close event for the main window.
        Stops the system worker thread gracefully before the application exits.
        """
        self.worker.stop()
        self.worker.quit()
        self.worker.wait()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Taskwire")
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