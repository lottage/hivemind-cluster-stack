"""
Reflex: plain on/off orders ("turn off the tv lights", "string lights on") skip the LLM.

Deterministic and conservative: it fires only when the sentence is a bare on/off order and the name
matches exactly one light, lamp, plug or fan. Anything else (questions, remarks, ambiguous names,
camera and config switches, server plugs) returns None and Courage's tool loop handles it.
Replaces the old harness System-1 path, whose prototypes named entities that don't exist and whose
vector match could not tell "turn on" from "turn off".
"""

import re
from typing import Any, Callable, Dict, List, Optional

ORDER_FIRST = re.compile(r"^(?:please\s+)?(?:(?:can|could|would) you\s+)?(?:turn|switch|flip)\s+(on|off)\s+(.+?)"
                         r"(?:\s+please)?\s*[.!?]?$")
NAME_FIRST = re.compile(r"^(?:please\s+)?(?:(?:can|could|would) you\s+)?(?:(?:turn|switch|flip)\s+)?(.+?)\s+(on|off)"
                        r"(?:\s+please)?\s*[.!?]?$")
COMPOUND = re.compile(r"\b(and|then|in|for|after|until|at|when|if|unless)\b|\d")
QUESTION_START =re.compile(r"^(is|are|was|were|do|does|did|what|which|who|where|when|why|how)\b")
# switches that are devices you'd switch by voice, not camera or firmware settings
SWITCH_DEVICE = re.compile(r"\b(lights?|lamps?|plugs?|fans?)\b")
SWITCH_SETTING = re.compile(r"\b(led|enabled|detection|alarm|privacy|auto|update|record|sync|lens|indicator|weight|mode)\b")
DROP = {"the", "my", "our", "a", "please"}


def _words(text: str) -> List[str]:
    words = [w for w in re.sub(r"[^a-z0-9]+", " ", text.lower()).split() if w not in DROP]
    return [w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words]  # "lights" == "light"


def parse(text: str) -> Optional[Dict[str, str]]:
    """'turn off the tv lights' -> {'state': 'off', 'name': 'tv lights'}; None if not a bare on/off order."""
    t = re.sub(r"\s+", " ", (text or "").strip().lower())
    if not t or QUESTION_START.match(t) or len(t) > 60:
        return None
    m = ORDER_FIRST.match(t)
    order = {"state": m.group(1), "name": m.group(2)} if m else None
    if not order:
        m = NAME_FIRST.match(t)
        order = {"state": m.group(2), "name": m.group(1)} if m else None
    # timers, conditions and compound orders ("... in ten minutes and lock up") are the LLM's job
    if order and (len(order["name"].split()) > 5 or COMPOUND.search(order["name"])):
        return None
    return order


def candidates(ha_states: Callable[[str], Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for domain in ("light", "switch", "fan"):
        try:
            res = ha_states(domain) or {}
        except Exception:
            continue
        for e in res.get("entities") or []:
            name = (e.get("friendly_name") or "").lower()
            if domain == "switch" and (not SWITCH_DEVICE.search(name) or SWITCH_SETTING.search(name)):
                continue
            out.append(dict(e, domain=domain))
    return out


def match(order: Dict[str, str], ents: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The one entity whose name contains every word the user said, or None (no match or ambiguous)."""
    want = set(_words(order["name"]))
    if not want:
        return None
    exact = [e for e in ents if set(_words(e.get("friendly_name") or "")) == want]
    if len(exact) == 1:
        return exact[0]
    # entity ids carry names too: "String Lights" is switch.front_porch_..._lights, so "porch lights" finds it
    hits = [e for e in ents if want <= set(_words(f"{e.get('friendly_name') or ''} {e['entity_id'].split('.', 1)[-1]}"))]
    return hits[0] if len(hits) == 1 else None
