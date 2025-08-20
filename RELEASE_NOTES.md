# CueBeam v0.1.1

## Fixes
- Pin `python-mpv==1.0.8` (valid on PyPI)
- Use correct DMX library name `sacn==1.11.0`
- PEP8 cleanup across Python modules for flake8 compliance
- CI installs `mpv` before Python deps

## Features
- WebSocket `/ws/status` live status feed
- Bluetooth scan, pair/trust/connect and preferred device auto-connect
- GPIO / Art-Net / sACN triggers with thresholds and debounce
