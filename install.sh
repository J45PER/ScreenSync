#!/usr/bin/env bash
# ScreenSync installer for Raspberry Pi OS 32-bit (Pi 3)
set -euo pipefail

echo "=== ScreenSync Installer ==="

# Ensure NTP sync is enabled
echo "[1/3] Enabling NTP time sync..."
sudo timedatectl set-ntp true
echo "      Time sync status:"
timedatectl show --property=NTPSynchronized --value

# Install dependencies
echo "[2/3] Installing dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pygame

# Create images directory if missing
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$SCRIPT_DIR/images"

# Create systemd service
echo "[3/3] Installing systemd service..."

# Detect screen side
read -rp "Which screen does this Pi drive? (left/right): " SCREEN_SIDE
SCREEN_SIDE=$(echo "$SCREEN_SIDE" | tr '[:upper:]' '[:lower:]')
if [[ "$SCREEN_SIDE" != "left" && "$SCREEN_SIDE" != "right" ]]; then
    echo "ERROR: must be 'left' or 'right'"
    exit 1
fi

cat <<EOF | sudo tee /etc/systemd/system/screensync.service > /dev/null
[Unit]
Description=ScreenSync Slideshow
After=network-online.target time-sync.target
Wants=network-online.target time-sync.target

[Service]
Type=simple
User=$(whoami)
Environment=DISPLAY=:0
ExecStart=/usr/bin/python3 ${SCRIPT_DIR}/slideshow.py --screen ${SCREEN_SIDE}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable screensync.service

echo ""
echo "=== Done! ==="
echo "Place your images in: $SCRIPT_DIR/images/"
echo "  Naming: 00. Left.png, 00. Right.png, 01. Left.png, etc."
echo ""
echo "Start now with:  sudo systemctl start screensync"
echo "View logs with:  journalctl -u screensync -f"
