import sys
import os
import time
import tracemalloc
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../Taskwire')))

from main import MainWindow

def run_profile():
    print("Starting memory profiling...")
    tracemalloc.start()
    
    app = QApplication(sys.argv)
    window = MainWindow()
    # Don't show window to avoid rendering overhead/issues in some envs, 
    # but we need the worker to run.
    # SystemWorker starts on window init.
    
    snapshot1 = tracemalloc.take_snapshot()
    
    def on_timeout():
        print("5 seconds elapsed. Taking snapshot...")
        snapshot2 = tracemalloc.take_snapshot()
        
        current, peak = tracemalloc.get_traced_memory()
        print(f"Current memory usage: {current / 10**6:.1f} MB")
        print(f"Peak memory usage:    {peak / 10**6:.1f} MB")
        
        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        print("\nTop 10 memory differences:")
        for stat in top_stats[:10]:
            print(stat)
            
        app.quit()

    # Run for 5 seconds
    QTimer.singleShot(5000, on_timeout)
    
    app.exec()
    tracemalloc.stop()

if __name__ == "__main__":
    run_profile()
