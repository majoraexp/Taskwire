#!/bin/bash
set -e

echo "=== Step 1: Nuitka standalone build ==="
python3 -m nuitka \
    --standalone \
    --enable-plugin=pyqt6 \
    --include-data-file=app_icon.png=app_icon.png \
    --linux-icon=app_icon.png \
    --output-dir=dist \
    --output-filename=Taskwire \
    main.py

echo "=== Step 2: Injecting libxcb-cursor.so.0 ==="
PLATFORMS_DIR="dist/main.dist/PyQt6/Qt6/plugins/platforms"
cp /usr/lib/x86_64-linux-gnu/libxcb-cursor.so.0 "$PLATFORMS_DIR/"

# Get existing rpath and append $ORIGIN so libqxcb.so finds libxcb-cursor.so.0
# in its own directory. Using --set-rpath because Bullseye patchelf lacks --add-rpath.
EXISTING_RPATH=$(patchelf --print-rpath "$PLATFORMS_DIR/libqxcb.so" 2>/dev/null || echo "")
if [ -n "$EXISTING_RPATH" ]; then
    patchelf --set-rpath "${EXISTING_RPATH}:\$ORIGIN" "$PLATFORMS_DIR/libqxcb.so"
else
    patchelf --set-rpath '$ORIGIN' "$PLATFORMS_DIR/libqxcb.so"
fi
echo "Injected and patched rpath successfully"

echo "=== Step 3: Creating self-extracting onefile binary ==="
# Since Nuitka --onefile rebuilds the dist from scratch (wiping our injected lib),
# we create a self-extracting archive manually. The launcher script extracts the
# dist to a cache dir on first run, then executes from cache on subsequent runs.
# Cache is invalidated when binary size changes (indicates a new version).

cat > dist/Taskwire << 'LAUNCHER'
#!/bin/bash
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/taskwire-standalone"
BINARY_SIZE=$(stat -c%s "$0" 2>/dev/null || stat -f%z "$0")
MARKER="$CACHE_DIR/.version_$BINARY_SIZE"

if [ ! -f "$MARKER" ]; then
    rm -rf "$CACHE_DIR"
    mkdir -p "$CACHE_DIR"
    SKIP=$(awk '/^__ARCHIVE_BELOW__$/{print NR + 1; exit}' "$0")
    tail -n +$SKIP "$0" | tar xzf - -C "$CACHE_DIR"
    touch "$MARKER"
fi

export LD_LIBRARY_PATH="$CACHE_DIR:$CACHE_DIR/PyQt6/Qt6/plugins/platforms:${LD_LIBRARY_PATH:-}"
exec "$CACHE_DIR/Taskwire.bin" "$@"
__ARCHIVE_BELOW__
LAUNCHER

# Rename the actual binary inside dist so it doesn't conflict with our launcher
mv dist/main.dist/Taskwire dist/main.dist/Taskwire.bin

# Append the tarball to the launcher script
cd dist/main.dist && tar czf - . >> ../Taskwire
cd ../..
chmod +x dist/Taskwire

echo "=== Step 4: Creating native Nuitka onefile (ELF binary) ==="
# This produces a smaller true executable but does NOT include libxcb-cursor.so.0,
# so it may crash on distros missing that library (e.g., Linux Mint).
# Uses ccache from step 1 so C compilation is fast.
python3 -m nuitka \
    --onefile \
    --enable-plugin=pyqt6 \
    --include-data-file=app_icon.png=app_icon.png \
    --linux-icon=app_icon.png \
    --output-dir=dist \
    --output-filename=Taskwire-native \
    main.py

echo "=== Build complete ==="
echo "Self-extracting archive (compatible):"
ls -lh dist/Taskwire
echo "Native Nuitka onefile (ELF):"
ls -lh dist/Taskwire-native
