@echo off
setlocal EnableDelayedExpansion

echo ------------------------------------------------
echo Taskwire Windows Nuitka Build (Portable Mode)
echo ------------------------------------------------

:: Change to script directory
cd /d "%~dp0"

:: 1. Bootstrap Python 3.11 (Portable)
echo [1/6] Checking Portable Python Environment...
:: Always run bootstrap to ensure pip/virtualenv are installed
python bootstrap.py
if !errorlevel! neq 0 (
    echo Error: Failed to bootstrap Python 3.11.
    pause
    exit /b 1
)

:: 2. Stop LHM
echo [2/6] Stopping background processes...
if exist "Taskwire\kill_lhm.ps1" (
    powershell -ExecutionPolicy Bypass -File "Taskwire\kill_lhm.ps1"
)

:: 3. Setup Venv using Portable Python
echo [3/6] Setting up virtual environment using Portable Python...
if exist "venv" (
    echo Cleaning old venv...
    rmdir /s /q venv
)

echo Creating venv with python_dist\python.exe...
"python_dist\python.exe" -m virtualenv venv
if !errorlevel! neq 0 (
    echo Error: Failed to create venv.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

:: 4. Install Deps
echo [4/6] Installing dependencies...
pip install --upgrade pip
if exist "Taskwire\requirements.txt" (
    pip install -r "Taskwire\requirements.txt"
) else (
    echo Error: Taskwire/requirements.txt not found!
    pause
    exit /b 1
)
pip install nuitka ordered-set zstandard Pillow

:: 5. Prepare Assets
echo [5/6] Preparing assets...
python convert_icon.py
if !errorlevel! neq 0 (
    echo Error: Icon conversion failed.
    pause
    exit /b 1
)

:: 6. Run Nuitka (With MinGW64)
echo [6/6] Compiling with Nuitka...
:: Point to Taskwire\main.py (local folder)
:: Point to Taskwire\app_icon.png

nuitka ^
    --standalone ^
    --onefile ^
    --enable-plugin=pyqt6 ^
    --windows-console-mode=disable ^
    --windows-uac-admin ^
    --windows-icon-from-ico=app_icon.ico ^
    --include-data-file=Taskwire\app_icon.png=app_icon.png ^
    --output-dir=output ^
    --output-filename=Taskwire_Nuitka.exe ^
    --no-pyi-file ^
    --assume-yes-for-downloads ^
    --mingw64 ^
    Taskwire\main.py

if !errorlevel! neq 0 (
    echo Error: Nuitka build failed.
    pause
    exit /b 1
)

echo.
echo [Build Success]
echo Output: Windows_port_Nuitka\output\Taskwire_Nuitka.exe
echo ------------------------------------------------
pause