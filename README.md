# CueBeam

[![CI](https://github.com/NicholasTracy/CueBeam/actions/workflows/python-app.yml/badge.svg)](https://github.com/NicholasTracy/CueBeam/actions/workflows/python-app.yml)
[![pre-commit](https://github.com/NicholasTracy/CueBeam/actions/workflows/pre-commit.yml/badge.svg)](https://github.com/NicholasTracy/CueBeam/actions/workflows/pre-commit.yml)

CueBeam is a lightweight **media cue playback system** designed for **Raspberry Pi** (and other Linux SBCs) that gives you gapless, automated video playback with a simple **web interface**.

Think of it as a remote-controlled, always-on media player appliance — ideal for events, kiosks, installations, or stage productions.

---

## ✨ Features

- 🎥 Gapless video playback using **MPV**
- 🌐 Web UI (FastAPI + WebSockets)
- 📡 REST API for automation
- 🎛️ Cue-based control system
- 🔌 GPIO + Art-Net + sACN input triggers
- 🔊 Bluetooth A2DP pairing & auto-reconnect
- ⚡ Lightweight, runs on Raspberry Pi

---

## 🚀 Quick Install (One-Liner)

On a fresh Raspberry Pi OS:

```bash
curl -sSL https://raw.githubusercontent.com/NicholasTracy/CueBeam/main/install.sh | bash
```

This will:
- Install dependencies
- Clone CueBeam
- Create a Python venv
- Install requirements
- Set up systemd service

Once done, CueBeam is live at:

👉 `http://<pi-ip>:8080`

---

## 🛠 Manual Install

If you prefer manual setup:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-dev git mpv ffmpeg \
    bluetooth bluez bluez-tools python3-rpi.gpio python3-gpiozero

git clone https://github.com/NicholasTracy/CueBeam.git
cd CueBeam
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

uvicorn --app-dir src cuebeam.web.asgi:app --host 0.0.0.0 --port 8080
```

---

## ▶️ Usage

- Open browser to: `http://<pi-ip>:8080`
- Drag & drop media files into the `media/` folder
- Control via:
  - Web UI
  - REST API
  - WebSocket status feed
  - Triggers (GPIO / Art-Net / sACN)
  - Bluetooth Audio interface for scanning and connecting bluetooth devices

---

## 📡 API (FastAPI)

Interactive docs at:

👉 `http://<pi-ip>:8080/docs`

---

## 🔄 Updating CueBeam

```bash
cd ~/CueBeam
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart cuebeam
```

---

## 🧪 Testing (TODO)

```bash
pytest
```

---

## 📦 Project Layout

In the reorganised structure, all Python modules live inside a
`src/cuebeam` package.  This keeps the repository root clean and
prevents accidental imports from the working directory when the
project is installed in editable mode.

```
CueBeam/
├── src/
│   └── cuebeam/
│       ├── __init__.py   # exposes PlaybackManager and ControlManager
│       ├── bt.py         # Bluetooth utilities
│       ├── control.py    # Cue and trigger handling
│       ├── playback.py   # Playback engine
│       └── web/
│           ├── __init__.py
│           ├── app.py    # FastAPI application factory and routes
│           └── asgi.py   # ASGI entrypoint for Uvicorn
├── install.sh          # One‑line installer script
├── scripts/install.sh  # Detailed install script used by developers
├── config/             # Default configuration YAML
├── playlists/          # Stores the current playlist
├── static/             # CSS/JS assets (dark responsive theme)
├── templates/          # HTML templates for the web UI
└── systemd/            # systemd service unit
```

Note: the root‑level `cuebeam` directory from earlier versions has
been removed.  Use `src/cuebeam` as the canonical import path.

---

## 📝 License

GPLv3 — free to use, modify, and share.
