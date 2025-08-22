"""
Playback management for CueBeam.

This module provides the :class:`PlaybackManager` class which wraps the
``mpv`` media player and offers methods to start idle playback, trigger
event/random clips and query or modify playback state.  Paths for
media, playlists and configuration are resolved relative to the project
root so that the package can live under a ``src`` directory without
requiring the repository root to be on the import path.

Key improvements over earlier versions:

* All logging is performed via the :mod:`logging` module rather than
  ``print`` statements.  Structured logging provides timestamps,
  severity levels and configurability【690924082245555†L52-L120】.
* Uploaded filenames are sanitised in the web layer to prevent
  directory traversal; see :mod:`cuebeam.web.app`.
* The project root is computed dynamically, ensuring that media and
  config paths resolve correctly when the package is installed in a
  subdirectory.
"""

from __future__ import annotations

import logging
import os
import random
import threading
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

import yaml
from apscheduler.schedulers.background import BackgroundScheduler
from mpv import MPV

from .bt import ensure_connected

# Obtain a module‑level logger.  Clients can configure the root logger
# elsewhere to control formatting and output.  Never use ``print`` here.
logger = logging.getLogger(__name__)

# Compute the project root two levels up from this file.  ``__file__``
# points at ``src/cuebeam/playback.py``; parents[0] is ``src/cuebeam``,
# parents[1] is ``src`` and parents[2] is the repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Define common directories relative to the project root.  These
# directories are created on demand when the manager is instantiated.
MEDIA_DIR = PROJECT_ROOT / "media"
PLAYLISTS_DIR = PROJECT_ROOT / "playlists"
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"

IDLE_DIR = MEDIA_DIR / "idle"
EVENTS_DIR = MEDIA_DIR / "events"
RANDOM_DIR = MEDIA_DIR / "random"
CURRENT_M3U = PLAYLISTS_DIR / "current.m3u"


class PlaybackManager:
    """Manages media playback using ``mpv``.

    The manager maintains a minimal internal state (last event
    timestamp, whether random mode is active, current playing path and
    pause status).  It exposes methods to start playback, inject event
    and random clips, toggle pause and skip to the next item.  A
    background idle monitor thread injects random clips after a period
    of inactivity.
    """

    def __init__(self) -> None:
        # Load or create configuration
        self._load_config()
        # Protect mutable state across threads
        self._lock = threading.RLock()
        self._state: Dict[str, Any] = {
            "last_event_ts": 0.0,
            "last_random_injected_ts": 0.0,
            "in_random_mode": False,
            "current_path": "",
            "is_paused": False,
        }

        # Background scheduler for daily shutdown
        self._scheduler = BackgroundScheduler()
        self._scheduler.start()
        self._apply_shutdown_schedule()

        # Initialise mpv player with configured audio output and flags
        flags: List[str] = self.cfg.get("mpv_flags", []) or []
        ao = self.cfg.get("audio_output_device") or None
        self.mpv = MPV(ao=ao, ytdl=False)

        # Do not set a global loop-playlist here.  The idle loop is enabled
        # explicitly in ``start()`` and disabled when event or random clips
        # are injected.  A global infinite loop across the entire playlist
        # would cause event or random clips to repeat indefinitely.

        # Apply mpv flags.  Unknown options are ignored gracefully.
        for f in flags:
            f = (f or "").strip()
            if not f:
                continue
            key, _, val = f.partition("=")
            key = key.lstrip("-").replace("-", "_")
            try:
                if val:
                    # Convert some common boolean/int strings
                    v_obj: object = val
                    if val.isdigit():
                        v_obj = int(val)
                    elif val.lower() in ("yes", "true", "on"):
                        v_obj = "yes"
                    elif val.lower() in ("no", "false", "off"):
                        v_obj = "no"
                    self.mpv.command("set", key, v_obj)
                else:
                    self.mpv.command("set", key, "yes")
            except Exception:
                # Fallback to set_property if command fails
                try:
                    if val:
                        self.mpv.set_property(key, val)
                    else:
                        self.mpv.set_property(key, True)
                except Exception:
                    logger.warning("ignoring unknown mpv option: %s", f)

        # Install hooks to track the currently playing file
        self._install_mpv_hooks()

        # Ensure necessary directories exist
        PLAYLISTS_DIR.mkdir(parents=True, exist_ok=True)
        for d in (MEDIA_DIR, IDLE_DIR, EVENTS_DIR, RANDOM_DIR):
            d.mkdir(parents=True, exist_ok=True)

        # Initialise an empty playlist file if none exists
        if not CURRENT_M3U.exists():
            CURRENT_M3U.write_text("", encoding="utf-8")

        # Attempt to connect to preferred Bluetooth device
        pref = (self.cfg.get("bluetooth") or {}).get("preferred_mac", "").strip()
        if pref:
            try:
                _ = ensure_connected(pref)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Bluetooth connection failed: %s", exc)

        # Start background idle monitor thread
        threading.Thread(target=self._idle_monitor_loop, daemon=True).start()

    # ------------------------------------------------------------------
    # Configuration handling
    def _load_config(self) -> None:
        """Load configuration from ``config.yaml`` or create defaults."""
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not CONFIG_PATH.exists():
            CONFIG_PATH.write_text(
                "idle_to_random_seconds: 60\n"
                'daily_shutdown_time: ""\n'
                "mpv_flags: []\n"
                'audio_output_device: ""\n'
                'trigger_source: "gpio"\n',
                encoding="utf-8",
            )
        self.cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}

        # Populate defaults
        self.cfg.setdefault("idle_to_random_seconds", 60)
        self.cfg.setdefault("daily_shutdown_time", "")
        self.cfg.setdefault("mpv_flags", [])
        self.cfg.setdefault("audio_output_device", "")
        self.cfg.setdefault("trigger_source", "gpio")
        self.cfg.setdefault(
            "gpio",
            {"pin": 17, "pull": "up", "edge": "falling", "debounce_ms": 50},
        )
        self.cfg.setdefault(
            "artnet",
            {
                "listen_host": "0.0.0.0",
                "port": 6454,
                "universe": 0,
                "channel": 1,
                "threshold": 128,
            },
        )
        self.cfg.setdefault("sacn", {"universe": 1, "channel": 1, "threshold": 128})
        self.cfg.setdefault("bluetooth", {"preferred_mac": "", "scan_seconds": 8})
        self.cfg.setdefault("auth", {"enabled": False})

    def reload_config(self) -> None:
        """Reload the configuration file and apply changes."""
        with self._lock:
            self._load_config()
            self._apply_shutdown_schedule()

    def _apply_shutdown_schedule(self) -> None:
        """Schedule a daily shutdown if ``daily_shutdown_time`` is set."""
        # Remove any existing job
        for job in self._scheduler.get_jobs():
            if job.id == "daily_shutdown":
                self._scheduler.remove_job(job.id)

        t = (self.cfg.get("daily_shutdown_time") or "").strip()
        if t:
            try:
                hh, mm = [int(x) for x in t.split(":", 1)]
            except ValueError:
                logger.warning("Invalid daily_shutdown_time: %s", t)
                return
            self._scheduler.add_job(
                self.shutdown_pi,
                "cron",
                hour=hh,
                minute=mm,
                id="daily_shutdown",
            )

    # ------------------------------------------------------------------
    # mpv hooks and helpers
    def _install_mpv_hooks(self) -> None:
        """Install hooks to update playback state when the path changes."""
        try:
            # If mpv supports property observers (python-mpv >= 1.0)
            @self.mpv.property_observer("path")  # type: ignore[no-redef]
            def _on_path(_name, val) -> None:
                path_str = str(val) if val else ""
                with self._lock:
                    self._state["current_path"] = path_str
                    if path_str.startswith(str(RANDOM_DIR)):
                        self._state["in_random_mode"] = True
                    elif path_str.startswith(str(IDLE_DIR)):
                        self._state["in_random_mode"] = False
        except AttributeError:
            # Fallback: poll the ``path`` property periodically
            def _poll_loop() -> None:
                last = ""
                while True:
                    try:
                        cur = str(getattr(self.mpv, "path", "") or "")
                    except Exception:
                        cur = ""
                    if cur != last:
                        with self._lock:
                            self._state["current_path"] = cur
                            if cur.startswith(str(RANDOM_DIR)):
                                self._state["in_random_mode"] = True
                            elif cur.startswith(str(IDLE_DIR)):
                                self._state["in_random_mode"] = False
                        last = cur
                    time.sleep(0.5)
            threading.Thread(target=_poll_loop, daemon=True).start()

    def _write_m3u(self, items: List[str]) -> None:
        tmp = CURRENT_M3U.with_suffix(".tmp")
        text = "\n".join(items) + ("\n" if items else "")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(CURRENT_M3U)

    def _read_m3u(self) -> List[str]:
        if not CURRENT_M3U.exists():
            return []
        lines = CURRENT_M3U.read_text(encoding="utf-8").splitlines()
        return [line.strip() for line in lines if line.strip()]

    def _clear_playlist(self) -> None:
        try:
            self.mpv.command("playlist-clear")
        except Exception:
            pass
        self._write_m3u([])

    def _random_file(self, folder: Path) -> Optional[Path]:
        vids = [p for p in folder.iterdir() if p.is_file()]
        return random.choice(vids) if vids else None

    def _rebuild_mpv_playlist(self, items: List[str]) -> None:
        cur = ""
        try:
            cur = str(getattr(self.mpv, "path", "") or "")
        except Exception:
            pass
        # Clear mpv's internal playlist and repopulate
        self.mpv.command("playlist-clear")
        for it in items:
            self.mpv.command("loadfile", it, "append-play")
        # If the previous current item is still in the list, jump to it
        if cur and cur in items:
            idx = items.index(cur)
            self.mpv.command("playlist-play-index", str(idx))
        else:
            self.mpv.command("playlist-play-index", "0")

    # ------------------------------------------------------------------
    # Public control methods
    def start(self) -> None:
        """Start playback by loading a random idle file."""
        with self._lock:
            idle = self._random_file(IDLE_DIR)
            if not idle:
                logger.warning("No idle files found in %s", IDLE_DIR)
                return
            # Clear playlist and start playing the idle clip
            self._clear_playlist()
            self.mpv.command("loadfile", str(idle), "append-play")
            self._write_m3u([str(idle)])
            # Enable infinite looping for the idle playlist
            try:
                self.mpv.command("set_property", "loop-playlist", "inf")
            except Exception:
                try:
                    self.mpv.command("set", "loop-playlist", "inf")
                except Exception:
                    pass
            self.mpv.pause = False

    def trigger_event(self) -> bool:
        """Inject an event clip into the playlist.

        Returns ``True`` if a clip was injected, otherwise ``False`` (e.g. no
        events available).  If a random clip is currently playing the
        event is not injected.
        """
        with self._lock:
            # Record the event timestamp
            self._state["last_event_ts"] = float(time.time())
            # Do not inject if a random clip is currently playing
            if bool(self._state["in_random_mode"]):
                return False
            ev = self._random_file(EVENTS_DIR)
            if not ev:
                return False
            idle = self._random_file(IDLE_DIR)
            # Build a new playlist: event plays immediately, then idle
            newlst: List[str] = [str(ev)]
            if idle:
                newlst.append(str(idle))
            else:
                logger.warning("No idle files available to follow event")
            # Write the playlist file
            self._write_m3u(newlst)
            # Replace current playback with event and following idle
            try:
                # Clear existing playlist and load new items
                self.mpv.command("playlist-clear")
                for it in newlst:
                    self.mpv.command("loadfile", it, "append-play")
                # Start playing the first item (event) immediately
                self.mpv.command("playlist-play-index", "0")
                # Disable looping while event/random playlists are active
                try:
                    self.mpv.command("set_property", "loop-playlist", "no")
                except Exception:
                    try:
                        self.mpv.command("set", "loop-playlist", "no")
                    except Exception:
                        pass
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to inject event clip: %s", exc)
                return False
            # Reset random mode state
            self._state["in_random_mode"] = False
            return True

    def trigger_random(self) -> bool:
        """Inject a random clip into the playlist.

        Returns ``True`` if a clip was injected, otherwise ``False``.
        """
        with self._lock:
            rnd = self._random_file(RANDOM_DIR)
            if not rnd:
                return False
            lst = self._read_m3u()
            if not lst:
                return False
            idle = self._random_file(IDLE_DIR)
            # Insert random clip after the currently playing idle, then return to idle
            newlst: List[str] = [lst[0], str(rnd)]
            if idle:
                newlst.append(str(idle))
            else:
                logger.warning("No idle files available after random")
            self._write_m3u(newlst)
            # Rebuild mpv playlist and keep playing current idle until it ends
            self._rebuild_mpv_playlist(newlst)
            # Disable looping for the event/random playlist
            try:
                self.mpv.command("set_property", "loop-playlist", "no")
            except Exception:
                try:
                    self.mpv.command("set", "loop-playlist", "no")
                except Exception:
                    pass
            self._state["last_random_injected_ts"] = float(time.time())
            return True

    def pause_toggle(self) -> bool:
        """Toggle playback pause/resume.

        Returns the new pause state (``True`` if paused)."""
        with self._lock:
            paused = bool(self.mpv.pause)
            self.mpv.pause = not paused
            self._state["is_paused"] = bool(self.mpv.pause)
            return bool(self._state["is_paused"])

    def skip(self) -> bool:
        """Skip to the next item in the playlist."""
        try:
            self.mpv.command("playlist-next", "force")
            return True
        except Exception:
            return False

    def shutdown_pi(self) -> None:
        """Shutdown the Raspberry Pi immediately."""
        os.system("sudo /sbin/shutdown -h now")

    def reboot_pi(self) -> None:
        """Reboot the Raspberry Pi immediately."""
        os.system("sudo /sbin/reboot")

    def status(self) -> Dict[str, Any]:
        """Return a snapshot of the current playback state and configuration."""
        with self._lock:
            cur = str(self._state.get("current_path", ""))
            category = ""
            if cur:
                if self._state.get("in_random_mode"):
                    category = "random"
                elif cur.startswith(str(IDLE_DIR)):
                    category = "idle"
                else:
                    category = "event"
            return {
                "current_path": cur,
                "current_basename": os.path.basename(cur) if cur else "",
                "current_category": category,
                "is_paused": bool(self._state.get("is_paused", False)),
                "in_random_mode": bool(self._state.get("in_random_mode", False)),
                "last_event_ts": float(self._state.get("last_event_ts", 0.0)),
                "playlist": self._read_m3u(),
                "audio_output_device": str(self.cfg.get("audio_output_device", "")),
                "idle_to_random_seconds": int(
                    self.cfg.get("idle_to_random_seconds", 60)
                ),
                "trigger_source": str(self.cfg.get("trigger_source", "gpio")),
                "gpio": self.cfg.get("gpio", {}),
                "artnet": self.cfg.get("artnet", {}),
                "sacn": self.cfg.get("sacn", {}),
            }

    # ------------------------------------------------------------------
    # Media scanning helpers
    def reload_media(self) -> None:
        """Reload media libraries.

        This stub exists for API compatibility with earlier versions of
        CueBeam.  In a future release this method could rescan the media
        directories and rebuild playlists.  Currently it just reloads
        configuration and clears cached random state.
        """
        with self._lock:
            # Reset event and random timestamps so that the idle monitor
            # will inject random clips after the configured interval.
            self._state["last_event_ts"] = 0.0
            self._state["last_random_injected_ts"] = 0.0
            self.reload_config()

    def ensure_idle_playing(self) -> None:
        """Ensure that idle playback is active.

        If nothing is playing or the current item is not from the idle
        directory, this method will restart playback with a random idle
        clip.
        """
        with self._lock:
            cur = str(self._state.get("current_path", ""))
            if not cur or not cur.startswith(str(IDLE_DIR)):
                self.start()

    def now_playing(self) -> Optional[str]:
        """Return the full path of the currently playing file, if any."""
        with self._lock:
            return str(self._state.get("current_path")) or None

    # ------------------------------------------------------------------
    # Background idle monitor loop
    def _idle_monitor_loop(self) -> None:
        while True:
            time.sleep(1.0)
            try:
                with self._lock:
                    cur = str(self._state.get("current_path", ""))
                    # If nothing is playing, restart idle playback
                    if not cur:
                        try:
                            self.start()
                        except Exception:
                            pass
                        continue
                    # Skip random mode – do not inject additional clips
                    if bool(self._state["in_random_mode"]):
                        continue
                    # Only inject random clips when idle has been playing for
                    # the configured duration without recent events.
                    wait_s = int(self.cfg.get("idle_to_random_seconds", 60))
                    last_event = float(self._state["last_event_ts"])
                    if cur.startswith(str(IDLE_DIR)):
                        if float(time.time()) - last_event >= wait_s:
                            recently = (
                                float(time.time())
                                - float(self._state.get("last_random_injected_ts", 0.0))
                            )
                            if recently >= max(5, wait_s // 2):
                                # Attempt to inject a random clip; ignore result
                                _ = self.trigger_random()
            except Exception as exc:  # noqa: BLE001
                # Log unexpected exceptions in the idle monitor loop
                logger.exception("Error in idle monitor loop: %s", exc)
