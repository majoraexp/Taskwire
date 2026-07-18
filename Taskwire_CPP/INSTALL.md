# Taskwire Installation

## Option 1: AppImage (recommended for most users)

Download `Taskwire-x86_64.AppImage`, then:

```bash
chmod +x Taskwire-x86_64.AppImage
./Taskwire-x86_64.AppImage
```

No dependencies needed. Works on any Linux distro. ~32 MB.

## Option 2: Native binary (~871 KB)

Download the `taskwire` binary and install Qt6 from your package manager:

**Fedora / Nobara / RHEL:**
```bash
sudo dnf install qt6-qtbase qt6-qtbase-gui
```

**Ubuntu / Debian / Linux Mint:**
```bash
sudo apt install qt6-base-dev libqt6widgets6
```

**Arch / Manjaro:**
```bash
sudo pacman -S qt6-base
```

**openSUSE:**
```bash
sudo zypper install qt6-base
```

Then run:
```bash
chmod +x taskwire
./taskwire
```

To install system-wide:
```bash
sudo cp taskwire /usr/local/bin/
```

## Option 3: Build from source

Requires CMake 3.16+, a C++17 compiler, and Qt6 development headers.

**Install build dependencies:**

Fedora / Nobara:
```bash
sudo dnf install cmake gcc-c++ qt6-qtbase-devel
```

Ubuntu / Debian:
```bash
sudo apt install cmake g++ qt6-base-dev
```

Arch / Manjaro:
```bash
sudo pacman -S cmake qt6-base
```

**Build:**
```bash
git clone https://github.com/majoraexp/Taskwire.git
cd Taskwire/Taskwire_CPP
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
cmake --build . -j$(nproc)
```

**Run:**
```bash
./taskwire
```

**Install system-wide (optional):**
```bash
sudo cmake --install . --prefix /usr/local
```

This installs the binary to `/usr/local/bin/taskwire`, the desktop entry to `/usr/local/share/applications/`, and the icon to `/usr/local/share/icons/`.
