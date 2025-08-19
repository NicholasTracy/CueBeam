import socket
import struct
import threading
from typing import Callable, List, Optional

from gpiozero import Button
import sacn


class ControlManager:
    def __init__(self, cfg: dict, on_event: Callable[[], None]) -> None:
        self.cfg = cfg
        self.on_event = on_event
        self._threads: List[threading.Thread] = []
        self._stop = threading.Event()
        self._gpio_btn: Optional[Button] = None
        self._sacn: Optional[sacn.sACNreceiver] = None

    def start(self) -> None:
        source = (self.cfg.get("trigger_source") or "gpio").lower()
        if source == "gpio":
            self._start_gpio()
        elif source == "artnet":
            self._start_artnet()
        elif source == "sacn":
            self._start_sacn()

    def stop(self) -> None:
        self._stop.set()
        if self._gpio_btn:
            try:
                self._gpio_btn.close()
            except Exception:
                pass
        if self._sacn:
            try:
                self._sacn.stop()
            except Exception:
                pass

    # --- backends ---------------------------------------------------------

    def _start_gpio(self) -> None:
        g = self.cfg.get("gpio", {})
        pin = int(g.get("pin", 17))
        pull = (g.get("pull", "up") or "up").lower()
        edge = (g.get("edge", "falling") or "falling").lower()
        debounce_s = max(0, int(g.get("debounce_ms", 50))) / 1000.0

        pull_up = pull == "up"
        btn = Button(pin, pull_up=pull_up, bounce_time=debounce_s or None)
        self._gpio_btn = btn

        def cb() -> None:
            self.on_event()

        if edge in ("falling", "both"):
            btn.when_pressed = cb
        if edge in ("rising", "both"):
            btn.when_released = cb

    def _start_artnet(self) -> None:
        a = self.cfg.get("artnet", {})
        host = a.get("listen_host", "0.0.0.0")
        port = int(a.get("port", 6454))
        universe = int(a.get("universe", 0))
        channel = max(1, min(512, int(a.get("channel", 1)))) - 1
        threshold = int(a.get("threshold", 128))

        def run() -> None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind((host, port))
            sock.settimeout(1.0)
            header = b"Art-Net\x00"

            while not self._stop.is_set():
                try:
                    data, _ = sock.recvfrom(2048)
                except socket.timeout:
                    continue

                if not data.startswith(header):
                    continue

                # OpCode 0x5000 (OpDmx) in little-endian
                if data[8:10] != b"\x00P":
                    continue

                u = struct.unpack("<H", data[14:16])[0]
                if u != universe:
                    continue

                length = struct.unpack(">H", data[16:18])[0]
                dmx = data[18 : 18 + length]
                if channel < len(dmx) and dmx[channel] >= threshold:
                    self.on_event()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        self._threads.append(t)

    def _start_sacn(self) -> None:
        s = self.cfg.get("sacn", {})
        universe = int(s.get("universe", 1))
        channel = max(1, min(512, int(s.get("channel", 1)))) - 1
        threshold = int(s.get("threshold", 128))

        receiver = sacn.sACNreceiver()
        self._sacn = receiver

        @receiver.listen_on("universe", universe=universe)  # type: ignore[misc]
        def callback(packet):  # type: ignore[no-redef]
            if channel < len(packet.dmxData) and packet.dmxData[channel] >= threshold:
                self.on_event()

        receiver.start()
