# Use Debian 11 (Bullseye) for older glibc (2.31) compatibility
# This ensures the binary runs on Ubuntu 20.04+, Debian 11+, Fedora 32+, etc.
FROM python:3.11-bullseye

# Install build tools and system libraries required for Nuitka and PyQt6
RUN apt-get update && apt-get install -y \
    build-essential \
    patchelf \
    ccache \
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
    fuse \
    libfuse2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the entire project
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install nuitka ordered-set zstandard

# Pin PyQt6 to 6.5.3 to ensure we get a manylinux wheel compatible with glibc 2.31
# Newer versions (6.6+) might require newer glibc or try to build from source
RUN pip install PyQt6==6.5.3
RUN pip install --no-cache-dir -r Taskwire/requirements.txt

# Switch to source directory
WORKDIR /app/Taskwire

# Nuitka Compilation Command
# --standalone: Include all dependencies
# --onefile: Bundle into a single executable
# --enable-plugin=pyqt6: Enable PyQt6 plugin
# --include-data-file: Bundle the icon inside the executable
# --linux-icon: Set the elf file icon
CMD ["python3", "-m", "nuitka", \
     "--standalone", \
     "--onefile", \
     "--enable-plugin=pyqt6", \
     "--include-data-file=app_icon.png=app_icon.png", \
     "--linux-icon=app_icon.png", \
     "--output-dir=dist", \
     "--output-filename=Taskwire_Nuitka", \
     "--no-pyi-file", \
     "main.py"]
