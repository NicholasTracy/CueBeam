import subprocess
from typing import List, Dict


def _run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    return r.stdout


def scan(timeout_sec: int = 8) -> List[Dict[str, str]]:
    _run(["bluetoothctl", "--timeout", str(timeout_sec), "scan", "on"])
    out = _run(["bluetoothctl", "devices"])
    devices = []
    for line in out.splitlines():
        parts = line.strip().split(" ", 2)
        if len(parts) >= 3 and parts[0] == "Device":
            mac = parts[1]
            name = parts[2]
            devices.append({"mac": mac, "name": name})
    return devices


def pair_trust_connect(mac: str) -> bool:
    mac = mac.strip()
    if not mac:
        return False
    _run(["bluetoothctl", "power", "on"])
    _run(["bluetoothctl", "agent", "on"])
    _run(["bluetoothctl", "default-agent"])
    _run(["bluetoothctl", "pair", mac])
    _run(["bluetoothctl", "trust", mac])
    out = _run(["bluetoothctl", "connect", mac])
    info = _run(["bluetoothctl", "info", mac])
    return "Connection successful" in out or "Connected: yes" in info


def ensure_connected(mac: str) -> bool:
    mac = mac.strip()
    if not mac:
        return False
    info = _run(["bluetoothctl", "info", mac])
    if "Connected: yes" in info:
        return True
    out = _run(["bluetoothctl", "connect", mac])
    info2 = _run(["bluetoothctl", "info", mac])
    return "Connection successful" in out or "Connected: yes" in info2
