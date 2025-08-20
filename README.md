# CueBeam

[![CI](https://github.com/<your-username>/CueBeam/actions/workflows/python-app.yml/badge.svg)](https://github.com/<your-username>/CueBeam/actions/workflows/python-app.yml)
[![pre-commit](https://github.com/<your-username>/CueBeam/actions/workflows/pre-commit.yml/badge.svg)](https://github.com/<your-username>/CueBeam/actions/workflows/pre-commit.yml)

CueBeam is a lightweight **media cue playback system** designed for **Raspberry Pi** (and other Linux SBCs) that gives you gapless, automated video playback with a simple **web interface**. 

Think of it as a remote-controlled, always-on media player appliance — ideal for events, kiosks, installations, or stage productions.

---

## ✨ Features

- 🎬 **Gapless playback** with `mpv` backend (no black frames between files)
- 📂 Organize files into:
  - `idle/` — looped background playback
  - `cues/` — triggered or scheduled playback
- 📱 **Web UI** for uploading, managing, and triggering videos
- 🔌 **GPIO integration** — trigger cues via physical buttons or Artnet/sACN
- 📡 **Bluetooth scan/pair support** (in Settings tab)
- 🚀 Autostart as a systemd service
- 🛠️ Built with **FastAPI**, **uvicorn**, **WebSockets**, and **mpv JSON IPC**

---

## 📋 Requirements

- Raspberry Pi 3 (or similar SBC, x86 also works)
- Raspberry Pi OS Lite or Debian/Ubuntu-based Linux
- Installed system packages:
  ```bash
  sudo apt update
  sudo apt install -y python3 python3-venv python3-dev git mpv ffmpeg \
                      bluetooth bluez bluez-tools
  ```
- (Optional, for GPIO)  
  ```bash
  sudo apt install -y python3-rpi.gpio python3-gpiozero
  ```

---

## ⚡ Quick Install

```bash
# Clone the repo
git clone https://github.com/NicholasTracy/CueBeam.git
cd CueBeam

# Create and activate venv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -U pip wheel
pip install -r requirements.txt

# Run server
uvicorn asgi:app --host 0.0.0.0 --port 8080
```

Then open a browser to:  
👉 `http://<pi-ip-address>:8080`

---

## 📂 Project Layout

```
CueBeam/
├── app.py                # Entry point
├── asgi.py               # ASGI server config
├── playback.py           # PlaybackManager (mpv controller)
├── control.py            # GPIO / external control
├── bt.py                 # Bluetooth scan & pairing
├── web.py                # FastAPI routes, upload UI
├── static/               # Web frontend assets
├── templates/            # Jinja2 HTML templates
├── playlists/            # (optional) saved cue sequences
├── idle/                 # idle videos (looped)
├── cues/                 # cue videos (triggered)
└── tools/
    └── bump_version.py   # helper script
```

---

## 🖥️ Usage

1. Upload idle videos via the **Web UI** → “Idle” tab.
   - These loop continuously when no cues are active.
2. Upload cue videos via the **Web UI** → “Cues” tab.
   - These can be triggered on demand or via GPIO.
3. Manage system settings via the **Settings** tab:
   - Scan & pair Bluetooth devices
   - Configure GPIO triggers
   - Restart/reload playback
4. Use WebSocket API (`/ws/status`) for real-time monitoring.

---

## 🔧 Autostart as Service

```bash
sudo cp cuebeam.service /etc/systemd/system/
sudo systemctl enable cuebeam
sudo systemctl start cuebeam
```

Service will now run on boot, serving at port **8080**.

---

## 👨‍💻 Development

We enforce **flake8** and **mypy** with [pre-commit](https://pre-commit.com/).

### One-time setup:

```bash
pip install pre-commit
pre-commit install
```

### Run hooks manually:

```bash
pre-commit run --all-files
```

### Run tests (if added):

```bash
pytest
```

---

## 📡 API (FastAPI)

Once running, explore the interactive API docs at:  
👉 `http://<pi-ip>:8080/docs`

---

## 📜 License

Licensed under the **GPL v3** — see [LICENSE](LICENSE).

---

## 🙌 Contributing

- Fork the repo & create feature branches
- Make sure `pre-commit run --all-files` passes
- Open a PR with details of your change

---

## 📸 Demo

![Web UI Screenshot](static/demo.png)

_Example of CueBeam web interface — upload, manage, and trigger video playback from your browser._

---
