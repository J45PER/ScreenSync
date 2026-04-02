#!/usr/bin/env python3
"""
ScreenSync Manager — local desktop app for managing slideshow images and settings.

Uses Tkinter (pre-installed on Pi OS). Launch from the desktop icon or run:
    python3 manager.py
"""

import glob
import json
import os
import shutil
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageTk

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(BASE_DIR, "images")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
THUMB_SIZE = (160, 90)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "screens": ["Left", "Right"],
    "device_screens": [],
    "slide_duration": 20,
    "fade_duration": 1.0,
    "slots": 6,
}


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def get_slot_images() -> dict:
    """Return {(slot_index, screen_name): filepath}."""
    result = {}
    os.makedirs(IMAGES_DIR, exist_ok=True)
    for path in glob.glob(os.path.join(IMAGES_DIR, "*")):
        basename = os.path.basename(path)
        if ". " not in basename:
            continue
        try:
            num_str, rest = basename.split(". ", 1)
            slot = int(num_str)
            screen_name = os.path.splitext(rest)[0]
            result[(slot, screen_name)] = path
        except (ValueError, IndexError):
            continue
    return result


def clear_slot_image(slot: int, screen_name: str):
    pattern = os.path.join(IMAGES_DIR, f"{slot:02d}. {screen_name}.*")
    for f in glob.glob(pattern):
        os.remove(f)


def make_thumbnail(path: str) -> Image.Image:
    img = Image.open(path)
    img.thumbnail(THUMB_SIZE, Image.LANCZOS)
    return img


# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------

BG = "#0f1117"
CARD = "#1a1d27"
BORDER = "#2a2d3a"
ACCENT = "#6366f1"
ACCENT_HOVER = "#818cf8"
DANGER = "#ef4444"
SUCCESS = "#22c55e"
TEXT = "#e2e8f0"
TEXT_MUTED = "#94a3b8"
INPUT_BG = "#252836"


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class ScreenSyncApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ScreenSync Manager")
        self.root.configure(bg=BG)
        self.root.minsize(700, 500)

        self.cfg = load_config()
        self.thumb_refs = []  # prevent GC of PhotoImages

        # Styles
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, fieldbackground=INPUT_BG,
                         bordercolor=BORDER, troughcolor=INPUT_BG)
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Card.TLabel", background=CARD, foreground=TEXT)
        style.configure("Muted.TLabel", background=CARD, foreground=TEXT_MUTED, font=("", 8))
        style.configure("Header.TLabel", background=BG, foreground=TEXT, font=("", 14, "bold"))
        style.configure("Section.TLabel", background=CARD, foreground=TEXT, font=("", 11, "bold"))
        style.configure("Accent.TButton", background=ACCENT, foreground="white")
        style.map("Accent.TButton", background=[("active", ACCENT_HOVER)])
        style.configure("Danger.TButton", background=DANGER, foreground="white")
        style.map("Danger.TButton", background=[("active", "#f87171")])
        style.configure("Success.TButton", background=SUCCESS, foreground="white")
        style.map("Success.TButton", background=[("active", "#4ade80")])
        style.configure("TEntry", fieldbackground=INPUT_BG, foreground=TEXT,
                         insertcolor=TEXT)
        style.configure("TCheckbutton", background=CARD, foreground=TEXT)
        style.map("TCheckbutton", background=[("active", CARD)])

        self._build_ui()

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self):
        # Header
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=16, pady=(16, 8))

        title = ttk.Label(header, text="ScreenSync", style="Header.TLabel")
        title.pack(side="left")

        btn_frame = ttk.Frame(header)
        btn_frame.pack(side="right")

        self.status_label = ttk.Label(btn_frame, text="  Checking...  ", style="TLabel",
                                       font=("", 9))
        self.status_label.pack(side="left", padx=(0, 8))

        ttk.Button(btn_frame, text="Start Slideshow", style="Success.TButton",
                   command=self._start_slideshow).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Stop", style="Danger.TButton",
                   command=self._stop_slideshow).pack(side="left", padx=2)

        # Scrollable body
        canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        self.scroll_frame = ttk.Frame(canvas)

        self.scroll_frame.bind("<Configure>",
                               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=16)
        scrollbar.pack(side="right", fill="y")

        # Bind mousewheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-3, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(3, "units"))

        self._build_settings()
        self._build_image_grid()
        self._check_status()

    def _build_settings(self):
        card = ttk.Frame(self.scroll_frame, style="Card.TFrame", padding=16)
        card.pack(fill="x", pady=(0, 12))

        ttk.Label(card, text="Device Settings", style="Section.TLabel").pack(anchor="w")

        row1 = ttk.Frame(card, style="Card.TFrame")
        row1.pack(fill="x", pady=(12, 0))

        # Screen names
        col1 = ttk.Frame(row1, style="Card.TFrame")
        col1.pack(side="left", fill="x", expand=True, padx=(0, 12))
        ttk.Label(col1, text="SCREEN NAMES (comma-separated)", style="Muted.TLabel").pack(anchor="w")
        self.screens_var = tk.StringVar(value=", ".join(self.cfg["screens"]))
        ttk.Entry(col1, textvariable=self.screens_var).pack(fill="x", pady=(4, 0))

        # Slide duration
        col2 = ttk.Frame(row1, style="Card.TFrame")
        col2.pack(side="left", padx=(0, 12))
        ttk.Label(col2, text="SLIDE DURATION (s)", style="Muted.TLabel").pack(anchor="w")
        self.duration_var = tk.StringVar(value=str(self.cfg["slide_duration"]))
        ttk.Entry(col2, textvariable=self.duration_var, width=8).pack(pady=(4, 0))

        # Fade duration
        col3 = ttk.Frame(row1, style="Card.TFrame")
        col3.pack(side="left", padx=(0, 12))
        ttk.Label(col3, text="FADE DURATION (s)", style="Muted.TLabel").pack(anchor="w")
        self.fade_var = tk.StringVar(value=str(self.cfg["fade_duration"]))
        ttk.Entry(col3, textvariable=self.fade_var, width=8).pack(pady=(4, 0))

        # Slots
        col4 = ttk.Frame(row1, style="Card.TFrame")
        col4.pack(side="left")
        ttk.Label(col4, text="SLOTS", style="Muted.TLabel").pack(anchor="w")
        self.slots_var = tk.StringVar(value=str(self.cfg["slots"]))
        ttk.Entry(col4, textvariable=self.slots_var, width=6).pack(pady=(4, 0))

        # Device screens checkboxes
        row2 = ttk.Frame(card, style="Card.TFrame")
        row2.pack(fill="x", pady=(12, 0))
        ttk.Label(row2, text="THIS DEVICE DRIVES", style="Muted.TLabel").pack(anchor="w")

        self.device_screen_frame = ttk.Frame(row2, style="Card.TFrame")
        self.device_screen_frame.pack(anchor="w", pady=(4, 0))
        self.device_screen_vars = {}
        self._rebuild_device_checkboxes()

        # Save button
        ttk.Button(card, text="Save Settings", style="Accent.TButton",
                   command=self._save_settings).pack(anchor="w", pady=(16, 0))

    def _rebuild_device_checkboxes(self):
        for w in self.device_screen_frame.winfo_children():
            w.destroy()
        self.device_screen_vars.clear()
        for name in self.cfg["screens"]:
            var = tk.BooleanVar(value=(name in self.cfg["device_screens"]))
            self.device_screen_vars[name] = var
            ttk.Checkbutton(self.device_screen_frame, text=name, variable=var,
                            style="TCheckbutton").pack(side="left", padx=(0, 16))

    def _build_image_grid(self):
        self.grid_card = ttk.Frame(self.scroll_frame, style="Card.TFrame", padding=16)
        self.grid_card.pack(fill="x", pady=(0, 16))
        self._refresh_grid()

    def _refresh_grid(self):
        for w in self.grid_card.winfo_children():
            w.destroy()
        self.thumb_refs.clear()

        ttk.Label(self.grid_card, text="Image Slots", style="Section.TLabel").pack(anchor="w")

        images = get_slot_images()
        screens = self.cfg["screens"]
        slots = self.cfg["slots"]
        half = slots // 2
        duration = self.cfg["slide_duration"]

        # Header row
        grid = ttk.Frame(self.grid_card, style="Card.TFrame")
        grid.pack(fill="x", pady=(12, 0))

        # Configure columns
        grid.columnconfigure(0, weight=0, minsize=70)
        for i in range(len(screens)):
            grid.columnconfigure(i + 1, weight=1, minsize=180)

        row = 0

        # Column headers
        ttk.Label(grid, text="SLOT", style="Muted.TLabel").grid(
            row=row, column=0, sticky="w", padx=4, pady=4)
        for ci, screen in enumerate(screens):
            ttk.Label(grid, text=screen.upper(), style="Muted.TLabel").grid(
                row=row, column=ci + 1, sticky="w", padx=4, pady=4)
        row += 1

        for slot in range(slots):
            # Group divider
            if slot == 0:
                lbl = ttk.Label(grid, text="--- Even Minutes ---",
                                foreground=ACCENT, background=CARD, font=("", 9, "bold"))
                lbl.grid(row=row, column=0, columnspan=len(screens) + 1,
                         sticky="w", padx=4, pady=(8, 4))
                row += 1
            elif slot == half:
                lbl = ttk.Label(grid, text="--- Odd Minutes ---",
                                foreground=ACCENT, background=CARD, font=("", 9, "bold"))
                lbl.grid(row=row, column=0, columnspan=len(screens) + 1,
                         sticky="w", padx=4, pady=(8, 4))
                row += 1

            # Slot label
            group_slot = slot % half if half > 0 else slot
            time_range = f"{group_slot * duration}s–{(group_slot + 1) * duration}s"
            slot_frame = ttk.Frame(grid, style="Card.TFrame")
            slot_frame.grid(row=row, column=0, sticky="w", padx=4, pady=4)
            ttk.Label(slot_frame, text=f"{slot:02d}", style="Card.TLabel",
                      font=("", 11, "bold")).pack(anchor="w")
            ttk.Label(slot_frame, text=time_range, style="Muted.TLabel").pack(anchor="w")

            # Image cells
            for ci, screen in enumerate(screens):
                cell = ttk.Frame(grid, style="Card.TFrame")
                cell.grid(row=row, column=ci + 1, sticky="w", padx=4, pady=4)

                key = (slot, screen)
                if key in images:
                    path = images[key]
                    try:
                        pil_img = make_thumbnail(path)
                        tk_img = ImageTk.PhotoImage(pil_img)
                        self.thumb_refs.append(tk_img)
                        lbl = tk.Label(cell, image=tk_img, bg=CARD, bd=1, relief="solid")
                        lbl.pack(anchor="w")
                    except Exception:
                        ttk.Label(cell, text="(load error)", style="Muted.TLabel").pack(anchor="w")

                    btn_row = ttk.Frame(cell, style="Card.TFrame")
                    btn_row.pack(anchor="w", pady=(4, 0))
                    ttk.Button(btn_row, text="Replace",
                               command=lambda s=slot, sc=screen: self._upload(s, sc)
                               ).pack(side="left", padx=(0, 4))
                    ttk.Button(btn_row, text="Delete", style="Danger.TButton",
                               command=lambda s=slot, sc=screen: self._delete(s, sc)
                               ).pack(side="left")
                else:
                    ttk.Label(cell, text="No image", style="Muted.TLabel").pack(anchor="w", pady=8)
                    ttk.Button(cell, text="Upload", style="Accent.TButton",
                               command=lambda s=slot, sc=screen: self._upload(s, sc)
                               ).pack(anchor="w")

            row += 1

    # -----------------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------------

    def _save_settings(self):
        # Parse screen names
        raw = self.screens_var.get()
        screens = [s.strip() for s in raw.split(",") if s.strip()]
        if not screens:
            messagebox.showerror("Error", "At least one screen name is required.")
            return

        try:
            duration = int(self.duration_var.get())
        except ValueError:
            messagebox.showerror("Error", "Slide duration must be a whole number.")
            return
        try:
            fade = float(self.fade_var.get())
        except ValueError:
            messagebox.showerror("Error", "Fade duration must be a number.")
            return
        try:
            slots = int(self.slots_var.get())
        except ValueError:
            messagebox.showerror("Error", "Slots must be a whole number.")
            return

        device_screens = [name for name, var in self.device_screen_vars.items() if var.get()]

        self.cfg["screens"] = screens
        self.cfg["device_screens"] = device_screens
        self.cfg["slide_duration"] = duration
        self.cfg["fade_duration"] = fade
        self.cfg["slots"] = slots
        save_config(self.cfg)

        self._rebuild_device_checkboxes()
        self._refresh_grid()
        messagebox.showinfo("Saved", "Settings saved to config.json")

    def _upload(self, slot: int, screen_name: str):
        path = filedialog.askopenfilename(
            title=f"Select image for slot {slot:02d} – {screen_name}",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            messagebox.showerror("Error", f"Unsupported file type: {ext}")
            return

        os.makedirs(IMAGES_DIR, exist_ok=True)
        clear_slot_image(slot, screen_name)
        dest = os.path.join(IMAGES_DIR, f"{slot:02d}. {screen_name}{ext}")
        shutil.copy2(path, dest)
        self._refresh_grid()

    def _delete(self, slot: int, screen_name: str):
        if messagebox.askyesno("Confirm", f"Delete image for slot {slot:02d} – {screen_name}?"):
            clear_slot_image(slot, screen_name)
            self._refresh_grid()

    def _start_slideshow(self):
        try:
            subprocess.run(["sudo", "systemctl", "start", "screensync"], check=True)
            self._check_status()
        except subprocess.CalledProcessError:
            messagebox.showerror("Error", "Failed to start slideshow service.")

    def _stop_slideshow(self):
        try:
            subprocess.run(["sudo", "systemctl", "stop", "screensync"], check=True)
            self._check_status()
        except subprocess.CalledProcessError:
            messagebox.showerror("Error", "Failed to stop slideshow service.")

    def _check_status(self):
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "screensync"],
                capture_output=True, text=True
            )
            status = result.stdout.strip()
            if status == "active":
                self.status_label.configure(text="  Running  ", foreground=SUCCESS)
            else:
                self.status_label.configure(text="  Stopped  ", foreground=DANGER)
        except Exception:
            self.status_label.configure(text="  Unknown  ", foreground=TEXT_MUTED)
        self.root.after(5000, self._check_status)


def main():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)

    root = tk.Tk()
    root.geometry("850x650")
    ScreenSyncApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
