import re
import subprocess
import time
from typing import List, Tuple

DEVICE_RE = re.compile(r"Device\s+([0-9A-F:]{17})\s+(.+)$")


def _run(cmd: str, timeout: int = 8) -> str:
    proc = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        text=True,
        check=False,
    )
    return proc.stdout


def scan(seconds: int = 8) -> List[Tuple[str, str]]:
    _run('echo -e "scan on\n" | bluetoothctl')
    time.sleep(seconds)
    out = _run('echo -e "scan off\ndevices\n" | bluetoothctl')

    devices: List[Tuple[str, str]] = []
    for line in out.splitlines():
        m = DEVICE_RE.search(line.strip())
        if m:
            devices.append((m.group(1), m.group(2)))
    return devices


def paired_devices() -> List[Tuple[str, str]]:
    out = _run('echo -e "paired-devices\n" | bluetoothctl')
    devices: List[Tuple[str, str]] = []
    for line in out.splitlines():
        m = DEVICE_RE.search(line.strip())
        if m:
            devices.append((m.group(1), m.group(2)))
    return devices


def pair_trust_connect(mac: str) -> bool:
    script = (
        "agent on\n"
        "default-agent\n"
        f"pair {mac}\n"
        f"trust {mac}\n"
        f"connect {mac}\n"
        "quit\n"
    )
    out = _run(f'echo -e "{script}" | bluetoothctl', timeout=20)
    ok = ("Connection successful" in out) or ("Connection attempt failed" not in out)
    return ok


def connect(mac: str) -> bool:
    out = _run(f'echo -e "connect {mac}\n" | bluetoothctl', timeout=15)
    return ("Connection successful" in out) or ("Already connected" in out)


def ensure_connected(preferred_mac: str) -> bool:
    if not preferred_mac:
        return False
    return connect(preferred_mac)
