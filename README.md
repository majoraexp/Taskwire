# Taskwire

![License](https://img.shields.io/github/license/majoraexp/Taskwire?style=flat-square&color=blueviolet)
![Release](https://img.shields.io/github/v/release/majoraexp/Taskwire?style=flat-square&color=orange)
![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Linux-orange?style=flat-square&logo=linux&logoColor=white)

> **⚠️ Disclaimer:** This is an AI "vibe coded" project, and my first attempt at making something useful with it.

**Taskwire** is a modern, dark-themed system monitor for Linux, designed with a "Video Game HUD" aesthetic. It provides real-time monitoring of your system's performance with a visual style inspired by cyberpunk interfaces and modern desktop widgets.

## 📦 Installation

![Taskwire Dashboard](taskwire_dashboard.png)

**Most Users:** You do **NOT** need to install Python or follow the steps below if you just want to run the app.
👉 **[Download the standalone executable](https://github.com/majoraexp/Taskwire/releases)**, mark it as executable (`chmod +x Taskwire`), and double-click to run.

### Running from Source (Developers)
If you want to modify the code or run it from source, follow these detailed steps.

### Prerequisites
*   **Python 3.8 or newer**: Verify with `python3 --version`.
*   **Linux**: Tested on Fedora/Nobara, Ubuntu, Debian, and Arch.

### Step-by-Step Guide

1.  **Clone the repository:**
    Open your terminal and run:
    ```bash
    git clone https://github.com/majoraexp/Taskwire.git
    cd Taskwire
    ```

2.  **Create a virtual environment (Recommended):**
    This keeps your system packages clean.
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
    *(You will see `(venv)` appear in your terminal prompt indicating it is active.)*

3.  **Install dependencies:**
    This installs `PyQt6` (for the GUI) and `psutil` (for system monitoring).
    ```bash
    pip install -r Taskwire/requirements.txt
    ```

4.  **Run the application:**
    ```bash
    python3 Taskwire/main.py
    ```

## 🛠 Building Executable (Linux)

### Standard Build (For your own machine)
To create a standalone portable executable for your current OS version:

1.  Ensure you have the dev dependencies installed (PyInstaller):
    ```bash
    pip install pyinstaller
    ```

2.  Run the build script:
    ```bash
    ./build_app.sh
    ```

3.  The executable will be located at:
    ```
    Taskwire/dist/Taskwire
    ```

### Building for Distribution (High Compatibility)
**Recommended if sharing the binary.** 
If you build on a new Linux distro (like Nobara, Fedora 40+, Arch), the binary might not work on older systems (Ubuntu 24.04/22.04) due to `glibc` mismatches.

To build a universally compatible binary using Docker:

1.  Run the docker build script:
    ```bash
    ./build_with_docker.sh
    ```

2.  The compatible executable will be created at `Taskwire/dist/Taskwire`.

See [COMPATIBILITY_GUIDE.md](COMPATIBILITY_GUIDE.md) for more details.

## 🎨 Credits
*   **Theme:** Inspired by the [Dracula Theme](https://draculatheme.com/).
*   **Icons:** Procedurally generated via Python/Pillow.

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to this project.

## 📄 License

GNU General Public License v3.0
