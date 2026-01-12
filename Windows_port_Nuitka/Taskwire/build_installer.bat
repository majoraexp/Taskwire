@echo off
echo ==========================================
echo Building Taskwire Installer Executable...
echo ==========================================

:: 1. Ensure venv exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

:: 2. Install Dependencies
echo Installing dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

:: 3. Build setup.py -> Taskwire_Installer.exe
echo Compiling Setup Wizard...
:: --onefile: Single exe
:: --noconsole: No terminal window
:: --icon: Use the app icon
:: --name: Output name
pyinstaller --noconfirm --onefile --noconsole --name "Taskwire_Installer" --icon "app_icon.png" --add-data "app_icon.png;." setup.py

:: 4. Move to root
echo Moving executable...
move /Y dist\Taskwire_Installer.exe .

:: 5. Cleanup
echo Cleaning up build artifacts...
rd /s /q build
rd /s /q dist
del Taskwire_Installer.spec

echo ==========================================
echo Done! You can now run "Taskwire_Installer.exe"
echo ==========================================
pause
