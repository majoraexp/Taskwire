import unittest
import sys
import os
from collections import deque
from PyQt6.QtWidgets import QApplication

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../Taskwire')))

from src.ui import CpuHistoryWidget, DiskIOWidget, TempGraphWidget, FanGraphWidget

class TestResetLogic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def test_cpu_history_reset(self):
        print("\n--- Testing CpuHistoryWidget Reset ---")
        widget = CpuHistoryWidget(history_duration=90)
        widget.update_data(50.0)
        print(f"Before reset (Duration 90): Last point = {list(widget.data_points)[-1]}")
        self.assertIn(50.0, widget.data_points)
        
        # Change duration -> Should reset
        print("Changing duration to 60...")
        widget.set_duration(60)
        print(f"After reset (Duration 60): Data length = {len(widget.data_points)}")
        print(f"After reset content (sample): {list(widget.data_points)[:5]} ...")
        
        self.assertEqual(len(widget.data_points), 60) # Should be padded with 0s
        # My implementation pads with 0s: deque([0]*maxlen, ...)
        self.assertEqual(list(widget.data_points), [0]*60)
        
        widget.update_data(25.0)
        print(f"New update (25.0): Last point = {list(widget.data_points)[-1]}")
        self.assertEqual(list(widget.data_points)[-1], 25.0)

    def test_disk_io_reset(self):
        print("\n--- Testing DiskIOWidget Reset ---")
        widget = DiskIOWidget()
        widget.update_data({'read': 100, 'write': 200})
        print(f"Before reset: Read History Last = {list(widget.read_history)[-1]}")
        self.assertIn(100, widget.read_history)
        
        print("Changing duration to 60...")
        widget.set_duration(60)
        print(f"After reset: Read History sample = {list(widget.read_history)[:5]} ...")
        
        self.assertEqual(list(widget.read_history), [0]*60)
        self.assertEqual(list(widget.write_history), [0]*60)

    def test_temp_graph_reset(self):
        print("\n--- Testing TempGraphWidget Reset ---")
        widget = TempGraphWidget()
        widget.update_data({'CPU': 45.0})
        print(f"Before reset: History keys = {list(widget.history.keys())}, CPU val = {list(widget.history['CPU'])[-1]}")
        self.assertIn('CPU', widget.history)
        self.assertIn(45.0, widget.history['CPU'])
        
        print("Changing duration to 60...")
        widget.set_duration(60)
        print(f"After reset: History = {widget.history}")
        # Should clear history dict
        self.assertEqual(widget.history, {})
        
        # Next update fills it
        print("Updating with CPU: 50.0...")
        widget.update_data({'CPU': 50.0})
        print(f"After update: CPU history len = {len(widget.history['CPU'])}, Last = {list(widget.history['CPU'])[-1]}")
        
        self.assertIn('CPU', widget.history)
        # Should be padded with None then 50.0
        points = list(widget.history['CPU'])
        self.assertEqual(len(points), 60) # Maxlen
        self.assertEqual(points[-1], 50.0)
        self.assertIsNone(points[0])

    def test_fan_graph_reset(self):
        print("\n--- Testing FanGraphWidget Reset ---")
        widget = FanGraphWidget()
        widget.update_data({'Fan1': 1000})
        print(f"Before reset: History keys = {list(widget.history.keys())}, Fan1 val = {list(widget.history['Fan1'])[-1]}")
        self.assertIn('Fan1', widget.history)
        
        print("Changing duration to 60...")
        widget.set_duration(60)
        print(f"After reset: History = {widget.history}")
        self.assertEqual(widget.history, {})
        
        print("Updating with Fan1: 1200...")
        widget.update_data({'Fan1': 1200})
        points = list(widget.history['Fan1'])
        print(f"After update: Fan1 history len = {len(points)}, Last = {points[-1]}")
        
        self.assertIn('Fan1', widget.history)
        self.assertEqual(len(points), 60)
        self.assertEqual(points[-1], 1200)
        self.assertEqual(points[0], 0)

if __name__ == '__main__':
    unittest.main()
