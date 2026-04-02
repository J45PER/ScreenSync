#!/usr/bin/env bash
# ScreenSync installer for Raspberry Pi OS 32-bit (Pi 3)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CURRENT_USER="$(whoami)"

echo "=== ScreenSync Installer ==="

# Ensure NTP sync is enabled
echo "[1/4] Enabling NTP time sync..."
sudo timedatectl set-ntp true
echo "      Time sync status:"
timedatectl show --property=NTPSynchronized --value

# Install dependencies
echo "[2/4] Installing dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pygame python3-pil python3-pil.imagetk

# Create images directory
mkdir -p "$SCRIPT_DIR/images"

# Create slideshow systemd service
echo "[3/4] Installing slideshow service..."

cat <<EOF | sudo tee /etc/systemd/system/screensync.service > /dev/null
[Unit]
Description=ScreenSync Slideshow
After=network-online.target time-sync.target
Wants=network-online.target time-sync.target

[Service]
Type=simple
User=${CURRENT_USER}
Environment=DISPLAY=:0
WorkingDirectory=${SCRIPT_DIR}
ExecStart=/usr/bin/python3 ${SCRIPT_DIR}/slideshow.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical.target
EOF

sudo systemctl daemon-reload

# Install desktop shortcut
echo "[4/4] Installing desktop shortcut..."

DESKTOP_FILE="${SCRIPT_DIR}/screensync.desktop"
# Update Exec path to match actual install location
sed -i "s|Exec=.*|Exec=python3 ${SCRIPT_DIR}/manager.py|" "$DESKTOP_FILE"

# Copy to desktop and applications menu
DESKTOP_DIR="/home/${CURRENT_USER}/Desktop"
APPS_DIR="/home/${CURRENT_USER}/.local/share/applications"
mkdir -p "$DESKTOP_DIR" "$APPS_DIR"
cp "$DESKTOP_FILE" "$DESKTOP_DIR/screensync.desktop"
cp "$DESKTOP_FILE" "$APPS_DIR/screensync.desktop"
chmod +x "$DESKTOP_DIR/screensync.desktop"

echo ""
echo "=== Done! ==="
echo ""
echo "A 'ScreenSync Manager' icon has been added to your desktop."
echo "Use it to upload images and configure which screen this Pi drives."
echo ""
echo "Or run from terminal:  python3 ${SCRIPT_DIR}/manager.py"
echo "Slideshow logs:        journalctl -u screensync -f"
