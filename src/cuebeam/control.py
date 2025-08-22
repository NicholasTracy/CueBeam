"""
Trigger controller for CueBeam.

This module implements ``ControlManager`` which monitors external triggers
(GPIO, Art‑Net, sACN) and calls a callback when an event is detected.  It
uses structured logging instead of ``print`` for observability.
"""

from typing import Callable, Any, Dict
import logging


class ControlManager:
    def __init__(self, cfg: Dict[str, Any], on_event: Callable[[], None]) -> None:
        self.cfg = cfg
        self._on_event = on_event
        self._gpio_button = None
        # Each instance uses its own logger derived from the module name for
        # consistent logging.  Avoid using print statements; logging provides
        # timestamps, severity levels and better configurability【690924082245555†L52-L120】.
        self.logger = logging.getLogger(__name__)

    def start(self) -> None:
        """Start listening for events based on the configured trigger source."""
        src = (self.cfg.get("trigger_source") or "gpio").lower()
        if src == "gpio":
            self._start_gpio()
        elif src == "artnet":
            self._start_artnet()
        elif src == "sacn":
            self._start_sacn()
        else:
            self.logger.warning("Unknown trigger_source: %s", src)

    def _on_trigger(self) -> None:
        try:
            self._on_event()
        except Exception as exc:
            # Log the exception; retain traceback for debugging
            self.logger.exception("Exception in trigger handler: %s", exc)

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
            self.logger.info(
                "[GPIO] listening on BCM %s (%s) edge=%s",
                pin,
                "pull_up" if pull_up else "pull_down",
                edge,
            )
        except Exception as exc:
            self.logger.warning("GPIO disabled: %s", exc)

    def _start_artnet(self) -> None:
        # Stub implementation; log instead of printing
        self.logger.info("[ArtNet] listener enabled (stub)")

    def _start_sacn(self) -> None:
        # Stub implementation; log instead of printing
        self.logger.info("[sACN] listener enabled (stub)")