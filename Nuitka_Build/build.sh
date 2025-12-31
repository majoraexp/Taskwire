#!/bin/bash
set -e

# Calculate project root (assuming script is in Nuitka_Build/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "------------------------------------------------"
echo "Initializing Taskwire Nuitka Build (Compatibility Mode)"
echo "------------------------------------------------"

if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed."
    exit 1
fi

echo "[1/3] Building the Nuitka Builder Image..."
# Build from Project Root, pointing to the Dockerfile in Nuitka_Build
docker build -f "$SCRIPT_DIR/Dockerfile" -t taskwire-nuitka-builder "$PROJECT_ROOT"

echo "[2/3] Compiling with Nuitka (This may take a few minutes)..."
# Create output directory inside Nuitka_Build
mkdir -p "$SCRIPT_DIR/output"

# Run the container
# We mount Nuitka_Build/output to capture the build artifacts (executable + C source)
docker run --rm -v "$SCRIPT_DIR/output:/app/Taskwire/dist" taskwire-nuitka-builder

echo "------------------------------------------------"
echo "Build Complete!"
echo "Artifacts location: Nuitka_Build/output/"
echo " - Executable: Taskwire_Nuitka"
echo " - C Source:   main.onefile-build/ (and/or main.build/)"
echo "------------------------------------------------"
