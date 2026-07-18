#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build-appimage"
APPDIR="$BUILD_DIR/AppDir"
TOOLS_DIR="$SCRIPT_DIR/appimage-tools"
OUTPUT="$SCRIPT_DIR/Taskwire-x86_64.AppImage"

echo "=== Taskwire AppImage Build ==="

# Check appimagetool
if [ ! -f "$TOOLS_DIR/appimagetool-x86_64.AppImage" ]; then
    echo "Downloading appimagetool..."
    mkdir -p "$TOOLS_DIR"
    wget -q -O "$TOOLS_DIR/appimagetool-x86_64.AppImage" \
        https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$TOOLS_DIR/appimagetool-x86_64.AppImage"
fi

# Clean previous build
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Step 1: Build in Release mode
echo "--- Step 1: CMake Release build ---"
cd "$BUILD_DIR"
cmake -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX=/usr \
      "$SCRIPT_DIR"
cmake --build . -j"$(nproc)"

# Step 2: Create AppDir structure
echo "--- Step 2: Create AppDir ---"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/lib"
mkdir -p "$APPDIR/usr/plugins"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/512x512/apps"

# Install binary
cp "$BUILD_DIR/taskwire" "$APPDIR/usr/bin/"
strip "$APPDIR/usr/bin/taskwire"

# Install desktop file and icon
cp "$SCRIPT_DIR/taskwire.desktop" "$APPDIR/usr/share/applications/"
cp "$SCRIPT_DIR/taskwire.desktop" "$APPDIR/"
cp "$SCRIPT_DIR/app_icon.png" "$APPDIR/usr/share/icons/hicolor/512x512/apps/taskwire.png"
cp "$SCRIPT_DIR/app_icon.png" "$APPDIR/taskwire.png"

# Step 3: Bundle Qt and required shared libraries
echo "--- Step 3: Bundle libraries ---"

# Copy all non-system shared library dependencies
ldd "$APPDIR/usr/bin/taskwire" | while read -r line; do
    lib=$(echo "$line" | awk '{print $3}')
    [ -z "$lib" ] && continue
    [ ! -f "$lib" ] && continue
    name=$(basename "$lib")

    # Skip core system libs that must come from the host
    case "$name" in
        libc.so*|libm.so*|libdl.so*|librt.so*|libpthread.so*|ld-linux*) continue ;;
        libstdc++.so*|libgcc_s.so*) continue ;;
        libGL*.so*|libOpenGL*|libEGL*|libGLdispatch*) continue ;;
        libX11.so*|libxcb.so*|libX11-xcb*) continue ;;
        libdrm.so*|libgbm.so*) continue ;;
    esac

    cp -n "$lib" "$APPDIR/usr/lib/" 2>/dev/null || true
done

# Copy Qt platform plugins
QT_PLUGIN_DIR=$(qmake6 -query QT_INSTALL_PLUGINS 2>/dev/null || qmake -query QT_INSTALL_PLUGINS)
cp -r "$QT_PLUGIN_DIR/platforms" "$APPDIR/usr/plugins/"

# Bundle xcb-related libs that platform plugins need (not caught by binary ldd)
for xcblib in \
    libxcb-cursor.so.0 libxcb-xkb.so.1 libxcb-shape.so.0 libxcb-render-util.so.0 \
    libxcb-render.so.0 libxcb-image.so.0 libxcb-shm.so.0 libxcb-util.so.1; do
    path=$(ldconfig -p | grep "$xcblib" | head -1 | awk '{print $NF}')
    [ -n "$path" ] && [ -f "$path" ] && cp -n "$path" "$APPDIR/usr/lib/" 2>/dev/null || true
done

# Bundle Wayland support (Qt6WaylandClient + libwayland + plugin subdirs)
for waylib in libQt6WaylandClient.so.6 libwayland-client.so.0 libwayland-cursor.so.0; do
    path=$(ldconfig -p | grep "$waylib" | head -1 | awk '{print $NF}')
    [ -n "$path" ] && [ -f "$path" ] && cp -n "$path" "$APPDIR/usr/lib/" 2>/dev/null || true
done

# Copy Wayland plugin subdirectories (shell integration, graphics integration)
for subdir in wayland-decoration-client wayland-graphics-integration-client wayland-shell-integration; do
    if [ -d "$QT_PLUGIN_DIR/$subdir" ]; then
        cp -r "$QT_PLUGIN_DIR/$subdir" "$APPDIR/usr/plugins/"
    fi
done

echo "Bundled $(ls "$APPDIR/usr/lib/" | wc -l) libraries"

# Step 4: Create AppRun wrapper
echo "--- Step 4: Create AppRun ---"
cat > "$APPDIR/AppRun" << 'APPRUN_EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
export LD_LIBRARY_PATH="${HERE}/usr/lib:${LD_LIBRARY_PATH}"
export QT_PLUGIN_PATH="${HERE}/usr/plugins"
export QT_QPA_PLATFORM_PLUGIN_PATH="${HERE}/usr/plugins/platforms"
export XDG_DATA_DIRS="${HERE}/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
exec "${HERE}/usr/bin/taskwire" "$@"
APPRUN_EOF
chmod +x "$APPDIR/AppRun"

# Step 5: Package into AppImage
echo "--- Step 5: Create AppImage ---"
ARCH=x86_64 "$TOOLS_DIR/appimagetool-x86_64.AppImage" "$APPDIR" "$OUTPUT"

echo ""
echo "=== Build complete ==="
echo "AppImage: $OUTPUT"
ls -lh "$OUTPUT"
