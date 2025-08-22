#!/usr/bin/env bash
set -euo pipefail

APP_NAME="CueBeam"
# Replace with your username before committing:
# Use the maintainer’s GitHub account by default.  Replace the username
# if you are hosting your own fork.
REPO_URL="https://github.com/NicholasTracy/CueBeam.git"
APP_DIR="/home/pi/CueBeam"
PY="/usr/bin/python3"

echo "==> Updating apt and installing system packages"
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-dev git mpv ffmpeg \
  bluetooth bluez bluez-tools python3-rpi.gpio python3-gpiozero \
  libmpv2 || sudo apt install -y libmpv1

echo "==> Cloning or updating repository"
if [[ ! -d "$APP_DIR/.git" ]]; then
  sudo rm -rf "$APP_DIR"
  git clone "$REPO_URL" "$APP_DIR"
else
  (cd "$APP_DIR" && git pull --ff-only)
fi

echo "==> Creating media directories"
mkdir -p "$APP_DIR/media/idle" "$APP_DIR/media/event" "$APP_DIR/media/random"
sudo chown -R pi:pi "$APP_DIR/media"

echo "==> Creating Python venv and installing requirements"
cd "$APP_DIR"
if [[ ! -d venv ]]; then
  "$PY" -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
python -m pip install -U pip wheel setuptools
pip install -r requirements.txt || true
pip install \
  fastapi "uvicorn[standard]" jinja2 python-multipart \
  websockets ujson pyyaml mpv

echo "==> Installing systemd service"
sudo tee /etc/systemd/system/cuebeam.service >/dev/null <<'UNIT'
[Unit]
Description=CueBeam Media Playback Server
After=network-online.target
Wants=network-online.target

[Service]
User=pi
WorkingDirectory=/home/pi/CueBeam
Environment=LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu:/usr/lib/arm-linux-gnueabihf
# Point uvicorn to the new ASGI entrypoint.  ``--app-dir src`` adds the
# ``src`` directory to the Python module search path so that the
# ``cuebeam`` package can be found.  See ``src/cuebeam/web/asgi.py``.
ExecStart=/home/pi/CueBeam/venv/bin/uvicorn --app-dir src cuebeam.web.asgi:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
UNIT

echo "==> Enabling and starting service"
sudo systemctl daemon-reload
sudo systemctl enable cuebeam
sudo systemctl restart cuebeam

echo "==> Checking service status"
sleep 2
sudo systemctl --no-pager -l status cuebeam || true

echo "==> Done. Open: http://<pi-ip>:8080"
