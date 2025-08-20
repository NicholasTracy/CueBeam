# CueBeam

Headless playlisted video playback on Raspberry Pi (HDMI) with idle/event/random logic, GPIO or Art-Net/sACN triggers (stubs), Bluetooth audio pairing, web UI, now-playing + system info panels, and systemd autostart.

## Quick install (Pi)

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/yourname/CueBeam.git
cd CueBeam
bash scripts/install.sh
sudo systemctl enable --now cuebeam.service
```

Open `http://<pi-ip>:8080`

## Develop (no systemd)

```bash
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -U pip && pip install -r requirements.txt
export GPIOZERO_PIN_FACTORY=pigpio
uvicorn asgi:app --host 0.0.0.0 --port 8080 --reload --reload-exclude media
```

Add videos to `media/idle`, `media/events`, `media/random` (or use Upload).
