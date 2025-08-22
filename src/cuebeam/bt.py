"""
Bluetooth helper functions for CueBeam.

This module wraps the ``bluetoothctl`` CLI commands to scan for devices,
pair and trust, and ensure a connection.  In a future release these
functions should be replaced with a proper D‑Bus interface for better
robustness and error handling.
"""

import subprocess
from typing import List, Dict


def _run(cmd: list[str]) -> str:
    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return res.stdout


def scan(timeout_sec: int = 8) -> List[Dict[str, str]]:
    """Scan for Bluetooth devices.

    Returns a list of dicts with keys ``mac`` and ``name``.
    """
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
    """Pair, trust and connect to a device given its MAC address."""
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
    """Ensure a device is connected.  Attempt to connect if disconnected."""
    mac = mac.strip()
    if not mac:
        return False
    info = _run(["bluetoothctl", "info", mac])
    if "Connected: yes" in info:
        return True
    out = _run(["bluetoothctl", "connect", mac])
    info2 = _run(["bluetoothctl", "info", mac])
    return "Connection successful" in out or "Connected: yes" in info2
