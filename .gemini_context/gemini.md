# Gemini Context & Handover

**Project:** Taskwire
**Current Version:** v1.51
**Last Updated:** December 28, 2025 (Revision 1)

## 1. Project Status
Taskwire is a stable, standalone Linux system monitor built with Python/PyQt6. The application mimics a "Cyberpunk/HUD" aesthetic using custom `QPainter` rendering.

**Update (v1.51):**
*   **UI Refinement:** Optimized "Temperatures" and "Hard Disk Activity" widgets by expanding graph areas and repositioning legends.
*   **UX Improvement:** Fine-tuned default window height for a perfect "pixel-fit" dashboard on launch.

**Recent Major Update (v1.5):**
*   **Version Bump:** Incremented version to v1.5 to reflect cumulative improvements and stable state.
*   **Maintenance:** Continued documentation refinement and architectural verification.

**Major Update (v1.4):**
*   **Feature:** Light Mode Support (Theme Switching).
*   **Fix:** Linux Mint (Light Theme) compatibility fix for white table rows.
*   **Fix:** Process List UI stability (Header reset, Scroll jumping).

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
Or for maximum Linux compatibility (recommended for releases):
```bash
./build_with_docker.sh
```
Artifacts are placed in `dist/Taskwire` (or moved to project root for releases).

## 5. Session Log: Dec 25, 2025
**Objective:** Fix UI bugs on Linux Mint and add Light Mode.

**Actions Taken:**
1.  **Bug Fix: White Rows on Light Themes**
    *   **Issue:** `QTableWidget` inherited system "Alternate Base" color (white) on Linux Mint, breaking the dark theme.
    *   **Fix:** Explicitly set `alternate-background-color` to `#2a2a3a` (later dynamic `ModernTheme.ALTERNATE_TABLE_BG`) in `src/ui.py`.
    *   **Verification:** Built Docker-based compatible binary (Debian 11 base) and verified on Mint VM.

2.  **Feature: Light Mode**
    *   **Implementation:**
        *   Refactored `src/styles.py` to use `LightPalette` and `DarkPalette` classes.
        *   Added `ModernTheme.set_theme(mode)` to switch global class attributes.
        *   Added "Theme" menu in `main.py` -> `switch_theme()`.
        *   Added `refresh_theme()` method to ALL custom widgets in `src/ui.py` to support dynamic re-styling without application restart.

3.  **Bug Fix: Process List Header Reset**
    *   **Issue:** Switching themes caused Process List columns to disappear because `setup_table_style` recreated the `QHeaderView`, wiping out state and signals.
    *   **Fix:** Refactored `ProcessListWidget` to separate header creation from styling (`apply_table_theme`). `refresh_theme` now only updates the stylesheet.

4.  **Bug Fix: Process List Scroll Jump**
    *   **Issue:** Updating the process list caused the view to jump to the selected row due to `selectRow` auto-scrolling.
    *   **Fix:** Modified `render_table` in `src/ui.py` to save `verticalScrollBar().value()` before update and restore it after selection logic.

5.  **Release Management**
    *   **Version:** Bumped to v1.4.
    *   **Build:** Used `./build_with_docker.sh` to create a high-compatibility binary (`Taskwire_v1.4_Linux_x86_64`).
    *   **Distribution:** Pushed code to `main` and updated GitHub Release v1.4 with the new binary and notes.

## 6. Session Log: Dec 27, 2025
**Objective:** Enhance Graph History capabilities and UX.

**Actions Taken:**
1.  **Feature: Extended Graph History**
    *   Added "30 Minutes" option to the "Graph Duration" settings menu.
    *   Implemented logic in `main.py` to handle longer durations by adjusting update intervals (e.g., 10s interval for 30m view) to keep performance high.

2.  **Fix: Data Flushing on Duration Change**
    *   **Issue:** Switching between short (60s) and long (30m) durations caused mixed data points on graphs, resulting in confusing visual artifacts.
    *   **Fix:** Updated `set_duration` methods in `CpuHistoryWidget`, `TempGraphWidget`, and `DiskIOWidget` (`src/ui.py`) to clear existing history buffers (`deque`) immediately upon duration change.

3.  **UX: Graph Setting Indicator**
    *   Added a global `duration_label` at the top of the Dashboard tab to explicitly show the current graph history setting (e.g., "Graph History: 30m").
    *   Ensured this label updates dynamically when settings are changed via the menu.

    *   **Verification:** Validated that all graph widgets (CPU, Temp, Disk IO, Fans) correctly receive and apply the new duration and interval settings.

4.  **UX/UI: Graph Tooltip & Visualization Fixes**
    *   **Feature: Incremental Time Indicators:** Added X-axis labels to all graph widgets (`TempGraphWidget`, `CpuHistoryWidget`, `DiskIOWidget`, `FanGraphWidget`) showing time offset (e.g., "-30s", "-1m").
    *   **Feature: Hover Highlight:** Implemented a vertical dashed line that follows the cursor on all graphs to pinpoint the exact data point.
    *   **Fix: Tooltip Interaction (CPU):** Resolved an issue where the tooltip blocked mouse events at the bottom of the CPU graph by removing the overlapping `val_label` widget and moving the percentage display to a large `QPainter` overlay text in the bottom-right corner.
    *   **Fix: Tooltip Dynamic Updates:** Updated `update_data` methods in all graph widgets to dynamically refresh the tooltip content (including the new "Time: -Xs" header) while the user is persistently hovering, preventing stale data.
    *   **Fix: Tick Alignment:** Adjusted `maxlen` calculation to `duration + 1` (e.g., 91 points for 90s) to ensuring integer-aligned ticks (e.g., "18s" instead of "17.8s") that match the data points exactly.
    *   **Fix: Floating Point Labels:** Updated `format_time_offset` to round seconds to the nearest integer, fixing off-by-one label mismatches (e.g., "17s" label vs "-18s" tooltip).
    *   **Fix: Empty Data Points (Temp):** Changed `TempGraphWidget` initialization to use `None` instead of `30.0` for empty history. Updated drawing logic to skip `None` values (creating gaps) and tooltip to display "NA", preventing misleading "30.0°C" readings for future points.
    *   **Fix: Graph Drawing (Disk IO):** Fixed a regression where Disk I/O lines disappeared by restoring missing `draw_line` calls and ensuring correct `top_margin` usage.
    *   **Fix: Layout Margins:** Added consistent `top_margin = 10` to all graphs (`Cpu`, `Temp`, `Disk`) to prevent the 100% line from drawing exactly on the top edge pixel, improving hover reliability.

## 7. Session Log: Dec 28, 2025
**Objective:** Formalize Version 1.5 and improve initial UX.

**Actions Taken:**
1.  **Version Bump:** Officially updated project metadata to v1.5 across context documentation.
2.  **UI/UX Improvement:** Increased default window height to 1350 in `main.py` to ensure the entire dashboard (including CPU per-thread grid) is fully visible on launch without scrolling.

## 8. Session Log: Dec 28, 2025 (Revision 1)
**Objective:** UI/UX Polishing and v1.51 Release.

**Actions Taken:**
1.  **UI: Temperature Widget Optimization**
    *   Moved the legend to the bottom of the card.
    *   Set the graph area to expand and fill the middle space, increasing its minimum height to 150.
2.  **UI: Disk IO Widget Optimization**
    *   Applied the same expansion logic to the Hard Disk Activity graph for visual consistency with the Temperature widget.
3.  **UX: Window Sizing**
    *   Iteratively fine-tuned the default window height from 1350 down to 1297 to eliminate all trailing empty space below the dashboard while keeping all elements visible.
4.  **Release Management**
    *   **Version:** Bumped to v1.51.
    *   **Build:** Executed `./build_with_docker.sh` to generate a new compatible release binary.

## 9. Debug & Test Infrastructure
A collection of scripts in `test_scripts/` is available for debugging and verification:
*   **`profile_memory.py`**: Profiling script using `tracemalloc`. Runs the app for 5 seconds and compares memory snapshots to identify leaks or high usage.
*   **`test_reset_logic.py`**: Unit tests for widget history reset logic. Verifies that `set_duration` correctly clears and resizes history buffers (deque) in `CpuHistoryWidget`, `DiskIOWidget`, `TempGraphWidget`, and `FanGraphWidget`.
*   **`test_settings.py`**: Integration tests for `MainWindow` settings. Mocks UI components to verify that changing the "Graph Duration" in the menu correctly updates the application state and propagates changes to widgets.