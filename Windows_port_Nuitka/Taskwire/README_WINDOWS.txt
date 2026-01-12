Taskwire Windows Port - Setup Instructions
==========================================

1. Installation (The Easy Way)
   ---------------------------
   Run "Taskwire_Installer.exe" (if available) or double-click "setup.bat".
   This will open a GUI wizard that handles everything for you.

   * Note: If you want to create the standalone "Taskwire_Installer.exe" yourself,
     run "build_installer.bat".

2. Manual Installation
   -------------------
   a) Install Python 3.10+ (Add to PATH).
   b) Open terminal in this folder.
   c) pip install -r requirements.txt
   d) python main.py

3. Sensor Support & Windows Defender (IMPORTANT)
   ---------------------------------------------
   Taskwire uses "LibreHardwareMonitor" to read fans and temperatures.
   
   **ISSUE:** Windows Defender may block "LibreHardwareMonitor.sys".
   **SOLUTION:** Allow the driver in "Virus & threat protection" -> "Protection history".

4. Troubleshooting
   ---------------
   - "NA" on graphs? -> Check if LibreHardwareMonitor is running.
   - Build failed? -> Run "kill_lhm.ps1" manually or reboot to clear file locks.

Enjoy!

5. Updates (Jan 7, 2026 - Fixes)
   -----------------------------
   - **UI Logic:** Temp/Fan legends are now vertically stacked with separate labels for cleaner rendering.
   - **Installer:** Launch logic updated (cwd fix) to prevent visual artifacts on startup.
