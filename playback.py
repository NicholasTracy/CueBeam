import os
import random
import threading
import time
from pathlib import Path
from typing import List, Optional, Dict, Any

import yaml
from apscheduler.schedulers.background import BackgroundScheduler
from mpv import MPV

from bt import ensure_connected

ROOT = Path(__file__).parent.resolve()
MEDIA_DIR = ROOT / "media"
PLAYLISTS_DIR = ROOT / "playlists"
CONFIG_PATH = ROOT / "config" / "config.yaml"

IDLE_DIR = MEDIA_DIR / "idle"
EVENTS_DIR = MEDIA_DIR / "events"
RANDOM_DIR = MEDIA_DIR / "random"
CURRENT_M3U = PLAYLISTS_DIR / "current.m3u"


class PlaybackManager:
    def __init__(self) -> None:
        self._load_config()
        self._lock = threading.RLock()
        self._state: Dict[str, Any] = {
            "last_event_ts": 0.0,
            "last_random_injected_ts": 0.0,
            "in_random_mode": False,
            "current_path": "",
            "is_paused": False,
        }

        self._scheduler = BackgroundScheduler()
        self._scheduler.start()
        self._apply_shutdown_schedule()

        # mpv init + tolerant flag handling
        flags: List[str] = self.cfg.get("mpv_flags", []) or []
        ao = self.cfg.get("audio_output_device") or None
        self.mpv = MPV(ao=ao, ytdl=False)

        for f in flags:
            f = (f or "").strip()
            if not f:
                continue
            key, _, val = f.partition("=")
            key = key.lstrip("-").replace("-", "_")
            try:
                # Prefer mpv command interface
                if val:
                    v = val
                    if v.isdigit():
                        v = int(v)
                    elif v.lower() in ("yes", "true", "on"):
                        v = "yes"
                    elif v.lower() in ("no", "false", "off"):
                        v = "no"
                    self.mpv.command("set", key, v)
                else:
                    self.mpv.command("set", key, "yes")
            except Exception:
                try:
                    if val:
                        self.mpv.set_property(key, val)
                    else:
                        self.mpv.set_property(key, True)
                except Exception:
                    print(f"[WARN] ignoring unknown mpv option: {f}")

        self._install_mpv_hooks()

        PLAYLISTS_DIR.mkdir(parents=True, exist_ok=True)
        for d in (MEDIA_DIR, IDLE_DIR, EVENTS_DIR, RANDOM_DIR):
            d.mkdir(parents=True, exist_ok=True)

        if not CURRENT_M3U.exists():
            CURRENT_M3U.write_text("", encoding="utf-8")

        pref = (self.cfg.get("bluetooth") or {}).get("preferred_mac", "").strip()
        if pref:
            _ = ensure_connected(pref)

        threading.Thread(target=self._idle_monitor_loop, daemon=True).start()

    # config & schedule

    def _load_config(self) -> None:
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
        # Normalize
        self.cfg.setdefault("idle_to_random_seconds", 60)
        self.cfg.setdefault("daily_shutdown_time", "")
        self.cfg.setdefault("mpv_flags", [])
        self.cfg.setdefault("audio_output_device", "")
        self.cfg.setdefault("trigger_source", "gpio")
        self.cfg.setdefault("gpio", {"pin": 17, "pull": "up", "edge": "falling", "debounce_ms": 50})
        self.cfg.setdefault("artnet", {"listen_host": "0.0.0.0", "port": 6454, "universe": 0, "channel": 1, "threshold": 128})
        self.cfg.setdefault("sacn", {"universe": 1, "channel": 1, "threshold": 128})
        self.cfg.setdefault("bluetooth", {"preferred_mac": "", "scan_seconds": 8})
        self.cfg.setdefault("auth", {"enabled": False})

    def reload_config(self) -> None:
        with self._lock:
            self._load_config()
            self._apply_shutdown_schedule()

    def _apply_shutdown_schedule(self) -> None:
        for job in self._scheduler.get_jobs():
            if job.id == "daily_shutdown":
                self._scheduler.remove_job(job.id)

        t = (self.cfg.get("daily_shutdown_time") or "").strip()
        if t:
            hh, mm = [int(x) for x in t.split(":")]
            self._scheduler.add_job(
                self.shutdown_pi, "cron", hour=hh, minute=mm, id="daily_shutdown"
            )

    # mpv hooks (python-mpv 1.0.8 compatible)

    def _install_mpv_hooks(self) -> None:
        try:
            @self.mpv.property_observer("path")
            def _on_path(_name, val) -> None:
                path_str = str(val) if val else ""
                with self._lock:
                    self._state["current_path"] = path_str
                    if path_str.startswith(str(RANDOM_DIR)):
                        self._state["in_random_mode"] = True
                    elif path_str.startswith(str(IDLE_DIR)):
                        self._state["in_random_mode"] = False
        except AttributeError:
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

    # playlist helpers

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
        self.mpv.command("playlist-clear")
        for it in items:
            self.mpv.command("loadfile", it, "append-play")
        if cur and cur in items:
            idx = items.index(cur)
            self.mpv.command("playlist-play-index", str(idx))
        else:
            self.mpv.command("playlist-play-index", "0")

    # public controls

    def start(self) -> None:
        with self._lock:
            idle = self._random_file(IDLE_DIR)
            if not idle:
                print("[WARN] No idle files found in media/idle")
                return
            self._clear_playlist()
            self.mpv.command("loadfile", str(idle), "append-play")
            self._write_m3u([str(idle)])
            self.mpv.pause = False

    def trigger_event(self) -> bool:
        with self._lock:
            self._state["last_event_ts"] = float(time.time())
            if bool(self._state["in_random_mode"]):
                return False
            ev = self._random_file(EVENTS_DIR)
            if not ev:
                return False
            lst = self._read_m3u()
            if not lst:
                return False
            idle = self._random_file(IDLE_DIR)
            newlst: List[str] = [lst[0], str(ev)]
            if idle:
                newlst.append(str(idle))
            self._write_m3u(newlst)
            self._rebuild_mpv_playlist(newlst)
            return True

    def trigger_random(self) -> bool:
        with self._lock:
            rnd = self._random_file(RANDOM_DIR)
            if not rnd:
                return False
            lst = self._read_m3u()
            if not lst:
                return False
            idle = self._random_file(IDLE_DIR)
            newlst: List[str] = [lst[0], str(rnd)]
            if idle:
                newlst.append(str(idle))
            self._write_m3u(newlst)
            self._rebuild_mpv_playlist(newlst)
            self._state["last_random_injected_ts"] = float(time.time())
            return True

    def pause_toggle(self) -> bool:
        with self._lock:
            paused = bool(self.mpv.pause)
            self.mpv.pause = not paused
            self._state["is_paused"] = bool(self.mpv.pause)
            return bool(self._state["is_paused"])

    def skip(self) -> bool:
        try:
            self.mpv.command("playlist-next", "force")
            return True
        except Exception:
            return False

    def shutdown_pi(self) -> None:
        os.system("sudo /sbin/shutdown -h now")

    def reboot_pi(self) -> None:
        os.system("sudo /sbin/reboot")

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "current_path": str(self._state.get("current_path", "")),
                "is_paused": bool(self._state.get("is_paused", False)),
                "in_random_mode": bool(self._state.get("in_random_mode", False)),
                "last_event_ts": float(self._state.get("last_event_ts", 0.0)),
                "playlist": self._read_m3u(),
                "audio_output_device": str(self.cfg.get("audio_output_device", "")),
                "idle_to_random_seconds": int(self.cfg.get("idle_to_random_seconds", 60)),
                "trigger_source": str(self.cfg.get("trigger_source", "gpio")),
                "gpio": self.cfg.get("gpio", {}),
                "artnet": self.cfg.get("artnet", {}),
                "sacn": self.cfg.get("sacn", {}),
            }

    # idle loop

    def _idle_monitor_loop(self) -> None:
        while True:
            time.sleep(1.0)
            try:
                with self._lock:
                    if bool(self._state["in_random_mode"]):
                        continue
                    wait_s = int(self.cfg.get("idle_to_random_seconds", 60))
                    last_event = float(self._state["last_event_ts"])
                    cur = str(self._state["current_path"])
                    if cur and cur.startswith(str(IDLE_DIR)):
                        if float(time.time()) - last_event >= wait_s:
                            recently = float(time.time()) - float(self._state["last_random_injected_ts"])
                            if recently >= max(5, wait_s // 2):
                                _ = self.trigger_random()
            except Exception as exc:
                print(f"[idle loop] {exc}")
