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


def get_current_slide_state(even_slots, odd_slots, slide_duration, fade_duration):
    """
    Determine the current and next slide based on system time.

    The fade happens in the LAST fade_duration seconds of each slot, so
    the new image is fully visible exactly when the next slot begins.

    Returns (current_index, next_index, fade_alpha).
      - fade_alpha = 0   → show current image only (no fade)
      - fade_alpha = 1-255 → blending from current into next
    """
    now = time.time()
    sec_in_minute = now % 60
    minute = int(now // 60)
    is_even = (minute % 2 == 0)

    slide_set = even_slots if is_even else odd_slots
    next_slide_set = odd_slots if is_even else even_slots

    slot = min(int(sec_in_minute // slide_duration), len(slide_set) - 1)
    sec_into_slot = sec_in_minute - (slot * slide_duration)
    fade_start = slide_duration - fade_duration

    current_index = slide_set[slot]
    fade_alpha = 0

    # Work out the next slide index
    if slot + 1 < len(slide_set):
        next_index = slide_set[slot + 1]
    else:
        next_index = next_slide_set[0]

    # Are we in the fade zone (last fade_duration seconds of this slot)?
    if sec_into_slot >= fade_start and fade_duration > 0:
        progress = (sec_into_slot - fade_start) / fade_duration
        fade_alpha = min(int(progress * 255), 255)

    return current_index, next_index, fade_alpha


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
        self.blend_surface = pygame.Surface(self.size)
        self.blend_surface.set_alpha(0)

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
        """Render the correct frame based on current time. Non-blocking."""
        current_idx, next_idx, fade_alpha = get_current_slide_state(
            self.even_slots, self.odd_slots, self.slide_duration, self.fade_duration
        )

        current_surf = self.get_surface(current_idx)
        self.surface.blit(current_surf, (0, 0))

        if fade_alpha > 0:
            next_surf = self.get_surface(next_idx)
            self.blend_surface.blit(next_surf, (0, 0))
            self.blend_surface.set_alpha(fade_alpha)
            self.surface.blit(self.blend_surface, (0, 0))

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
            player.update()
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
            # Higher FPS during fades for smooth blending, lower when static
            _, _, alpha = get_current_slide_state(even_slots, odd_slots,
                                                  slide_duration, fade_duration)
            clock.tick(30 if alpha > 0 else 5)

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
                p.update()
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
            _, _, alpha = get_current_slide_state(even_slots, odd_slots,
                                                  slide_duration, fade_duration)
            clock.tick(30 if alpha > 0 else 5)

    pygame.quit()


if __name__ == "__main__":
    main()
