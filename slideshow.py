#!/usr/bin/env python3
"""
ScreenSync - Time-synchronised slideshow for dual Raspberry Pi displays.

Each Pi syncs to NTP/system time so both stay in lockstep without any
network communication between them.

Usage:
    python3 slideshow.py --screen left   # on Pi 1
    python3 slideshow.py --screen right  # on Pi 2

Image naming convention in the images/ folder:
    00. Left.png   00. Right.png
    01. Left.png   01. Right.png
    ...up to...
    05. Left.png   05. Right.png

Schedule (repeats every 2 minutes):
    Even minutes (0s-60s):  00 -> 01 -> 02  (20s each)
    Odd  minutes (0s-60s):  03 -> 04 -> 05  (20s each)

Transitions use a crossfade effect.
"""

import argparse
import glob
import os
import sys
import time

import pygame


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
SLIDE_DURATION = 20          # seconds per slide
FADE_DURATION = 1.0          # seconds for crossfade
FPS = 30                     # frame rate during fades
EVEN_MINUTE_SLIDES = [0, 1, 2]
ODD_MINUTE_SLIDES = [3, 4, 5]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_image(index: int, screen: str) -> str:
    """Locate the image file for a given index and screen side."""
    prefix = f"{index:02d}. {screen.capitalize()}"
    pattern = os.path.join(IMAGES_DIR, f"{prefix}.*")
    matches = glob.glob(pattern)
    if not matches:
        print(f"WARNING: no image found for pattern '{pattern}'")
        return None
    return matches[0]


def load_and_scale(path: str, target_size: tuple) -> pygame.Surface:
    """Load an image and scale it to fill the screen."""
    img = pygame.image.load(path).convert()
    return pygame.transform.smoothscale(img, target_size)


def get_current_slide(screen: str, image_cache: dict, screen_size: tuple):
    """
    Determine which slide should be displayed right now based on system time.

    Returns (surface, seconds_into_slide, slide_id).
    """
    now = time.time()
    # Seconds elapsed in the current minute
    sec_in_minute = now % 60
    minute = int(now // 60)
    is_even = (minute % 2 == 0)

    slide_set = EVEN_MINUTE_SLIDES if is_even else ODD_MINUTE_SLIDES

    # Which of the 3 slides are we on? (0-19s → first, 20-39s → second, 40-59s → third)
    slot = min(int(sec_in_minute // SLIDE_DURATION), 2)
    slide_index = slide_set[slot]
    seconds_into = sec_in_minute - (slot * SLIDE_DURATION)

    # Unique id for cache invalidation
    slide_id = (minute, slot)

    # Load / cache
    if slide_index not in image_cache:
        path = find_image(slide_index, screen)
        if path:
            image_cache[slide_index] = load_and_scale(path, screen_size)
        else:
            # Fallback: solid black
            surf = pygame.Surface(screen_size)
            surf.fill((0, 0, 0))
            image_cache[slide_index] = surf

    return image_cache[slide_index], seconds_into, slide_id


def crossfade(screen_surf, old_img, new_img, duration, fps):
    """Render a crossfade from old_img to new_img."""
    clock = pygame.time.Clock()
    steps = max(int(duration * fps), 1)
    for i in range(1, steps + 1):
        alpha = int(255 * i / steps)

        screen_surf.blit(old_img, (0, 0))
        new_img.set_alpha(alpha)
        screen_surf.blit(new_img, (0, 0))
        new_img.set_alpha(255)  # reset

        pygame.display.flip()
        clock.tick(fps)

        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            ):
                return False  # signal to quit
    return True


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ScreenSync slideshow")
    parser.add_argument(
        "--screen",
        choices=["left", "right"],
        required=True,
        help="Which screen this Pi drives (left or right)",
    )
    parser.add_argument(
        "--windowed",
        action="store_true",
        help="Run in a window instead of fullscreen (for testing)",
    )
    args = parser.parse_args()

    # Pygame init
    pygame.init()
    if args.windowed:
        screen_surf = pygame.display.set_mode((800, 480))
    else:
        screen_surf = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption(f"ScreenSync – {args.screen.capitalize()}")
    pygame.mouse.set_visible(False)
    screen_size = screen_surf.get_size()

    image_cache = {}
    clock = pygame.time.Clock()

    # Preload all images for this screen
    for idx in EVEN_MINUTE_SLIDES + ODD_MINUTE_SLIDES:
        path = find_image(idx, args.screen)
        if path:
            image_cache[idx] = load_and_scale(path, screen_size)
            print(f"Loaded: {path}")
        else:
            surf = pygame.Surface(screen_size)
            surf.fill((0, 0, 0))
            image_cache[idx] = surf

    # Show initial slide
    current_surface, _, current_id = get_current_slide(
        args.screen, image_cache, screen_size
    )
    screen_surf.blit(current_surface, (0, 0))
    pygame.display.flip()

    running = True
    while running:
        # Check what slide we should be on now
        new_surface, seconds_into, new_id = get_current_slide(
            args.screen, image_cache, screen_size
        )

        if new_id != current_id:
            # Slide changed — crossfade
            if not crossfade(
                screen_surf, current_surface, new_surface, FADE_DURATION, FPS
            ):
                break
            current_surface = new_surface
            current_id = new_id
        else:
            # Just hold the current slide
            screen_surf.blit(current_surface, (0, 0))
            pygame.display.flip()

        # Event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        # Sleep briefly — no need to spin at full FPS while holding a slide
        clock.tick(10)

    pygame.quit()


if __name__ == "__main__":
    main()
