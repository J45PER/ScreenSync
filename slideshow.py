#!/usr/bin/env python3
"""
ScreenSync - Time-synchronised slideshow for Raspberry Pi displays.

Each Pi syncs to NTP/system time so all stay in lockstep without any
network communication between them.

Usage:
    python3 slideshow.py --screen Left
    python3 slideshow.py --screen Right
    python3 slideshow.py                  # reads device_screens from config.json

Reads settings from config.json (created by the web UI).
Falls back to sensible defaults if no config exists.
"""

import argparse
import glob
import json
import os
import time

import pygame


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(BASE_DIR, "images")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    defaults = {
        "screens": ["Left", "Right"],
        "device_screens": [],
        "slide_duration": 20,
        "fade_duration": 1.0,
        "slots": 6,
    }
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        for k, v in defaults.items():
            cfg.setdefault(k, v)
        return cfg
    return defaults


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_image(index: int, screen: str) -> str:
    """Locate the image file for a given index and screen name."""
    prefix = f"{index:02d}. {screen}"
    pattern = os.path.join(IMAGES_DIR, f"{prefix}.*")
    matches = glob.glob(pattern)
    if not matches:
        return None
    return matches[0]


def load_and_scale(path: str, target_size: tuple) -> pygame.Surface:
    img = pygame.image.load(path).convert()
    return pygame.transform.smoothscale(img, target_size)


def build_schedule(total_slots: int, slide_duration: int):
    """
    Split slots into two groups for even/odd minutes.
    Returns (even_slots, odd_slots, slots_per_group).
    """
    half = total_slots // 2
    even = list(range(0, half))
    odd = list(range(half, half * 2))
    return even, odd, half


def get_current_slide_index(even_slots, odd_slots, slide_duration):
    """Return the image index to display right now."""
    now = time.time()
    sec_in_minute = now % 60
    minute = int(now // 60)
    is_even = (minute % 2 == 0)

    slide_set = even_slots if is_even else odd_slots
    slot = min(int(sec_in_minute // slide_duration), len(slide_set) - 1)
    slide_id = (minute, slot)
    return slide_set[slot], slide_id


def crossfade(screen_surf, old_img, new_img, duration, fps=30):
    clock = pygame.time.Clock()
    steps = max(int(duration * fps), 1)
    for i in range(1, steps + 1):
        alpha = int(255 * i / steps)
        screen_surf.blit(old_img, (0, 0))
        new_img.set_alpha(alpha)
        screen_surf.blit(new_img, (0, 0))
        new_img.set_alpha(255)
        pygame.display.flip()
        clock.tick(fps)
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            ):
                return False
    return True


# ---------------------------------------------------------------------------
# Single-screen slideshow on a given pygame surface
# ---------------------------------------------------------------------------

class ScreenPlayer:
    """Manages the slideshow for one screen name on one display surface."""

    def __init__(self, screen_name, surface, even_slots, odd_slots, slide_duration, fade_duration):
        self.screen_name = screen_name
        self.surface = surface
        self.size = surface.get_size()
        self.even_slots = even_slots
        self.odd_slots = odd_slots
        self.slide_duration = slide_duration
        self.fade_duration = fade_duration
        self.cache = {}
        self.current_id = None
        self.current_surface = None

    def preload(self):
        for idx in self.even_slots + self.odd_slots:
            path = find_image(idx, self.screen_name)
            if path:
                self.cache[idx] = load_and_scale(path, self.size)
                print(f"  [{self.screen_name}] Loaded: {os.path.basename(path)}")
            else:
                surf = pygame.Surface(self.size)
                surf.fill((0, 0, 0))
                self.cache[idx] = surf

    def get_surface(self, idx):
        if idx not in self.cache:
            path = find_image(idx, self.screen_name)
            if path:
                self.cache[idx] = load_and_scale(path, self.size)
            else:
                surf = pygame.Surface(self.size)
                surf.fill((0, 0, 0))
                self.cache[idx] = surf
        return self.cache[idx]

    def update(self):
        """Check time and update display. Returns False if user quit during fade."""
        idx, slide_id = get_current_slide_index(
            self.even_slots, self.odd_slots, self.slide_duration
        )
        new_surface = self.get_surface(idx)

        if self.current_id is None:
            # First frame
            self.surface.blit(new_surface, (0, 0))
            self.current_surface = new_surface
            self.current_id = slide_id
            return True

        if slide_id != self.current_id:
            if not crossfade(self.surface, self.current_surface, new_surface,
                             self.fade_duration):
                return False
            self.current_surface = new_surface
            self.current_id = slide_id
        else:
            self.surface.blit(new_surface, (0, 0))

        return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ScreenSync slideshow")
    parser.add_argument(
        "--screen",
        help="Screen name to display (e.g. Left, Right). "
             "Omit to use device_screens from config.json.",
    )
    parser.add_argument(
        "--windowed",
        action="store_true",
        help="Run in a window instead of fullscreen (for testing)",
    )
    args = parser.parse_args()

    cfg = load_config()
    slide_duration = cfg["slide_duration"]
    fade_duration = cfg["fade_duration"]
    even_slots, odd_slots, _ = build_schedule(cfg["slots"], slide_duration)

    # Determine which screen(s) this device should display
    if args.screen:
        screen_names = [args.screen]
    elif cfg["device_screens"]:
        screen_names = cfg["device_screens"]
    else:
        print("ERROR: No screen specified. Use --screen or set device_screens in the manager app.")
        return

    print(f"ScreenSync starting — screens: {screen_names}")
    print(f"  Schedule: even={even_slots}, odd={odd_slots}, duration={slide_duration}s")

    pygame.init()

    if len(screen_names) == 1:
        # Single screen — simple fullscreen or windowed
        if args.windowed:
            display = pygame.display.set_mode((800, 480))
        else:
            display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.display.set_caption(f"ScreenSync – {screen_names[0]}")
        pygame.mouse.set_visible(False)

        player = ScreenPlayer(screen_names[0], display, even_slots, odd_slots,
                              slide_duration, fade_duration)
        player.preload()

        clock = pygame.time.Clock()
        running = True
        while running:
            if not player.update():
                break
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
            clock.tick(10)

    else:
        # Multi-screen on one device: split the display into equal vertical strips
        if args.windowed:
            total_w, total_h = 800 * len(screen_names), 480
            display = pygame.display.set_mode((total_w, total_h))
        else:
            display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            total_w, total_h = display.get_size()
        pygame.display.set_caption("ScreenSync")
        pygame.mouse.set_visible(False)

        strip_w = total_w // len(screen_names)
        players = []
        for i, name in enumerate(screen_names):
            sub = display.subsurface(pygame.Rect(i * strip_w, 0, strip_w, total_h))
            p = ScreenPlayer(name, sub, even_slots, odd_slots,
                             slide_duration, fade_duration)
            p.preload()
            players.append(p)

        clock = pygame.time.Clock()
        running = True
        while running:
            for p in players:
                if not p.update():
                    running = False
                    break
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
            clock.tick(10)

    pygame.quit()


if __name__ == "__main__":
    main()
