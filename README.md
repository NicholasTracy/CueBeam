# CueBeam

[![CI](https://github.com/<your-username>/CueBeam/actions/workflows/python-app.yml/badge.svg)](https://github.com/<your-username>/CueBeam/actions/workflows/python-app.yml)
[![pre-commit](https://github.com/<your-username>/CueBeam/actions/workflows/pre-commit.yml/badge.svg)](https://github.com/<your-username>/CueBeam/actions/workflows/pre-commit.yml)

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
curl -sSL https://raw.githubusercontent.com/<your-username>/CueBeam/main/install.sh | bash
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

git clone https://github.com/<your-username>/CueBeam.git
cd CueBeam
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

uvicorn asgi:app --host 0.0.0.0 --port 8080
```

---

## ▶️ Usage

- Open browser to: `http://<pi-ip>:8080`
- Drag & drop media files into the `media/` folder
- Control via:
  - Web UI
  - REST API
  - WebSocket status feed
  - Triggers (GPIO / Art-Net / sACN / Bluetooth)

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

## 🧪 Testing

```bash
pytest
```

---

## 📦 Project Layout

```
CueBeam/
├── asgi.py        # FastAPI entrypoint
├── web.py         # Web routes / UI
├── playback.py    # Playback engine
├── control.py     # Cue + trigger handling
├── requirements.txt
├── install.sh     # Auto installer
└── README.md
```

---

## 📝 License

GPLv3 — free to use, modify, and share.
