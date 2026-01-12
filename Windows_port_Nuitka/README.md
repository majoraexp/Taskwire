# Taskwire Windows Nuitka Build System

This directory contains a standalone, portable build system to compile the Windows Port of Taskwire into a native C++ executable using Nuitka.

## Why this exists
Building Python GUI apps on Windows can be difficult due to:
1.  **Python Version Mismatches:** Nuitka + MinGW often require specific Python versions (e.g., 3.11/3.12) and fail on newer ones (3.13+).
2.  **Antivirus False Positives:** Single-file executables (`.exe`) are often flagged as "Wacatac" trojans by Windows Defender due to their self-extracting nature.

This build system solves both.

## How to Build

### Option A: Folder Build (Recommended)
Creates a folder containing the executable and libraries.
*   **Script:** `build_onedir.bat`
*   **Output:** `output_onedir/Taskwire.dist/`
*   **Pros:** **Avoids Antivirus False Positives**, faster startup.
*   **Cons:** Must distribute the whole folder (zip it up).

### Option B: Single File Build
Creates a single `.exe` file.
*   **Script:** `build.bat`
*   **Output:** `output/Taskwire_Nuitka.exe`
*   **Pros:** Convenient single file.
*   **Cons:** **High risk of Windows Defender detection** (False Positive), slower startup.

## How it Works
1.  **Bootstrap:** `bootstrap.py` automatically downloads a portable **Python 3.11** distribution (Nuget package) from the internet.
2.  **Isolation:** It sets up a local `venv` using that portable Python, ignoring your system installed Python.
3.  **Compilation:** It downloads the **MinGW64** C compiler automatically and compiles the app.

## Requirements
*   Internet connection (for first run to download Python/MinGW).
*   Windows 10/11.
