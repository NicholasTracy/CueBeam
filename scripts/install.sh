
#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"
USER_NAME="${SUDO_USER:-$USER}"

echo "[1/6] Installing apt packages..."
sudo apt-get update
sudo apt-get install -y   python3-full python3-venv python3-pip   mpv libmpv1   pigpio python3-pigpio   bluez bluez-tools   unzip curl

echo "[2/6] Enabling pigpio + Bluetooth daemons..."
sudo systemctl enable --now pigpiod
sudo systemctl enable --now bluetooth

echo "[3/6] Creating virtualenv (with system site packages)..."
if [ ! -d .venv ]; then
  python3 -m venv --system-site-packages .venv
fi
source .venv/bin/activate
python -m pip install -U pip setuptools wheel

echo "[4/6] Installing Python requirements..."
grep -q '^python-multipart' requirements.txt || echo 'python-multipart>=0.0.9' >> requirements.txt
python -m pip install -r requirements.txt

echo "[5/6] Creating folders and default config..."
mkdir -p media/{idle,events,random} playlists logs config
if [ ! -s config/config.yaml ]; then
  cat > config/config.yaml <<'YAML'
idle_to_random_seconds: 60
daily_shutdown_time: ""
mpv_flags: []
audio_output_device: ""
trigger_source: "gpio"
gpio: { pin: 17, pull: "up", edge: "falling", debounce_ms: 50 }
artnet: { listen_host: "0.0.0.0", port: 6454, universe: 0, channel: 1, threshold: 128 }
sacn:   { universe: 1, channel: 1, threshold: 128 }
bluetooth: { preferred_mac: "", scan_seconds: 8 }
auth: { enabled: false, cookie_secret: "" }
YAML
fi

echo "[6/6] Installing systemd service..."
sudo tee /etc/systemd/system/cuebeam.service >/dev/null <<EOF
[Unit]
Description=CueBeam media controller
After=network-online.target bluetooth.service pigpiod.service
Wants=network-online.target

[Service]
User=${USER_NAME}
WorkingDirectory=${REPO_DIR}
Environment=GPIOZERO_PIN_FACTORY=pigpio
ExecStart=${REPO_DIR}/.venv/bin/uvicorn --app-dir src cuebeam.web.asgi:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=2
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
echo "Install complete. Start with: sudo systemctl enable --now cuebeam.service"
