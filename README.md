# ScreenSync

Time-synchronised multi-screen slideshow for Raspberry Pi. All devices sync to NTP internet time so they stay in perfect lockstep with no direct communication between them.

## Features

- **Desktop manager app** — click the icon to upload images and configure screens
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

All timing settings are adjustable in the manager app.

## Setup

On each Pi:

```bash
cd /home/pi
git clone https://github.com/j45per/screensync.git ScreenSync
cd ScreenSync
git checkout claude/sync-pi-slideshows-uyEN4
chmod +x install.sh
./install.sh
```

The installer:
1. Enables NTP time sync
2. Installs Python 3, Pygame, and Pillow
3. Creates a systemd service for the slideshow
4. Adds a **ScreenSync Manager** icon to your desktop

## Usage

1. Double-click the **ScreenSync Manager** icon on the desktop (or run `python3 manager.py`)
2. Set screen names (e.g. Left, Right) and tick which screen(s) this device drives
3. Upload images into each slot using the file picker
4. Click **Start Slideshow**

Press **Escape** to exit the slideshow.

## Manual testing

```bash
python3 slideshow.py --screen Left --windowed
```

## Troubleshooting

- **Out of sync?** Check NTP: `timedatectl status`
- **Black screen?** Check images: `ls images/`
- **Logs:** `journalctl -u screensync -f`
