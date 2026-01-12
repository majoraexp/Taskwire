@echo off
setlocal EnableDelayedExpansion

:: Error handling
if not exist "main.py" (
    echo Error: main.py not found. Please run this script from the Windows_port/Taskwire directory.
    pause
    exit /b 1
)

echo [0/4] Stopping background processes...
powershell -ExecutionPolicy Bypass -File kill_lhm.ps1
if %errorlevel% neq 0 (
    echo Error: Failed to stop LibreHardwareMonitor. Please close it manually.
    pause
    exit /b 1
)

echo [1/4] Cleaning previous builds...
if exist build (
    set "trash_build=build_trash_%RANDOM%"
    ren build "!trash_build!" >nul 2>&1
    if exist build (
        echo Error: Could not clean 'build' directory. Files are locked.
        pause
        exit /b 1
    )
    start /b cmd /c "rd /s /q "!trash_build!" >nul 2>&1"
)

if exist dist (
    set "trash_dist=dist_trash_%RANDOM%"
    ren dist "!trash_dist!" >nul 2>&1
    if exist dist (
        echo Error: Could not clean 'dist' directory. 'LibreHardwareMonitor.sys' is likely locked by the Kernel.
        echo Solution: Please REBOOT your computer to release the driver lock, then try again.
        pause
        exit /b 1
    )
    :: Try to delete trash in background, but don't wait/fail if it sticks around
    start /b cmd /c "rd /s /q "!trash_dist!" >nul 2>&1"
)

echo [2/4] Setting up virtual environment...
if exist venv (
    echo venv exists.
) else (
    echo Creating venv...
    python -m venv venv
)

echo [3/4] Installing dependencies...
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo [4/4] Building Executable...
:: --onedir: Create a folder (faster startup than --onefile)
:: --windowed: No console window
:: --icon: Set exe icon
:: --add-data: Include the icon file in the bundle (Windows uses semicolon separator)
:: --uac-admin: Request Admin privileges (Required for some hardware sensors)
pyinstaller --noconfirm --onedir --windowed --uac-admin --name "Taskwire" --icon "app_icon.png" --add-data "app_icon.png;." main.py

echo.
echo ------------------------------------------------
echo Build Complete!
echo The executable is located at: dist\Taskwire\Taskwire.exe
echo ------------------------------------------------
pause
