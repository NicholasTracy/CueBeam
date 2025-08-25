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


def pair_trust_connect(mac: str, pin: str | None = None) -> bool:
    """Pair, trust and connect to a device given its MAC address.

    If a ``pin`` is supplied, an interactive pairing attempt is made to
    accommodate legacy devices that require a PIN code.  In this mode the
    function will attempt to respond to a PIN or passkey prompt automatically
    by sending the provided PIN or confirming the displayed passkey.  When no
    ``pin`` is given, the original non‑interactive behaviour is used.
    """
    mac = mac.strip()
    if not mac:
        return False
    # Always ensure the controller is powered and an agent is registered
    _run(["bluetoothctl", "power", "on"])
    _run(["bluetoothctl", "agent", "on"])
    _run(["bluetoothctl", "default-agent"])
    # If no PIN provided, fall back to the simple pairing sequence
    if not pin:
        _run(["bluetoothctl", "pair", mac])
        _run(["bluetoothctl", "trust", mac])
        out = _run(["bluetoothctl", "connect", mac])
        info = _run(["bluetoothctl", "info", mac])
        return "Connection successful" in out or "Connected: yes" in info
    # Otherwise attempt an interactive pair using pexpect
    try:
        import pexpect  # type: ignore
    except Exception:
        # pexpect not available; cannot handle PIN prompts
        return False
    # Spawn bluetoothctl in interactive mode
    try:
        child = pexpect.spawn("bluetoothctl", encoding="utf-8", timeout=30)
        # Wait for initial prompt
        # Match prompts from bluetoothctl.  Use raw strings to avoid invalid
        # escape sequence warnings (W605) for backslash characters.
        child.expect([r"#", r"\$", pexpect.TIMEOUT, pexpect.EOF])
        child.sendline("power on")
        child.sendline("agent KeyboardOnly")
        child.sendline("default-agent")
        child.sendline(f"pair {mac}")
        paired = False
        while True:
            idx = child.expect([
                "Enter PIN code:",
                "[agent] Confirm passkey",
                "Pairing successful",
                "Failed to pair",
                pexpect.EOF,
                pexpect.TIMEOUT,
            ])
            # Prompt for PIN: send the supplied code
            if idx == 0:
                child.sendline(pin)
                continue
            # Prompt to confirm a displayed passkey – always confirm
            if idx == 1:
                child.sendline("yes")
                continue
            # Successful pairing
            if idx == 2:
                paired = True
                break
            # Failure or unexpected output
            if idx in (3, 4, 5):
                break
        # After pairing attempt, trust and connect regardless of success
        child.sendline(f"trust {mac}")
        child.sendline(f"connect {mac}")
        # Wait briefly for output then terminate
        try:
            child.expect("Connected: yes", timeout=10)
            connected = True
        except Exception:
            connected = False
        child.close()
        return paired or connected
    except Exception:
        # Any unexpected error means the pairing failed
        return False


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
