# ScreenSync

Time-synchronised dual-screen slideshow for two Raspberry Pi 3s. Both Pis sync to NTP internet time so they stay in perfect lockstep with no direct communication between them.

## How it works

| Minute type | Seconds 0-19 | Seconds 20-39 | Seconds 40-59 |
|-------------|-------------|---------------|---------------|
| **Even** (0, 2, 4…) | Image 00 | Image 01 | Image 02 |
| **Odd**  (1, 3, 5…) | Image 03 | Image 04 | Image 05 |

Each image displays for 20 seconds with a 1-second crossfade transition. The cycle repeats every 2 minutes.

## Image naming

Place images in the `images/` folder:

```
images/
  00. Left.png    00. Right.png
  01. Left.png    01. Right.png
  02. Left.png    02. Right.png
  03. Left.png    03. Right.png
  04. Left.png    04. Right.png
  05. Left.png    05. Right.png
```

Any image format supported by Pygame works (PNG, JPG, BMP, etc.). Images are automatically scaled to fill the screen.

## Setup

On each Pi:

```bash
git clone <this-repo> ~/ScreenSync
cd ~/ScreenSync
chmod +x install.sh
./install.sh
```

The installer will:
1. Enable NTP time sync
2. Install Python 3 and Pygame
3. Create a systemd service (asks whether this Pi is `left` or `right`)

## Running

```bash
# As a service (auto-starts on boot)
sudo systemctl start screensync

# Or manually for testing (windowed mode)
python3 slideshow.py --screen left --windowed
```

Press **Escape** to exit.

## Troubleshooting

- **Out of sync?** Check both Pis have NTP working: `timedatectl status`
- **Black screen?** Check images exist: `ls images/`
- **View logs:** `journalctl -u screensync -f`
