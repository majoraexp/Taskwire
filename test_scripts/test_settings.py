import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../Taskwire')))

from PyQt6.QtWidgets import QApplication, QWidget

# Create a dummy QWidget subclass to use as a mock
class MockWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.update_data = MagicMock()
        self.refresh_theme = MagicMock()
        self.set_duration = MagicMock()
        self.update_cpu = MagicMock()
        self.update_gpu = MagicMock()
        self.update_fans = MagicMock()
        self.title_label = MagicMock()
        self.title_label.setText = MagicMock()
        
class MockSystemWorker(MagicMock):
    pass

# Patch with the class itself, so when instantiated it returns a real QWidget
with patch('src.ui.CpuHistoryWidget', MockWidget), \
     patch('src.ui.ProcessListWidget', MockWidget), \
     patch('src.ui.MemoryWidget', MockWidget), \
     patch('src.ui.NetworkWidget', MockWidget), \
     patch('src.ui.DiskWidget', MockWidget), \
     patch('src.ui.TempGraphWidget', MockWidget), \
     patch('src.ui.TopPanelWidget', MockWidget), \
     patch('src.ui.DiskIOWidget', MockWidget), \
     patch('src.ui.CpuWidget', MockWidget), \
     patch('src.system_monitor.SystemWorker'):
    from main import MainWindow

class TestSettings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a dummy app if it doesn't exist
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        # We need to ensure that the mocked classes are used during MainWindow initialization.
        # The imports in main.py have already happened. 
        # But 'main.py' imports 'from src.ui import ...'.
        # Since I patched 'src.ui...', I need to make sure MainWindow uses those patches.
        # But wait, main.py imports classes at module level. Patching sys.modules or using patch.dict might be needed,
        # OR just patch where they are used in main.py.
        
        # Let's try patching the classes in 'main' namespace directly since they are imported there.
        pass

    def test_logic(self):
        # We need to re-import or patch inside the test method to affect MainWindow's init if we want to intercept the class instantiation.
        # Since main.py does "from src.ui import CpuWidget", we need to patch "main.CpuWidget".
        
        with patch('main.CpuHistoryWidget', MockWidget), \
             patch('main.ProcessListWidget', MockWidget), \
             patch('main.MemoryWidget', MockWidget), \
             patch('main.NetworkWidget', MockWidget), \
             patch('main.DiskWidget', MockWidget), \
             patch('main.TempGraphWidget', MockWidget), \
             patch('main.TopPanelWidget', MockWidget), \
             patch('main.DiskIOWidget', MockWidget), \
             patch('main.CpuWidget', MockWidget), \
             patch('main.SystemWorker') as MockWorker:
             
            # Setup Mock Worker signals
            mock_worker_instance = MockWorker.return_value
            mock_worker_instance.cpu_update = MagicMock()
            mock_worker_instance.gpu_update = MagicMock()
            mock_worker_instance.fan_update = MagicMock()
            mock_worker_instance.memory_update = MagicMock()
            mock_worker_instance.process_update = MagicMock()
            mock_worker_instance.network_update = MagicMock()
            mock_worker_instance.disk_update = MagicMock()
            mock_worker_instance.temp_update = MagicMock()
            mock_worker_instance.disk_io_update = MagicMock()
            mock_worker_instance.started = MagicMock()
            
            # Init Window
            window = MainWindow()
            
            # --- Test Initial State ---
            self.assertEqual(window.graph_duration, 90, "Initial graph duration should be 90")
            
            # --- Test Default Selection in Dialog ---
            with patch('PyQt6.QtWidgets.QInputDialog.getItem') as mock_getitem:
                # Mock user cancelling
                mock_getitem.return_value = ("90 Seconds", False)
                
                window.change_graph_duration()
                
                args, _ = mock_getitem.call_args
                options = args[3]
                current_index = args[4]
                self.assertEqual(options[current_index], "90 Seconds", "Default selection should match current state (90)")

            # --- Test Updating Duration ---
            with patch('PyQt6.QtWidgets.QInputDialog.getItem') as mock_getitem:
                # Mock user selecting "60 Seconds"
                mock_getitem.return_value = ("60 Seconds", True)
                
                window.change_graph_duration()
                
                self.assertEqual(window.graph_duration, 60, "State should update to 60")
                window.cpu_history.set_duration.assert_called_with(60)
                window.disk_io_widget.set_duration.assert_called_with(60)
                
            # --- Test Updating Back to 90 ---
            with patch('PyQt6.QtWidgets.QInputDialog.getItem') as mock_getitem:
                # Mock user selecting "90 Seconds"
                mock_getitem.return_value = ("90 Seconds", True)
                
                window.change_graph_duration()
                
                args, _ = mock_getitem.call_args
                current_index = args[4]
                # Previous state was 60, so it should default to 60 selection
                self.assertEqual(options[current_index], "60 Seconds", "Dialog should default to previous state (60)")
                
                self.assertEqual(window.graph_duration, 90, "State should update back to 90")
                window.cpu_history.set_duration.assert_called_with(90)

if __name__ == '__main__':
    unittest.main()