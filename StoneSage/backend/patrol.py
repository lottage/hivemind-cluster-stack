"""
PTZ patrol: the PTZ cameras sweep their whole pan range every so often and report who and what they saw.

Per camera (config.json patrol.cameras, keyed by HA camera entity):
  ptz           HA entity prefix (button.<ptz>_move_left/right, number.<ptz>_movement_angle, select.<ptz>_move_to_preset)
  frames        "frigate:<camera>" (Frigate's latest frame; that camera streams anyway) or "go2rtc:<stream>"
  home_preset   where the camera returns after a sweep
  quiet_when_home  skip sweeps while a resident is home (indoor camera: the motor is audible)
  battery_sensor   battery-gated schedule (solar driveway): see interval_for()

A sweep: pan to the left end stop, step right by step_deg taking a frame each time until the picture stops changing
(right end stop reached) or max_frames, then return home. Each frame is checked by the vision model for known
profiles (for a Frigate camera only when Frigate sees someone, to spare the GPU). Sightings go into Courage's
presence like Frigate's (source "patrol"). A camera John moved by hand in the last few minutes is left alone.
"""

import io
import json
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional

MANUAL_HOLD_S = 300          # a hand-moved camera is not swept for this long
LEFT_END_MOVES = 3           # 3 x 120 deg left: past the end stop of any Tapo pan range


def _key(name: str) -> str:
    """Identity key, same rule as frigate_presence.norm_name: 'Aunt May' -> 'aunt-may'."""
    return re.sub(r"[^a-z0-9-]", "", (name or "").strip().lower().replace(" ", "-").replace("'", ""))


def frames_differ(a: Optional[bytes], b: Optional[bytes], threshold: float = 3.0) -> bool:
    """Mean absolute difference (0-255 scale) of small grayscale thumbnails. After a pan step the view shifts a lot;
    at the end stop the camera does not move and consecutive frames are nearly identical."""
    if not a or not b:
        return True
    try:
        from PIL import Image, ImageChops, ImageStat
        ta = Image.open(io.BytesIO(a)).convert("L").resize((96, 54))
        tb = Image.open(io.BytesIO(b)).convert("L").resize((96, 54))
        return ImageStat.Stat(ImageChops.difference(ta, tb)).mean[0] > threshold
    except Exception:
        return True


def interval_for(cam: Dict[str, Any], base_min: float, battery: Optional[float], daylight: bool,
                 residents_home: List[str]) -> Optional[float]:
    """Minutes until this camera's next sweep, or None to skip it for now (John's rules, 2026-09-25)."""
    if cam.get("quiet_when_home") and residents_home:
        return None                     # indoor motor noise: not while Austin or Savannah is home
    if cam.get("battery_sensor"):
        if battery is None or battery < 30:
            return None                 # unknown or low: let the panel catch up
        if daylight and battery >= 60:
            return base_min
        return 60.0
    return base_min


def residents_home(people: List[str], ha_person_state: Callable[[str], Optional[str]],
                   minutes_since_seen: Dict[str, Optional[float]], seen_window_min: float = 90) -> List[str]:
    """Who counts as home. An HA person entity (phone GPS) is trusted when it has a state; someone without one
    (Savannah has no tracker yet) counts as home if a camera saw them within seen_window_min."""
    home = []
    for name in people:
        state = ha_person_state(name)
        if state in ("home", "not_home") or (state and state not in ("unknown", "unavailable")):
            if state == "home":
                home.append(name)
            continue
        seen = minutes_since_seen.get(name.lower())
        if seen is not None and seen <= seen_window_min:
            home.append(name)
    return home


class Patrol:
    def __init__(self, cfg_fn: Callable[[], Dict[str, Any]], ha: Any, frame_fn: Callable[[str], Optional[bytes]],
                 vision_fn: Callable[[bytes, str, List[str]], Dict[str, Any]],
                 frigate_in_view: Callable[[str], List[Dict[str, Any]]], presence_fn: Callable[[], Dict[str, Any]],
                 clock: Callable[[], float] = time.time, sleep: Callable[[float], None] = time.sleep,
                 state_path: Optional[str] = None):
        self.cfg_fn, self.ha, self.frame_fn, self.vision_fn = cfg_fn, ha, frame_fn, vision_fn
        self.frigate_in_view, self.presence_fn = frigate_in_view, presence_fn
        self.clock, self.sleep = clock, sleep
        self.state_path = state_path
        self.state: Dict[str, Dict[str, Any]] = {}     # entity -> {last, next, frames, skip, busy, interval_s}
        self._load_state()
        self.sightings: Dict[str, Dict[str, Any]] = {} # identity -> newest patrol sighting
        self.frames: Dict[str, List[bytes]] = {}       # entity -> jpegs of the last sweep
        self.manual_at: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

    # -------------------------------------------------------------- config ----
    def _pcfg(self) -> Dict[str, Any]:
        return self.cfg_fn().get("patrol") or {}

    def _load_state(self) -> None:
        """Last sweep times survive a StoneSage restart (otherwise every deploy wakes the solar camera for a sweep)."""
        if not self.state_path:
            return
        try:
            with open(self.state_path, encoding="utf-8") as f:
                for entity, last in (json.load(f) or {}).items():
                    self.state[entity] = {"last": float(last)}
        except (OSError, ValueError):
            pass

    def _save_state(self) -> None:
        if not self.state_path:
            return
        try:
            tmp = self.state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({e: s["last"] for e, s in self.state.items() if s.get("last")}, f)
            import os
            os.replace(tmp, self.state_path)
        except OSError:
            pass

    def note_manual(self, entity: str) -> None:
        """Called by the PTZ route: John is steering this camera, so the patrol keeps out of the way."""
        self.manual_at[entity] = self.clock()

    def _ha_state(self, entity_id: str) -> Optional[str]:
        return (self.ha.get_state(entity_id) or {}).get("state")

    # ------------------------------------------------------------- schedule ----
    def due(self, entity: str, cam: Dict[str, Any]) -> Optional[str]:
        """None if this camera should sweep now, else the reason it waits (shown in the UI)."""
        pcfg = self._pcfg()
        st = self.state.setdefault(entity, {})
        now = self.clock()
        if now - self.manual_at.get(entity, 0) < MANUAL_HOLD_S:
            return "moved by hand recently"
        people = pcfg.get("residents", ["Austin", "Savannah"])
        seen = {n: (v or {}).get("minutes_ago") for n, v in ((self.presence_fn() or {}).get("locations") or {}).items()}
        home = residents_home(people, lambda n: self._ha_state(f"person.{n.lower()}"), seen)
        battery = None
        if cam.get("battery_sensor"):
            try:
                battery = float(self._ha_state(cam["battery_sensor"]))
            except (TypeError, ValueError):
                battery = None
        daylight = self._ha_state("sun.sun") == "above_horizon"
        minutes = interval_for(cam, float(pcfg.get("interval_min", 15)), battery, daylight, home)
        if minutes is None:
            reason = f"paused: {', '.join(home)} home" if cam.get("quiet_when_home") and home else \
                     f"paused: battery {battery if battery is not None else '?'}%"
            st.update(skip=reason, next=None)
            return reason
        nxt = st.get("last", 0) + minutes * 60
        st.update(skip=None, next=nxt, interval_s=minutes * 60)
        return None if now >= nxt else "waiting"

    # ---------------------------------------------------------------- sweep ----
    def sweep(self, entity: str, cam: Dict[str, Any]) -> Dict[str, Any]:
        pcfg = self._pcfg()
        ptz, step, max_frames = cam["ptz"], int(pcfg.get("step_deg", 30)), int(pcfg.get("max_frames", 9))
        settle = float(pcfg.get("settle_s", 3))
        # Steps to skip after the left end stop: there the driveway camera looks straight into the house wall.
        skip = int(cam.get("skip_steps", pcfg.get("skip_steps", 1)))
        profiles = self._profile_names()
        st = self.state.setdefault(entity, {})
        st["busy"] = True
        frames: List[bytes] = []
        seen_log: List[Dict[str, Any]] = []
        try:
            self.ha.call_service("number", "set_value", {"entity_id": f"number.{ptz}_movement_angle", "value": 120})
            for _ in range(LEFT_END_MOVES):
                self.ha.press_button(f"button.{ptz}_move_left")
                self.sleep(settle + 1)
            self.ha.call_service("number", "set_value", {"entity_id": f"number.{ptz}_movement_angle", "value": step})
            for _ in range(skip):
                self.ha.press_button(f"button.{ptz}_move_right")
                self.sleep(settle)
            prev = None
            for i in range(max_frames):
                pan = (i + skip) * step
                self.sleep(settle)
                frame = self.frame_fn(cam["frames"])
                if frame is None:
                    break
                if i > 0 and not frames_differ(prev, frame):
                    break                                    # did not move: right end stop
                frames.append(frame)
                prev = frame
                names = self._look(cam, frame, pan, profiles)
                if names:
                    seen_log.append({"pan": pan, "seen": names})
                    self._record(entity, cam, names, len(frames) - 1, pan)
                if i < max_frames - 1:
                    self.ha.press_button(f"button.{ptz}_move_right")
        finally:
            self.ha.call_service("number", "set_value", {"entity_id": f"number.{ptz}_movement_angle", "value": 15})
            if cam.get("home_preset"):
                self.ha.select_option(f"select.{ptz}_move_to_preset", cam["home_preset"])
            with self._lock:
                self.frames[entity] = frames
            last = self.clock()
            st.update(busy=False, last=last, frames=len(frames), seen=seen_log, first_pan=skip * step, step=step,
                      next=last + st["interval_s"] if st.get("interval_s") else None)
            self._save_state()
        return {"frames": len(frames), "seen": seen_log}

    def _look(self, cam: Dict[str, Any], frame: bytes, pan: int, profiles: List[str]) -> List[str]:
        """Known profiles in this frame. On a Frigate camera the VLM only runs when Frigate is tracking someone."""
        kind, _, name = cam["frames"].partition(":")
        if kind == "frigate":
            try:
                if not self.frigate_in_view(name):
                    return []
            except Exception:
                pass  # Frigate unreachable: look anyway
        res = self.vision_fn(frame, f"{cam.get('name', '')} (pan {pan} deg)", profiles) or {}
        valid = {p.lower(): p for p in profiles}
        return [valid[n.lower()] for n in res.get("seen", []) if isinstance(n, str) and n.lower() in valid]

    def _record(self, entity: str, cam: Dict[str, Any], names: List[str], frame_idx: int, pan: int) -> None:
        now = self.clock()
        with self._lock:
            for n in names:
                self.sightings[_key(n)] = {"seen_at": now, "entity": entity, "camera": cam.get("name", entity),
                                           "frame": frame_idx, "pan": pan}

    # ----------------------------------------------------------- corrections ----
    def correct(self, ref: str, shown: str, action: str, name: str = "") -> Dict[str, Any]:
        """A correction from a Residents & Pets card. ref = '<entity>|<frame>' of the sighting shown as `shown`.
        Reject drops it; relabel re-files it under `name` (newest sighting per identity still wins). Returns the
        frame bytes too, so the caller can teach Frigate's face library when `name` is a person."""
        entity, _, idx = (ref or "").rpartition("|")
        if not entity or not idx.isdigit():
            return {"ok": False, "error": "bad patrol sighting ref"}
        old = _key(shown)
        with self._lock:
            rec = self.sightings.get(old)
            if not rec or rec["entity"] != entity or rec["frame"] != int(idx):
                return {"ok": False, "error": "that sighting has been replaced by a newer sweep"}
            del self.sightings[old]
            if action == "relabel":
                new = _key(name)
                cur = self.sightings.get(new)
                if cur is None or rec["seen_at"] >= cur["seen_at"]:
                    self.sightings[new] = rec
        self._log_correction({"source": "patrol", "entity": entity, "pan": rec["pan"], "shown": shown,
                              "action": action, "name": name or None})
        return {"ok": True, "name": name or None, "frame": self.frame(entity, int(idx))}

    def _log_correction(self, entry: Dict[str, Any]) -> None:
        """Append-only record next to the state file (tuning data for the patrol's vision prompt later)."""
        if not self.state_path:
            return
        import os
        entry["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        try:
            with open(os.path.join(os.path.dirname(self.state_path), "patrol_corrections.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    def _profile_names(self) -> List[str]:
        ents = (self.presence_fn() or {}).get("known_entities") or {}
        return [e["name"] for g in ("people", "pets") for e in ents.get(g, []) if e.get("name")]

    # ---------------------------------------------------------------- output ----
    def locations(self) -> Dict[str, Dict[str, Any]]:
        now = self.clock()
        with self._lock:
            items = list(self.sightings.items())
        return {k: {"minutes_ago": round((now - v["seen_at"]) / 60, 1), "mtime": v["seen_at"], "camera": v["camera"],
                    "doing": f"seen on patrol (pan {v['pan']} deg)", "source": "patrol",
                    "patrol_ref": f"{v['entity']}|{v['frame']}",
                    "snapshot_url": f"/api/patrol/frame?entity={v['entity']}&i={v['frame']}"} for k, v in items}

    def frame(self, entity: str, i: int) -> Optional[bytes]:
        with self._lock:
            frames = self.frames.get(entity) or []
            return frames[i] if 0 <= i < len(frames) else None

    def status(self) -> Dict[str, Any]:
        cams = self._pcfg().get("cameras") or {}
        out = {}
        for entity, cam in cams.items():
            st = self.state.get(entity, {})
            out[entity] = {"name": cam.get("name", entity), "busy": st.get("busy", False), "last": st.get("last"),
                           "next": st.get("next"), "skip": st.get("skip"), "frames": st.get("frames", 0),
                           "seen": st.get("seen", []), "first_pan": st.get("first_pan", 0), "step": st.get("step", 30)}
        return {"enabled": bool(self._pcfg().get("enabled")), "cameras": out}

    # ------------------------------------------------------------------ loop ----
    def run_once(self) -> None:
        pcfg = self._pcfg()
        if not pcfg.get("enabled"):
            return
        for entity, cam in (pcfg.get("cameras") or {}).items():
            if self.due(entity, cam) is None:
                self.sweep(entity, cam)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        def loop():
            while True:
                try:
                    self.run_once()
                except Exception as e:  # never let one bad sweep stop the patrol
                    import logging
                    logging.getLogger("StoneSage.Patrol").warning(f"patrol: {type(e).__name__}: {e}")
                self.sleep(60)

        self._thread = threading.Thread(target=loop, name="ptz-patrol", daemon=True)
        self._thread.start()

    def run_now(self, entity: str) -> Dict[str, Any]:
        """Manual sweep (UI button), in the background; refused while that camera is already sweeping."""
        cam = (self._pcfg().get("cameras") or {}).get(entity)
        if not cam:
            return {"ok": False, "error": "not a patrol camera"}
        if self.state.get(entity, {}).get("busy"):
            return {"ok": False, "error": "already sweeping"}
        self.manual_at.pop(entity, None)
        threading.Thread(target=self.sweep, args=(entity, cam), daemon=True).start()
        return {"ok": True}


def parse_vision_json(text: str) -> Dict[str, Any]:
    """The VLM's reply -> {"seen": [...], "note": str}; tolerant of code fences and chatter around the JSON."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {"seen": [], "note": (text or "")[:200]}
    try:
        d = json.loads(m.group(0))
        return {"seen": [s for s in d.get("seen", []) if isinstance(s, str)], "note": str(d.get("note", ""))[:200]}
    except Exception:
        return {"seen": [], "note": (text or "")[:200]}
