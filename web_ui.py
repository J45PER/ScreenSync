#!/usr/bin/env python3
"""
ScreenSync Web UI — manage images, screens, and device configuration.

Run on each Pi:
    python3 web_ui.py

Then visit http://<pi-ip>:5000 in a browser.
"""

import json
import glob
import os
import shutil
import subprocess

from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(BASE_DIR, "images")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"),
            static_folder=os.path.join(BASE_DIR, "static"))

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "bmp", "gif", "webp"}

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "screens": ["Left", "Right"],
    "device_screens": [],          # which screen(s) THIS device drives
    "slide_duration": 20,
    "fade_duration": 1.0,
    "slots": 6,                    # total number of image slots (00-05)
}


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        # Merge with defaults for any missing keys
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

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_slot_images() -> dict:
    """Return {(slot_index, screen_name): filepath} for all images found."""
    result = {}
    os.makedirs(IMAGES_DIR, exist_ok=True)
    for path in glob.glob(os.path.join(IMAGES_DIR, "*")):
        basename = os.path.basename(path)
        # Parse "00. Left.png" format
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
    """Remove any existing image for a given slot + screen."""
    pattern = os.path.join(IMAGES_DIR, f"{slot:02d}. {screen_name}.*")
    for f in glob.glob(pattern):
        os.remove(f)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    cfg = load_config()
    images = get_slot_images()
    return render_template("index.html", config=cfg, images=images)


@app.route("/config", methods=["POST"])
def update_config():
    cfg = load_config()

    # Screen names (comma-separated)
    screens_raw = request.form.get("screens", "")
    if screens_raw.strip():
        cfg["screens"] = [s.strip() for s in screens_raw.split(",") if s.strip()]

    # Which screen(s) this device drives
    device_screens = request.form.getlist("device_screens")
    cfg["device_screens"] = device_screens

    # Timing
    try:
        cfg["slide_duration"] = int(request.form.get("slide_duration", 20))
    except ValueError:
        pass
    try:
        cfg["fade_duration"] = float(request.form.get("fade_duration", 1.0))
    except ValueError:
        pass

    # Number of slots
    try:
        cfg["slots"] = int(request.form.get("slots", 6))
    except ValueError:
        pass

    save_config(cfg)
    return redirect(url_for("index"))


@app.route("/upload", methods=["POST"])
def upload_image():
    slot = request.form.get("slot")
    screen_name = request.form.get("screen_name")
    file = request.files.get("file")

    if not slot or not screen_name or not file or not file.filename:
        return redirect(url_for("index"))

    try:
        slot = int(slot)
    except ValueError:
        return redirect(url_for("index"))

    if not allowed_file(file.filename):
        return redirect(url_for("index"))

    ext = file.filename.rsplit(".", 1)[1].lower()
    os.makedirs(IMAGES_DIR, exist_ok=True)

    # Remove old file for this slot+screen
    clear_slot_image(slot, screen_name)

    dest = os.path.join(IMAGES_DIR, f"{slot:02d}. {screen_name}.{ext}")
    file.save(dest)
    return redirect(url_for("index"))


@app.route("/delete", methods=["POST"])
def delete_image():
    slot = request.form.get("slot")
    screen_name = request.form.get("screen_name")
    if slot is not None and screen_name:
        clear_slot_image(int(slot), screen_name)
    return redirect(url_for("index"))


@app.route("/images/<path:filename>")
def serve_image(filename):
    return send_from_directory(IMAGES_DIR, filename)


@app.route("/slideshow/start", methods=["POST"])
def start_slideshow():
    try:
        subprocess.run(["sudo", "systemctl", "start", "screensync"], check=True)
        return jsonify({"status": "started"})
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/slideshow/stop", methods=["POST"])
def stop_slideshow():
    try:
        subprocess.run(["sudo", "systemctl", "stop", "screensync"], check=True)
        return jsonify({"status": "stopped"})
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/slideshow/status")
def slideshow_status():
    result = subprocess.run(
        ["systemctl", "is-active", "screensync"],
        capture_output=True, text=True
    )
    return jsonify({"status": result.stdout.strip()})


if __name__ == "__main__":
    os.makedirs(IMAGES_DIR, exist_ok=True)
    # Ensure a config exists
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
    app.run(host="0.0.0.0", port=5000, debug=False)
