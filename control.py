import threading
from typing import Callable, Any, Dict

from playback import PlaybackManager  # only for type context, not required


class ControlManager:
    def __init__(self, cfg: Dict[str, Any], on_event: Callable[[], None]) -> None:
        self.cfg = cfg
        self._on_event = on_event
        self._gpio_button = None
        self._thread = None

    def start(self) -> None:
        src = (self.cfg.get("trigger_source") or "gpio").lower()
        if src == "gpio":
            self._start_gpio()
        elif src == "artnet":
            self._start_artnet()
        elif src == "sacn":
            self._start_sacn()
        else:
            print(f"[WARN] Unknown trigger_source: {src}")

    # --- GPIO

    def _on_trigger(self) -> None:
        try:
            self._on_event()
        except Exception as e:
            print(f"[trigger] {e}")

    def _start_gpio(self) -> None:
        try:
            from gpiozero import Button
            g = self.cfg.get("gpio") or {}
            pin = int(g.get("pin", 17))
            pull_up = (g.get("pull", "up").lower() == "up")
            bounce_s = float(g.get("debounce_ms", 50)) / 1000.0
            edge = (g.get("edge", "falling").lower())
            btn = Button(pin, pull_up=pull_up, bounce_time=bounce_s or None)
            if edge == "rising":
                btn.when_pressed = self._on_trigger
            elif edge == "both":
                btn.when_pressed = self._on_trigger
                btn.when_released = self._on_trigger
            else:
                btn.when_released = self._on_trigger
            self._gpio_button = btn
            print(f"[GPIO] listening on BCM {pin} ({'pull_up' if pull_up else 'pull_down'}) edge={edge}")
        except Exception as e:
            print(f"[WARN] GPIO disabled: {e}")

    # --- Art-Net / sACN placeholders (previous logic assumed)
    def _start_artnet(self) -> None:
        # TODO: hook your existing artnet listener here
        print("[ArtNet] listener enabled")

    def _start_sacn(self) -> None:
        # TODO: hook your existing sACN listener here
        print("[sACN] listener enabled")