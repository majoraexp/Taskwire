#!/bin/bash

# ==============================================================================
# NOBARA CAPS LOCK KILL SWITCH (NUCLEAR EDITION v3)
# ==============================================================================
# Targets:
# 1. KDE Plasma (Wayland/X11) - Direct Config Injection
# 2. GNOME (Wayland/X11) - GSettings Injection
# 3. System Console (TTY) - Kernel Keymap
# 4. X11 / Xwayland - Xorg Config
# ==============================================================================

if [[ $EUID -ne 0 ]]; then
   echo "CRITICAL: This script must be run as ROOT (sudo)."
   exit 1
fi

ACTION=$1

# Detect Real User (Sudo or Pkexec)
if [ -n "$PKEXEC_UID" ]; then
    REAL_USER=$(getent passwd "$PKEXEC_UID" | cut -d: -f1)
elif [ -n "$SUDO_USER" ]; then
    REAL_USER="$SUDO_USER"
else
    REAL_USER="$USER"
fi

if [ -z "$REAL_USER" ]; then
    echo "Error: Could not detect actual user. Are you running with sudo?"
    exit 1
fi

USER_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

disable_caps() {
    echo "============== INITIATING CAPS LOCK DISABLE =============="

    # --- LAYER 1: SYSTEM CONSOLE (TTY) ---
    echo "[1/4] Patching System Console..."
    localectl set-x11-keymap --no-convert us "" "" "caps:none"
    dumpkeys | sed "s/keycode  58 = Caps_Lock/keycode  58 = VoidSymbol/" | loadkeys 2>/dev/null
    echo "      -> Console map patched."

    # --- LAYER 2: KDE PLASMA (Nobara Default) ---
    echo "[2/4] Targeting KDE Plasma Configs..."
    KXKB_FILE="$USER_HOME/.config/kxkbrc"

    if [ -f "$KXKB_FILE" ]; then
        # Backup
        cp "$KXKB_FILE" "$KXKB_FILE.bak"

        # Check if [Layout] exists, if not create it
        if ! grep -q "\[Layout\]" "$KXKB_FILE"; then
            echo -e "\n[Layout]" >> "$KXKB_FILE"
        fi

        # Check if Options line exists
        if grep -q "Options=" "$KXKB_FILE"; then
            if ! grep -q "caps:none" "$KXKB_FILE"; then
                sed -i "/Options=/ s/$/,caps:none/" "$KXKB_FILE"
                sed -i "s/Options=,/Options=/" "$KXKB_FILE"
            fi
        else
            sed -i "/\[Layout\]/a Options=caps:none" "$KXKB_FILE"
        fi

        chown "$REAL_USER":"$REAL_USER" "$KXKB_FILE"
        echo "      -> Injected 'caps:none' into $KXKB_FILE"
    else
        mkdir -p "$USER_HOME/.config"
        echo -e "[Layout]\nOptions=caps:none\nResetOldOptions=true" > "$KXKB_FILE"
        chown -R "$REAL_USER":"$REAL_USER" "$USER_HOME/.config/kxkbrc"
        echo "      -> Created new KDE keyboard config."
    fi

    # --- LAYER 3: GNOME (If installed) ---
    echo "[3/4] Checking GNOME Settings..."
    if command -v gsettings &> /dev/null; then
        PID=$(pgrep -u "$REAL_USER" gnome-session | head -n 1)
        if [ -n "$PID" ]; then
            DBUS_ADDR=$(grep -z DBUS_SESSION_BUS_ADDRESS /proc/"$PID"/environ | cut -d= -f2-)
            export DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR"
            su -c "gsettings set org.gnome.desktop.input-sources xkb-options \"['caps:none']\"" - "$REAL_USER"
            echo "      -> Applied to GNOME session."
        else
            echo "      -> GNOME session not active, skipping."
        fi
    fi

    # --- LAYER 4: RUNTIME (X11/Xwayland) ---
    echo "[4/4] Patching Runtime (X11/XWayland)..."
    if command -v setxkbmap &> /dev/null; then
        setxkbmap -option caps:none 2>/dev/null
    fi

    echo "=========================================================="
    echo "SUCCESS: Caps Lock has been disabled in all config files."
    echo ""
    echo "!!! SYSTEM REBOOT REQUIRED !!!"
    echo "To ensure all background services and the Wayland compositor"
    echo "pick up the changes, you must REBOOT now."
    echo "=========================================================="
}

enable_caps() {
    echo "============== RESTORING CAPS LOCK =============="

    # 1. Restore Console
    localectl set-x11-keymap --no-convert us "" "" ""
    loadkeys -d 2>/dev/null

    # 2. Restore KDE
    KXKB_FILE="$USER_HOME/.config/kxkbrc"
    if [ -f "$KXKB_FILE" ]; then
        sed -i "s/caps:none//g" "$KXKB_FILE"
        sed -i "s/Options=,/Options=/g" "$KXKB_FILE"
        echo "      -> Removed override from KDE config."
    fi

    # 3. Restore GNOME
    if command -v gsettings &> /dev/null; then
         su -c "gsettings reset org.gnome.desktop.input-sources xkb-options" - "$REAL_USER"
    fi

    # 4. Restore Runtime
    setxkbmap -option 2>/dev/null

    echo "SUCCESS: Caps Lock restored."
    echo "!!! SYSTEM REBOOT REQUIRED !!!"
}

case "$ACTION" in
    disable)
        disable_caps
        ;;
    enable)
        enable_caps
        ;;
    *)
        echo "Usage: sudo $0 [disable|enable]"
        exit 1
        ;;
esac
