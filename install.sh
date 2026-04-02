#!/usr/bin/env bash
# ScreenSync installer for Raspberry Pi OS 32-bit (Pi 3)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== ScreenSync Installer ==="

# Ensure NTP sync is enabled
echo "[1/4] Enabling NTP time sync..."
sudo timedatectl set-ntp true
echo "      Time sync status:"
timedatectl show --property=NTPSynchronized --value

# Install dependencies
echo "[2/4] Installing dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pygame python3-flask

# Create images directory if missing
mkdir -p "$SCRIPT_DIR/images"

# Create slideshow systemd service
echo "[3/4] Installing slideshow service..."

cat <<EOF | sudo tee /etc/systemd/system/screensync.service > /dev/null
[Unit]
Description=ScreenSync Slideshow
After=network-online.target time-sync.target screensync-web.service
Wants=network-online.target time-sync.target

[Service]
Type=simple
User=$(whoami)
Environment=DISPLAY=:0
WorkingDirectory=${SCRIPT_DIR}
ExecStart=/usr/bin/python3 ${SCRIPT_DIR}/slideshow.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical.target
EOF

# Create web UI systemd service
echo "[4/4] Installing web UI service..."

cat <<EOF | sudo tee /etc/systemd/system/screensync-web.service > /dev/null
[Unit]
Description=ScreenSync Web UI
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=${SCRIPT_DIR}
ExecStart=/usr/bin/python3 ${SCRIPT_DIR}/web_ui.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable screensync-web.service

echo ""
echo "=== Done! ==="
echo ""
echo "Web UI:  http://$(hostname -I | awk '{print $1}'):5000"
echo "         Use the web UI to upload images and configure screens."
echo ""
echo "The slideshow service reads config.json (managed by the web UI)."
echo "Start the web UI:    sudo systemctl start screensync-web"
echo "Start the slideshow: sudo systemctl start screensync"
echo "View logs:           journalctl -u screensync -f"
