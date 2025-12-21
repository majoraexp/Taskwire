#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status

# Error handling function
handle_error() {
    echo ""
    echo "------------------------------------------------"
    echo "Build FAILED!"
    echo "The script encountered an error and could not complete."
    echo "------------------------------------------------"
    exit 1
}

# Trap any error signal (ERR) and run handle_error
trap 'handle_error' ERR

# Ensure we are in the right directory (subdir Taskwire)
cd "$(dirname "$0")/Taskwire"

echo "[1/4] Cleaning previous builds..."
rm -rf build dist

echo "[2/4] Setting up virtual environment..."
# Always recreate venv to ensure no broken paths
if [ -d "venv" ]; then
    rm -rf venv
fi
python3 -m venv venv

echo "[3/4] Installing dependencies..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
./venv/bin/pip install pyinstaller

echo "[4/4] Building Executable..."
# Run PyInstaller using the Spec file
./venv/bin/pyinstaller --clean Taskwire.spec

echo "------------------------------------------------"
echo "Build Complete!"
echo "The executable is located at: Taskwire/dist/Taskwire"
echo "------------------------------------------------"
