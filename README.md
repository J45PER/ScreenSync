# ScreenSync

Time-synchronised multi-screen slideshow for Raspberry Pi. All devices sync to NTP internet time so they stay in perfect lockstep with no direct communication between them.

## Features

- **Web UI** at `http://<pi-ip>:5000` for uploading images and configuring screens
- **Flexible screens** — start with Left/Right, add more screen names as needed
- **Multi-monitor** — one Pi can drive multiple screens (splits the display into strips)
- **Multi-device** — each Pi independently syncs to the same time-based schedule
- **Crossfade transitions** between slides

## Schedule

With the default 6 slots and 20s duration:

| Minute type | 0–19s | 20–39s | 40–59s |
|-------------|-------|--------|--------|
| **Even** (0, 2, 4…) | Image 00 | Image 01 | Image 02 |
| **Odd**  (1, 3, 5…) | Image 03 | Image 04 | Image 05 |

All timing settings are adjustable via the web UI.

## Setup

On each Pi:

```bash
git clone <this-repo> ~/ScreenSync
cd ~/ScreenSync
chmod +x install.sh
./install.sh
```

The installer sets up NTP, installs Python/Pygame/Flask, and creates two systemd services:
- `screensync-web` — the config/upload web UI (port 5000)
- `screensync` — the slideshow player

## Usage

1. Start the web UI: `sudo systemctl start screensync-web`
2. Open `http://<pi-ip>:5000` in a browser
3. Set the screen names (e.g. Left, Right) and tick which screen(s) this device drives
4. Upload images into each slot
5. Start the slideshow from the web UI or run `sudo systemctl start screensync`

Press **Escape** to exit the slideshow.

## Manual testing

```bash
python3 slideshow.py --screen Left --windowed
```

## Troubleshooting

- **Out of sync?** Check NTP: `timedatectl status`
- **Black screen?** Check images: `ls images/`
- **Logs:** `journalctl -u screensync -f` or `journalctl -u screensync-web -f`
