from typing import Callable, Any, Dict


class ControlManager:
    def __init__(self, cfg: Dict[str, Any], on_event: Callable[[], None]) -> None:
        self.cfg = cfg
        self._on_event = on_event
        self._gpio_button = None

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

    def _on_trigger(self) -> None:
        try:
            self._on_event()
        except Exception as exc:
            print(f"[trigger] {exc}")

    def _start_gpio(self) -> None:
        try:
            from gpiozero import Button

            g = self.cfg.get("gpio") or {}
            pin = int(g.get("pin", 17))
            pull_up = (g.get("pull", "up").lower() == "up")
            bounce_s = float(g.get("debounce_ms", 50)) / 1000.0
            edge = g.get("edge", "falling").lower()

            btn = Button(pin, pull_up=pull_up, bounce_time=bounce_s or None)

            if edge == "rising":
                btn.when_pressed = self._on_trigger
            elif edge == "both":
                btn.when_pressed = self._on_trigger
                btn.when_released = self._on_trigger
            else:
                btn.when_released = self._on_trigger

            self._gpio_button = btn
            print(
                f"[GPIO] listening on BCM {pin} "
                f"({'pull_up' if pull_up else 'pull_down'}) edge={edge}"
            )
        except Exception as exc:
            print(f"[WARN] GPIO disabled: {exc}")

    def _start_artnet(self) -> None:
        print("[ArtNet] listener enabled (stub)")

    def _start_sacn(self) -> None:
        print("[sACN] listener enabled (stub)")
