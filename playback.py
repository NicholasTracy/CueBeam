import os, random, threading, time, yaml
from pathlib import Path
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from mpv import MPV
from bt import ensure_connected
ROOT=Path(__file__).parent.resolve(); MEDIA_DIR=ROOT/'media'; PLAYLISTS_DIR=ROOT/'playlists'; CONFIG_PATH=ROOT/'config'/'config.yaml'
IDLE_DIR=MEDIA_DIR/'idle'; EVENTS_DIR=MEDIA_DIR/'events'; RANDOM_DIR=MEDIA_DIR/'random'; CURRENT_M3U=PLAYLISTS_DIR/'current.m3u'
class PlaybackManager:
    def __init__(self):
        self._load_config(); self._lock=threading.RLock(); self._state={'last_event_ts':0.0,'last_random_injected_ts':0.0,'in_random_mode':False,'current_path':'','is_paused':False}
        self._scheduler=BackgroundScheduler(); self._scheduler.start(); self._apply_shutdown_schedule()
        flags=self.cfg.get('mpv_flags',[]); ao=self.cfg.get('audio_output_device') or None; self.mpv=MPV(ao=ao, ytdl=False)
        for f in flags:
            key,eq,val=f.partition('=');
            if val: self.mpv.set_property(key.lstrip('-'), val)
        self._install_mpv_hooks()
        PLAYLISTS_DIR.mkdir(parents=True, exist_ok=True)
        for d in (MEDIA_DIR, IDLE_DIR, EVENTS_DIR, RANDOM_DIR): d.mkdir(parents=True, exist_ok=True)
        if not CURRENT_M3U.exists(): CURRENT_M3U.write_text('', encoding='utf-8')
        pref=(self.cfg.get('bluetooth') or {}).get('preferred_mac','').strip()
        if pref: _=ensure_connected(pref)
        threading.Thread(target=self._idle_monitor_loop, daemon=True).start()
    def _load_config(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not CONFIG_PATH.exists(): CONFIG_PATH.write_text('idle_to_random_seconds: 60\ndaily_shutdown_time: ""\nmpv_flags: []\naudio_output_device: ""\n', encoding='utf-8')
        self.cfg=yaml.safe_load(CONFIG_PATH.read_text(encoding='utf-8')) or {}
    def reload_config(self):
        with self._lock:
            self._load_config(); self._apply_shutdown_schedule()
    def _apply_shutdown_schedule(self):
        for job in self._scheduler.get_jobs():
            if job.id=='daily_shutdown': self._scheduler.remove_job(job.id)
        t=(self.cfg.get('daily_shutdown_time') or '').strip()
        if t:
            hh,mm=[int(x) for x in t.split(':')]
            self._scheduler.add_job(self.shutdown_pi, 'cron', hour=hh, minute=mm, id='daily_shutdown')
    def _install_mpv_hooks(self):
        @self.mpv.on_event('end-file')
        def _on_end(evt):
            with self._lock:
                self._state['current_path']=''
                lst=self._read_m3u()
                if len(lst)>=2 and str(lst[1]).startswith(str(IDLE_DIR)): self._state['in_random_mode']=False
        @self.mpv.property_observer('path')
        def _on_path(_n, val):
            with self._lock:
                self._state['current_path']=val or ''
                if val and str(val).startswith(str(RANDOM_DIR)): self._state['in_random_mode']=True
    def _write_m3u(self, items): CURRENT_M3U.write_text('\n'.join(items)+('\n' if items else ''), encoding='utf-8')
    def _read_m3u(self): return [l.strip() for l in CURRENT_M3U.read_text(encoding='utf-8').splitlines() if l.strip()] if CURRENT_M3U.exists() else []
    def _clear_playlist(self):
        try: self.mpv.command('playlist-clear')
        except Exception: pass
        self._write_m3u([])
    def _random_file(self, folder: Path) -> Optional[Path]:
        vids=[p for p in folder.iterdir() if p.is_file()];
        return random.choice(vids) if vids else None
    def start(self):
        with self._lock:
            idle=self._random_file(IDLE_DIR)
            if not idle: print('[WARN] No idle files found in media/idle'); return
            self._clear_playlist(); self.mpv.command('loadfile', str(idle), 'append-play'); self._write_m3u([str(idle)]); self.mpv.pause=False
    def _rebuild_mpv_playlist(self, items):
        self.mpv.command('playlist-clear')
        for it in items: self.mpv.command('loadfile', it, 'append-play')
        self.mpv.command('playlist-play-index', '0')
    def trigger_event(self):
        with self._lock:
            self._state['last_event_ts']=time.time()
            if self._state['in_random_mode']: return False
            ev=self._random_file(EVENTS_DIR)
            if not ev: return False
            lst=self._read_m3u()
            if not lst: return False
            idle=self._random_file(IDLE_DIR)
            newlst=[lst[0], str(ev)] + ([str(idle)] if idle else [])
            self._write_m3u(newlst); self._rebuild_mpv_playlist(newlst); return True
    def trigger_random(self):
        with self._lock:
            rnd=self._random_file(RANDOM_DIR)
            if not rnd: return False
            lst=self._read_m3u()
            if not lst: return False
            idle=self._random_file(IDLE_DIR)
            newlst=[lst[0], str(rnd)] + ([str(idle)] if idle else [])
            self._write_m3u(newlst); self._rebuild_mpv_playlist(newlst); self._state['last_random_injected_ts']=time.time(); return True
    def pause_toggle(self):
        with self._lock:
            self.mpv.pause=not bool(self.mpv.pause); self._state['is_paused']=bool(self.mpv.pause); return self._state['is_paused']
    def skip(self):
        try: self.mpv.command('playlist-next', 'force'); return True
        except Exception: return False
    def shutdown_pi(self): os.system('sudo /sbin/shutdown -h now')
    def reboot_pi(self): os.system('sudo /sbin/reboot')
    def status(self)->dict:
        with self._lock:
            return {'current_path':self._state['current_path'],'is_paused':self._state['is_paused'],'in_random_mode':self._state['in_random_mode'],'last_event_ts':self._state['last_event_ts'],'playlist':self._read_m3u(),'audio_output_device':self.cfg.get('audio_output_device',''),'idle_to_random_seconds':int(self.cfg.get('idle_to_random_seconds',60)),'trigger_source':(self.cfg.get('trigger_source') or 'gpio'),'gpio':self.cfg.get('gpio',{}),'artnet':self.cfg.get('artnet',{}),'sacn':self.cfg.get('sacn',{})}
    def _idle_monitor_loop(self):
        while True:
            time.sleep(1)
            try:
                with self._lock:
                    if self._state['in_random_mode']: continue
                    wait_s=int(self.cfg.get('idle_to_random_seconds',60))
                    last_event=self._state['last_event_ts']; cur=self._state['current_path']
                    if cur and cur.startswith(str(IDLE_DIR)) and (time.time()-last_event)>=wait_s:
                        if time.time()-self._state['last_random_injected_ts']>=max(5, wait_s//2): self.trigger_random()
            except Exception as e:
                print(f"[idle loop] {e}")
