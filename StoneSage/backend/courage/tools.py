"""
Courage's curated tool set.

Rules (John's decisions, 2026-09-23 plan):
- Reading states and cameras, including PTZ moves, runs freely.
- Other actions (HA service calls, notifications, announcements) run at once when the user ordered them,
  and need approval when Courage inferred them (2026-09-23). Unlock and open-cover always need approval.
- ha_call is limited to an allowlist of domain/service pairs; anything else is refused outright.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .prompt import home_status_text

CAMERAS: Dict[str, Dict[str, str]] = {
    "kitchen_living_room": {"entity": "camera.kitchen_living_room_hd_stream", "name": "Kitchen/Living Room"},
    "driveway_front_door": {"entity": "camera.driveway_front_door_hd_stream_direct", "name": "Driveway/Front Door"},
    "side_yard": {"entity": "camera.side_yard_hd_stream_direct", "name": "Side Yard"},
    "back_yard": {"entity": "camera.back_yard_hd_stream_direct", "name": "Back Yard"},
}

READ_DOMAINS = ["light", "switch", "climate", "sensor", "binary_sensor", "media_player", "lock", "cover", "fan", "person"]

# domain -> services Courage may request (always behind approval)
ALLOWED_SERVICES: Dict[str, List[str]] = {
    "light": ["turn_on", "turn_off", "toggle"],
    "switch": ["turn_on", "turn_off", "toggle"],
    "fan": ["turn_on", "turn_off"],
    "climate": ["set_temperature", "set_hvac_mode"],
    "media_player": ["media_pause", "media_play", "volume_set"],
    "scene": ["turn_on"],
    "cover": ["open_cover", "close_cover"],
    "lock": ["lock", "unlock"],
}

# smart plugs feeding the homelab: never switched off (same list as server.py /api/hass/call)
INFRA_WORDS = ("server", "kp125", "nas", "pve", "bigserv", "router", "unsloth", "ubu")
# Direct commands run at once; these still ask even when ordered outright (security)
ALWAYS_CONFIRM = {("lock", "unlock"), ("cover", "open_cover")}
# words in the user's message that make an action a direct order, per HA service / tool
DIRECT_SERVICE_WORDS: Dict[str, str] = {
    "turn_on": r"\b(turn|switch|put|flip)\b.*\bon\b|\b(on|up)\s*(please|now)?\s*$|\b(light up|start|activate)\b",
    "turn_off": r"\b(turn|switch|shut|put|flip)\b.*\b(off|down)\b|\b(off|kill)\b",
    "toggle": r"\btoggle\b|\b(turn|switch|flip)\b",
    "set_temperature": r"\b(set|raise|lower|bump|turn|make|increase|decrease|drop)\b|\bdegrees?\b|\d",
    "set_hvac_mode": r"\b(set|switch|turn|put)\b",
    "media_pause": r"\b(pause|stop)\b",
    "media_play": r"\b(play|resume|unpause)\b",
    "volume_set": r"\b(volume|louder|quieter|turn (it )?(up|down)|mute)\b",
    "lock": r"\block\b",
    "close_cover": r"\b(close|shut|lower)\b",
}
DIRECT_TOOL_WORDS: Dict[str, str] = {
    "notify": r"\b(send|notify|text|message|ping|push|remind)\b",
    "speak": r"\b(announce|say|tell|broadcast|shout|yell|call out)\b",
}

FILLER_WORDS ={"any", "all", "every", "the", "a", "an", "my", "our", "house", "home", "right", "now", "currently", "on", "off"}

MAX_RESULT_CHARS = 1500
STALE_MINUTES = 10  # presence_now(who) looks through a camera itself when the last sighting is older than this
PEOPLE = ["austin", "savannah", "luna", "kylo"]
MAX_ENTITIES = 25


@dataclass
class CourageDeps:
    """Callables Courage's tools use. Server wires real clients; tests pass fakes."""
    ha_states: Callable[[Optional[str]], Dict[str, Any]]                      # domain -> {"ok", "entities": [...]}
    ha_call: Callable[[str, str, Dict[str, Any]], Dict[str, Any]]            # domain, service, data -> {"ok", ...}
    presence: Callable[[], Dict[str, Any]]                                   # -> presence hub state
    camera_look: Callable[..., Optional[str]]                                # entity, name[, people_only=True] -> description
    camera_scan: Callable[[str, str], Optional[str]]                         # entity, name -> multi-angle report
    memory_search: Callable[[str], List[Dict[str, Any]]] = field(default=lambda q: [])
    notify: Callable[[str, str], Dict[str, Any]] = field(default=lambda msg, target: {"ok": False, "error": "notify not wired"})
    speak: Callable[[str, str], Dict[str, Any]] = field(default=lambda msg, room: {"ok": False, "error": "speak not wired"})


def _schema(props: Dict[str, Any], required: List[str]) -> Dict[str, Any]:
    return {"type": "object", "properties": props, "required": required}


def _clip(obj: Any) -> str:
    text = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, default=str)
    return text if len(text) <= MAX_RESULT_CHARS else text[:MAX_RESULT_CHARS] + " …(truncated)"


class CourageTools:
    def __init__(self, deps: CourageDeps):
        self.deps = deps
        cams = list(CAMERAS)
        self.specs: Dict[str, Dict[str, Any]] = {
            "presence_now": {
                "description": "Where people (Austin, Savannah) and pets (Luna the cat, Kylo the dog) are: last camera sighting, when, "
                               "and what they were doing. Pass `who` to find one of them: if their sighting is stale this also looks "
                               "through the camera right now.",
                "parameters": _schema({"who": {"type": "string", "enum": PEOPLE}}, []),
                "handler": self._presence_now, "approval": False,
                "status": "Checking who's about…",
            },
            "ha_get_states": {
                "description": "Read current Home Assistant states for one domain, optionally filtered by a word in the name (area or device).",
                "parameters": _schema({"domain": {"type": "string", "enum": READ_DOMAINS},
                                       "name_contains": {"type": "string", "description": "only when the user names a room or device, e.g. 'kitchen', 'tv'; omit for 'any'/'all'"}}, ["domain"]),
                "handler": self._ha_get_states, "approval": False,
                "status": "Reading the house…",
            },
            "camera_look": {
                "description": "Look through one camera right now and describe what is visible (people, pets, vehicles, animals).",
                "parameters": _schema({"camera": {"type": "string", "enum": cams}}, ["camera"]),
                "handler": self._camera_look, "approval": False,
                "status": "Looking at the {camera} camera…",
            },
            "camera_scan": {
                "description": "Pan a PTZ camera through its presets and describe each view. Slower (about 20-40 s); use when one look is not enough.",
                "parameters": _schema({"camera": {"type": "string", "enum": ["kitchen_living_room", "driveway_front_door"]}}, ["camera"]),
                "handler": self._camera_scan, "approval": False,
                "status": "Sweeping the {camera} camera…",
            },
            "memory_search": {
                "description": "Search long-term memory and notes for facts about the home, family, devices or past events.",
                "parameters": _schema({"query": {"type": "string"}}, ["query"]),
                "handler": self._memory_search, "approval": False,
                "status": "Rummaging through my notes…",
            },
            "ha_call": {
                "description": "Change a device through Home Assistant (lights, switches, fans, climate, media, scenes, covers, locks). Austin approves it first.",
                "parameters": _schema({"domain": {"type": "string", "enum": sorted(ALLOWED_SERVICES)},
                                       "service": {"type": "string", "description": "e.g. turn_on, turn_off, set_temperature"},
                                       "entity_id": {"type": "string"},
                                       "data": {"type": "object", "description": "extra service data, e.g. {\"temperature\": 70}"}},
                                      ["domain", "service", "entity_id"]),
                "handler": self._ha_call, "approval": True,
                "status": "Asking to {service} {entity_id}…",
            },
            "notify": {
                "description": "Send a push notification to Austin's phone (the only phone registered in Home Assistant). Austin approves it first.",
                "parameters": _schema({"message": {"type": "string"}, "target": {"type": "string", "enum": ["austin"]}}, ["message"]),
                "handler": self._notify, "approval": True,
                "status": "Asking to send a notification…",
            },
            "speak": {
                "description": "Announce a short message out loud on the Echo speakers (kitchen, bathroom or every Echo). Austin approves it first.",
                "parameters": _schema({"message": {"type": "string"}, "room": {"type": "string", "enum": ["kitchen", "bathroom", "everywhere"]}}, ["message"]),
                "handler": self._speak, "approval": True,
                "status": "Asking to make an announcement…",
            },
        }

    # ---- schema / metadata -------------------------------------------------
    def openai_tools(self) -> List[Dict[str, Any]]:
        return [{"type": "function", "function": {"name": n, "description": s["description"], "parameters": s["parameters"]}}
                for n, s in self.specs.items()]

    def needs_approval(self, name: str) -> bool:
        return bool(self.specs.get(name, {}).get("approval"))

    def status_text(self, name: str, args: Dict[str, Any]) -> str:
        tpl = self.specs.get(name, {}).get("status", f"Running {name}…")
        try:
            return tpl.format(**{k: str(v).replace("_", " ") for k, v in args.items()})
        except (KeyError, IndexError):
            return tpl.split("{")[0].strip() or f"Running {name}…"

    def validate(self, name: str, args: Dict[str, Any]) -> Optional[str]:
        """Return an error string if the call must be refused before approval is even asked."""
        if name not in self.specs:
            return f"unknown tool '{name}'"
        if name == "ha_call":
            domain, service, eid = args.get("domain", ""), args.get("service", ""), args.get("entity_id", "")
            if service not in ALLOWED_SERVICES.get(domain, []):
                return f"{domain}.{service} is not on Courage's allowlist"
            if not eid.startswith(f"{domain}."):
                return f"entity '{eid}' is not a {domain} entity"
            if domain == "switch" and service in ("turn_off", "toggle") and any(w in eid.lower() for w in INFRA_WORDS):
                return f"refused: {eid} powers server infrastructure (would take me down with it)"
            entity, candidates = self.resolve_entity(domain, eid)
            if entity is None and candidates is not None:
                hint = f" Closest: {', '.join(candidates)}." if candidates else f" Call ha_get_states for {domain} to find it."
                return f"no entity '{eid}' in Home Assistant.{hint}"
        if name in ("camera_look", "camera_scan") and args.get("camera") not in CAMERAS:
            return f"unknown camera '{args.get('camera')}'"
        return None

    def resolve_entity(self, domain: str, entity_id: str):
        """(entity, None) if it exists; (None, [close ids]) if not; (None, None) if HA can't be read (don't block)."""
        try:
            res = self.deps.ha_states(domain) or {}
        except Exception:
            return None, None
        if not res.get("ok", True):
            return None, None
        ents = res.get("entities") or []
        for e in ents:
            if e.get("entity_id") == entity_id:
                return e, None
        words = [w for w in entity_id.split(".", 1)[-1].split("_") if len(w) > 2]
        close = [e["entity_id"] for e in ents
                 if any(w in f"{e.get('entity_id', '')} {e.get('friendly_name', '')}".lower() for w in words)]
        return None, close[:6]

    def describe_action(self, name: str, args: Dict[str, Any]) -> str:
        if name == "ha_call":
            entity, _ = self.resolve_entity(args.get("domain", ""), args.get("entity_id", ""))
            label = (entity or {}).get("friendly_name") or args.get("entity_id")
            data = args.get("data") or {}
            if args.get("service") == "set_temperature" and "temperature" in data:
                now = (entity or {}).get("current_temperature") or ((entity or {}).get("attributes") or {}).get("current_temperature")
                return f"set the {label} to {data['temperature']}°" + (f" (it's {now}° now)" if now is not None else "")
            if args.get("service") == "set_hvac_mode" and data.get("hvac_mode"):
                return f"switch the {label} to {data['hvac_mode']}"
            extra = f" ({', '.join(f'{k} {v}' for k, v in args['data'].items())})" if args.get("data") else ""
            return f"{args.get('service', '').replace('_', ' ')} the {label}{extra}"
        if name == "notify":
            return f"notify {args.get('target', 'austin')}: \"{args.get('message', '')}\""
        if name == "speak":
            return f"announce in {args.get('room', 'kitchen')}: \"{args.get('message', '')}\""
        return f"{name}({json.dumps(args)})"

    def is_direct_command(self, name: str, args: Dict[str, Any], user_text: str) -> bool:
        """True when the user's own message ordered this action, so it runs without asking.

        Courage only asks when it inferred the action ("it's cold in here" -> raise the heat?).
        Unlocking doors and opening covers (garage) always ask.
        """
        text = (user_text or "").lower()
        if name == "ha_call":
            service = args.get("service", "")
            if (args.get("domain"), service) in ALWAYS_CONFIRM:
                return False
            pattern = DIRECT_SERVICE_WORDS.get(service)
            return bool(pattern and re.search(pattern, text))
        pattern = DIRECT_TOOL_WORDS.get(name)
        return bool(pattern and re.search(pattern, text))

    def execute(self, name: str, args: Dict[str, Any]) -> str:
        """Run a tool (approval must already be settled by the caller). Returns a clipped string for the model."""
        err = self.validate(name, args)
        if err:
            return _clip({"ok": False, "error": err})
        try:
            return _clip(self.specs[name]["handler"](**args))
        except TypeError as e:
            return _clip({"ok": False, "error": f"bad arguments: {e}"})
        except Exception as e:  # a tool failure must never kill the loop
            return _clip({"ok": False, "error": f"{type(e).__name__}: {e}"})

    # ---- handlers ------------------------------------------------------------
    @staticmethod
    def _camera_key(label: Optional[str]) -> str:
        """Sentry location label ('Kitchen/Living', 'Driveway/Front Door') -> CAMERAS key; indoor cam by default."""
        first = (label or "").lower().split("/")[0].split()[0] if (label or "").strip() else ""
        return next((k for k in CAMERAS if first and k.startswith(first)), "kitchen_living_room")

    def _presence_now(self, who: str = "") -> Dict[str, Any]:
        state = self.deps.presence() or {}
        locs = state.get("locations") or {}
        seen = {name: {"minutes_ago": v.get("minutes_ago"), "camera": v.get("camera"), "doing": v.get("doing")}
                for name, v in locs.items()}
        home = {n: t for n, t in ((n, home_status_text(hs)) for n, hs in (state.get("home_status") or {}).items()) if t}
        who = (who or "").lower().strip()
        if not who:
            return {"ok": True, "gps": home, "last_seen": seen,
                    "note": "gps = phone/Life360 home status (trust it for home or away); last_seen = past camera views."}
        loc = seen.get(who)
        out: Dict[str, Any] = {"ok": True, "who": who, "last_seen": loc or "no recent camera sighting"}
        if who in home:
            out["gps"] = home[who]
        away = (state.get("home_status") or {}).get(who, {}).get("state") not in (None, "home", "unknown", "unavailable")
        if away:
            out["note"] = "GPS says they are not home, so I did not look through the cameras."
        elif loc is None or (loc.get("minutes_ago") or 0) > STALE_MINUTES:
            cam = CAMERAS[self._camera_key(loc and loc.get("camera"))]
            out["looked_now"] = {"camera": cam["name"],
                                 "sees": self.deps.camera_look(cam["entity"], cam["name"], people_only=True)
                                 or "camera snapshot or vision failed"}
            out["note"] = ("The sighting was stale, so I looked just now. If they are not in this view, say where they "
                           "were last seen and that you can't see them now.")
        return out

    def _ha_get_states(self, domain: str, name_contains: str = "") -> Dict[str, Any]:
        res = self.deps.ha_states(domain) or {}
        if not res.get("ok", True):
            return {"ok": False, "error": res.get("error", "Home Assistant unavailable")}
        words = [w for w in (name_contains or "").lower().replace("_", " ").split()
                 if w not in FILLER_WORDS and w.rstrip("s") != domain]
        rows = []
        for e in res.get("entities", []):
            name = e.get("friendly_name") or e.get("entity_id")
            row = {"entity_id": e.get("entity_id"), "name": name, "state": e.get("state")}
            attrs = e.get("attributes") or {}
            for key in ("current_temperature", "temperature", "hvac_action", "brightness", "unit_of_measurement"):
                if key in attrs:
                    row[key] = attrs[key]
            rows.append(row)
        out: Dict[str, Any] = {"ok": True}
        if words:
            hits = [r for r in rows if any(w in f"{r['name']} {r['entity_id']}".lower() for w in words)]
            if hits:
                rows = hits
            else:  # a filter that matches nothing must not read as "nothing is on"
                out["note"] = f"no {domain} names matched '{name_contains}'; showing all {domain} entities"
        out.update(count=len(rows), entities=rows[:MAX_ENTITIES])
        return out

    def _camera_look(self, camera: str) -> Dict[str, Any]:
        cam = CAMERAS[camera]
        desc = self.deps.camera_look(cam["entity"], cam["name"])
        return {"ok": bool(desc), "camera": cam["name"], "description": desc or "camera snapshot or vision failed"}

    def _camera_scan(self, camera: str) -> Dict[str, Any]:
        cam = CAMERAS[camera]
        report = self.deps.camera_scan(cam["entity"], cam["name"])
        return {"ok": bool(report), "camera": cam["name"], "report": report or "scan failed"}

    def _memory_search(self, query: str) -> Dict[str, Any]:
        hits = self.deps.memory_search(query) or []
        return {"ok": True, "results": [str(h.get("text") or h.get("atom") or h)[:300] for h in hits[:5]]}

    def _ha_call(self, domain: str, service: str, entity_id: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = dict(data or {})
        payload["entity_id"] = entity_id
        res = self.deps.ha_call(domain, service, payload) or {}
        return {"ok": bool(res.get("ok")), "done": f"{domain}.{service} {entity_id}", "error": res.get("error")}

    def _notify(self, message: str, target: str = "austin") -> Dict[str, Any]:
        return self.deps.notify(message, target)

    def _speak(self, message: str, room: str = "kitchen") -> Dict[str, Any]:
        return self.deps.speak(message, room)
