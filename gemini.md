# Gemini Context & Handover

**Project:** Taskwire
**Current Version:** v1.2
**Last Updated:** December 21, 2025

## 1. Project Status
Taskwire is a stable, standalone Linux system monitor built with Python/PyQt6. The application mimics a "Cyberpunk/HUD" aesthetic using custom `QPainter` rendering.

**Recent Major Update (v1.2):**
*   **Fixed:** Process Tab text rendering issues ("garbled" text/lines) by reverting to standard `QTableWidgetItem` text rendering and removing the custom `ProgressDelegate`.
*   **Added:** CPU Frequency monitoring (MHz/GHz) for individual cores.
*   **Refined:** CPU Core widget layout (Left-aligned percentage, larger font).
*   **Docs:** Updated `README.md` and screenshots.

## 2. Architecture Overview
*   **Entry Point:** `main.py`
*   **Backend:** `src/system_monitor.py`
    *   Runs a `SystemWorker` in a separate `QThread`.
    *   Fetches data via `psutil` (and `subprocess` for `nvidia-smi`/`lsblk`).
    *   Emits signals (`cpu_update`, `memory_update`, etc.) to the UI.
*   **Frontend:** `src/ui.py`
    *   Contains custom widgets (`CircularGauge`, `CpuHistoryWidget`, `ProcessListWidget`).
    *   Uses a "Card" based layout system.
*   **Styling:** `src/styles.py` (Centralized `ModernTheme` class).

## 3. Future Work & Ideas
The following tasks are suggested for future iterations:

### Feature Enhancements
*   **GPU Support:** Improve AMD GPU support (currently relies on `psutil.sensors_temperatures` fallback, could add `rocm-smi`).
*   **Settings Menu:**
    *   Allow users to customize the refresh rate (currently ~1s).
    *   Theme toggle (or color accent picker).
*   **Network History:** Add a graph for network history similar to the CPU and Disk I/O graphs.
*   **Process Management:**
    *   Add "Suspend/Resume" process options.
    *   Add "Affinity" control (pinned cores).

### Technical Debt / Cleanup
*   **Refactoring:** `src/ui.py` is getting large. Consider splitting widgets into separate files (e.g., `src/widgets/cpu.py`, `src/widgets/process_list.py`).
*   **Testing:** Add unit tests for `system_monitor.py` (mocking `psutil`).

## 4. Build Instructions
To build the standalone executable:
```bash
./build_app.sh
```
Artifacts are placed in `dist/Taskwire`.
