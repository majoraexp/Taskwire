# Use an older stable base (Debian 11 / Bullseye) to ensure GLIBC compatibility
# GLIBC 2.31 is compatible with Ubuntu 20.04+, Debian 11+, and almost all modern distros.
FROM python:3.11-bullseye

# Install system libraries required by PyQt6 and PyInstaller to bundle correctly
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libegl1 \
    libxkbcommon-x11-0 \
    libdbus-1-3 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-xinerama0 \
    libxcb-xinput0 \
    libxcb-xfixes0 \
    libxcb-shape0 \
    libxcb-cursor0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the entire project context
COPY . .

# Install dependencies
# Upgrade pip first
RUN pip install --upgrade pip
# Install specific stable version of PyQt6 that has wheels for Debian 11
RUN pip install PyQt6==6.5.3
RUN pip install --no-cache-dir -r Taskwire/requirements.txt pyinstaller

# Switch to the inner directory where the spec file is
WORKDIR /app/Taskwire

# Run the build when the container starts
CMD ["pyinstaller", "--clean", "Taskwire.spec"]
