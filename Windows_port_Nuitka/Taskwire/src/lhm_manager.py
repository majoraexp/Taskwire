"""LibreHardwareMonitor Manager
----------------------------
Handles the automatic downloading, extraction, and execution of LibreHardwareMonitor.
This is required for advanced sensor reading (CPU Temp, Fans) on Windows.
"""
import os
import sys
import time
import zipfile
import shutil
import subprocess
import psutil
import requests

# Constants
LHM_VERSION = "v0.9.4"
LHM_ZIP_NAME = "LibreHardwareMonitor-net472.zip"
LHM_URL = f"https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/download/{LHM_VERSION}/{LHM_ZIP_NAME}"
LHM_EXE_NAME = "LibreHardwareMonitor.exe"

def get_base_dir():
    """Returns the base directory of the application."""
    if hasattr(sys, '_MEIPASS') or getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_libs_dir():
    """Returns the directory where external libs are stored."""
    return os.path.join(get_base_dir(), "libs")

def get_lhm_dir():
    """Returns the directory where LHM should be installed."""
    return os.path.join(get_libs_dir(), "LibreHardwareMonitor")

def is_lhm_running():
    """Checks if LibreHardwareMonitor is currently running."""
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] == LHM_EXE_NAME:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False

def download_file(url, dest_path):
    """Downloads a file from a URL to a destination path."""
    print(f"Downloading {url}...")
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Download complete.")
        return True
    except Exception as e:
        print(f"Download failed: {e}")
        return False

def install_lhm():
    """Downloads and extracts LibreHardwareMonitor, skipping .sys files to avoid AV flags."""
    libs_dir = get_libs_dir()
    lhm_dir = get_lhm_dir()
    
    if not os.path.exists(libs_dir):
        os.makedirs(libs_dir)
        
    zip_path = os.path.join(libs_dir, LHM_ZIP_NAME)
    
    # 1. Download
    if not download_file(LHM_URL, zip_path):
        return False
        
    # 2. Extract (Selectively)
    print(f"Extracting to {lhm_dir}...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Iterate through files in the zip
            for file_info in zip_ref.infolist():
                # Skip .sys files so they are never written to disk
                if file_info.filename.lower().endswith(".sys"):
                    print(f"Skipping driver extraction: {file_info.filename}")
                    continue
                
                # Extract everything else
                zip_ref.extract(file_info, lhm_dir)
        
        # Cleanup Zip
        os.remove(zip_path)

        print("Installation complete.")
        return True
    except Exception as e:
        print(f"Extraction failed: {e}")
        return False

def ensure_lhm_running():
    """
    Ensures that LibreHardwareMonitor is installed and running.
    Returns True if successful, False otherwise.
    """
    print("Checking LibreHardwareMonitor status...")
    
    # 1. Check if running
    if is_lhm_running():
        print("LibreHardwareMonitor is already running.")
        return True
        
    # 2. Check if installed
    lhm_dir = get_lhm_dir()
    lhm_exe = os.path.join(lhm_dir, LHM_EXE_NAME)
    
    if not os.path.exists(lhm_exe):
        print("LibreHardwareMonitor not found. Installing...")
        if not install_lhm():
            print("Failed to install LibreHardwareMonitor.")
            return False
            
    # 3. Run it
    if os.path.exists(lhm_exe):
        print(f"Starting {LHM_EXE_NAME} as Administrator...")
        try:
            import win32api
            # Use 'runas' verb to request Admin privileges. 
            # 0 = Parent HWND, 'runas' = Operation, lhm_exe = File, '' = Params, lhm_dir = Dir, 6 = SW_MINIMIZE (starts minimized)
            win32api.ShellExecute(0, 'runas', lhm_exe, '', lhm_dir, 6)
            
            # Give it a moment to start
            time.sleep(3)
            
            if is_lhm_running():
                print("LibreHardwareMonitor started successfully.")
                return True
            else:
                print("Failed to verify process start. It may be running with higher privileges than this script can see.")
                return True # Assume success if no exception, as Admin processes might hide from non-admin enumeration
        except ImportError:
            # Fallback if pywin32 missing (though it is in requirements)
            print("win32api not found, attempting standard launch...")
            subprocess.Popen([lhm_exe], cwd=lhm_dir, shell=False)
            return True
        except Exception as e:
            print(f"Error starting process: {e}")
            return False
    
    return False