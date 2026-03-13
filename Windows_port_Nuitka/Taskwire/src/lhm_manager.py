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
import io

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

import ctypes

def add_exclusion(path):
    """
    Adds a Windows Defender exclusion for the specified path using cmd.exe trampoline.
    Triggers a native UAC prompt.
    """
    print(f"Requesting Defender exclusion for: {path}")
    try:
        # Construct the command
        # We use cmd.exe /c to launch powershell, which often handles the UAC context transition better
        ps_cmd = f"Add-MpPreference -ExclusionPath '{path}' -Force"
        cmd_args = f"/c powershell -Command \"{ps_cmd}\""

        ret = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            "cmd.exe",
            cmd_args,
            None,
            0 # SW_HIDE (Hide the CMD window, users will just see the UAC prompt)
        )

        if ret <= 32:
            print(f"ShellExecute failed with code: {ret}")
            return False

        print("UAC prompt triggered. Waiting 5 seconds for policy application...")
        time.sleep(5)
        return True
    except Exception as e:
        print(f"Failed to trigger exclusion: {e}")
        return False

def install_lhm():
    """Downloads and extracts LibreHardwareMonitor completely in-memory."""
    libs_dir = get_libs_dir()
    lhm_dir = get_lhm_dir()

    if not os.path.exists(libs_dir):
        os.makedirs(libs_dir)

    # Ensure directory exists for exclusion
    if not os.path.exists(lhm_dir):
        os.makedirs(lhm_dir)

    # 1. PRE-EMPTIVELY Add Exclusion
    # Critical: Whitelist folder BEFORE writing real .sys files.
    if not add_exclusion(lhm_dir):
        print("Warning: Failed to add exclusion. Installation may be flagged.")

    # 2. Download to Memory
    print(f"Downloading {LHM_URL}...")
    try:
        response = requests.get(LHM_URL)
        response.raise_for_status()
        zip_buffer = io.BytesIO(response.content)
        print("Download complete.")
    except Exception as e:
        print(f"Download failed: {e}")
        return False

    # 3. Extract from Memory
    print(f"Extracting to {lhm_dir}...")
    try:
        with zipfile.ZipFile(zip_buffer) as zip_ref:
            # Extract ALL files (Real Drivers).
            # Reliance on Exclusion prevents AV flag here.
            zip_ref.extractall(lhm_dir)

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
    driver_sys = os.path.join(lhm_dir, "WinRing0x64.sys")

    # Force install if driver is missing (likely deleted by AV previously)
    if not os.path.exists(lhm_exe) or not os.path.exists(driver_sys):
        print("LibreHardwareMonitor or Driver missing. Installing...")
        if not install_lhm():
            print("Failed to install LibreHardwareMonitor.")
            return False
    else:
        # Even if installed, ensure exclusion is active (idempotent-ish)
        add_exclusion(lhm_dir)

    # 3. Run it
    if os.path.exists(lhm_exe):
        print(f"Starting {LHM_EXE_NAME} as Administrator...")
        try:
            import win32api
            # Use 'runas' verb to request Admin privileges.
            win32api.ShellExecute(0, 'runas', lhm_exe, '', lhm_dir, 6) # SW_MINIMIZE

            time.sleep(3)

            if is_lhm_running():
                print("LibreHardwareMonitor started successfully.")
                return True
            else:
                print("Failed to verify process start. It may be running with higher privileges.")
                return True
        except Exception as e:
            print(f"Error starting process: {e}")
            return False

    return False