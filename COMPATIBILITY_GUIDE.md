# Linux Binary Compatibility Guide

## The Issue: GLIBC Mismatch
If you build this application on a bleeding-edge Linux distribution (like Fedora Rawhide, Arch Linux, or Nobara 43+), the resulting binary links against a very recent version of `glibc` (e.g., 2.38, 2.40, 2.42). 

When you try to run this binary on a stable, long-term support (LTS) distribution like Ubuntu 24.04, Debian 12, or Linux Mint, you will encounter an error similar to this:

```
[PYI-224382:ERROR] Failed to load Python shared library...
/lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_ABI_GNU2_TLS' not found
```

This happens because Linux binaries are generally **forward-compatible** (old builds run on new systems) but not **backward-compatible** (new builds do not run on old systems).

## The Solution: Docker-Based Build
To ensure maximum compatibility across the Linux ecosystem, we use a **Dockerized build environment** based on **Debian 11 (Bullseye)**.

- **Debian 11** uses `glibc 2.31`.
- Binaries built against `glibc 2.31` are compatible with:
  - Ubuntu 20.04 LTS and newer
  - Debian 11 and newer
  - Fedora 32 and newer
  - CentOS/RHEL 9 and newer
  - Arch Linux, Manjaro, etc.

## How to Build for Distribution

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) installed and running.

### One-Step Build
We have provided a script that automates the entire process:

```bash
./build_with_docker.sh
```

This script will:
1. Build a Docker image containing Python 3.11 and necessary system libraries.
2. Compile the application using `PyInstaller` inside the container.
3. Output the compatible binary to `Taskwire/dist/Taskwire`.

### Manual Docker Build
If you prefer to run the commands yourself:

1. **Build the image:**
   ```bash
   docker build -t taskwire-builder .
   ```

2. **Run the container to compile:**
   ```bash
   # Mount the local dist folder to capture the output
   docker run --rm -v "$(pwd)/Taskwire/dist:/app/Taskwire/dist" taskwire-builder
   ```

## Why PyQt6 6.5.3?
The `Dockerfile` explicitly pins `PyQt6==6.5.3`. This is because newer versions of PyQt6 (like 6.8+) often provide wheels built for newer `glibc` versions (e.g., `manylinux_2_34`), which would defeat the purpose of building on Debian 11 or fail to install without compiling from source (which is slow and error-prone). 6.5.3 provides a stable, compatible binary wheel for our base image.
