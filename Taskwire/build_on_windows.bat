@echo off
TITLE Taskwire Builder
setlocal

echo ==========================================
echo      Taskwire - Windows Build
echo ==========================================

:: Check for Python
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python from python.org and try again.
    goto ERROR
)

echo [1/4] Cleaning previous builds...
IF EXIST build rmdir /s /q build
IF EXIST dist rmdir /s /q dist

echo [2/4] Setting up virtual environment...
:: Remove old venv if it exists to prevent path issues
IF EXIST venv rmdir /s /q venv

:: Create new venv
python -m venv venv
IF %ERRORLEVEL% NEQ 0 GOTO ERROR

:: Activate venv
call venv\Scripts\activate
IF %ERRORLEVEL% NEQ 0 GOTO ERROR

echo [3/4] Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
IF %ERRORLEVEL% NEQ 0 GOTO ERROR

echo [4/4] Building Executable...
:: Run PyInstaller using the Spec file
pyinstaller --clean Taskwire.spec
IF %ERRORLEVEL% NEQ 0 GOTO ERROR

echo.
echo ==========================================
echo BUILD SUCCESSFUL!
echo ==========================================
echo.
echo The executable is located in the "dist" folder:
echo    %CD%\dist\Taskwire.exe
echo.
pause
exit /b 0

:ERROR
echo.
echo ==========================================
echo BUILD FAILED!
echo ==========================================
echo The script encountered an error and could not complete.
echo.
pause
exit /b 1