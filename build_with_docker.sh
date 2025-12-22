#!/bin/bash
set -e

echo "------------------------------------------------"
echo "Initializing Docker Build for Maximum Compatibility"
echo "------------------------------------------------"

# Check if docker is available
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not in your PATH."
    echo "Please install Docker to use this compatibility build method."
    exit 1
fi

echo "[1/3] Building the Builder Image..."
docker build -t taskwire-builder .

echo "[2/3] Compiling Binary (inside container)..."
# We mount the local 'Taskwire/dist' directory to the container's output directory
# so the binary appears on your host machine.
mkdir -p Taskwire/dist
docker run --rm -v "$(pwd)/Taskwire/dist:/app/Taskwire/dist" taskwire-builder

echo "------------------------------------------------"
echo "Build Complete!"
echo "The compatible binary is located at: Taskwire/dist/Taskwire"
echo "You can verify its compatibility by running: ldd Taskwire/dist/Taskwire | grep libc.so"
echo "------------------------------------------------"
