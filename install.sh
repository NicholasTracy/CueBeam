#!/bin/bash
set -e

APP_NAME="CueBeam"
APP_DIR="/home/pi/$APP_NAME"
SERVICE_FILE="/etc/systemd/system/cuebeam.service"

echo "🚀 Installing $APP_NAME..."

# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install dependencies
sudo apt install -y python3 python3-venv python3-dev git mpv ffmpeg \
    bluetooth bluez bluez-tools python3-rpi.gpio python3-gpiozero

# 3. Clone or update repo
if [ ! -d "$APP_DIR" ]; then
    git clone https://github.com/<your-username>/CueBeam.git "$APP_DIR"
else
    cd "$APP_DIR"
    git pull
fi

cd "$APP_DIR"

# 4. Python virtualenv
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip wheel setuptools
pip install -r requirements.txt

# 5. Systemd service
echo "⚙️ Setting up systemd service..."
sudo tee $SERVICE_FILE > /dev/null <<EOL
[Unit]
Description=CueBeam Media Playback Server
After=network.target

[Service]
User=pi
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/uvicorn asgi:app --host 0.0.0.0 --port 8080
Restart=always

[Install]
WantedBy=multi-user.target
EOL

sudo systemctl daemon-reload
sudo systemctl enable cuebeam
sudo systemctl restart cuebeam

echo "✅ $APP_NAME installed and running at http://<pi-ip>:8080"
