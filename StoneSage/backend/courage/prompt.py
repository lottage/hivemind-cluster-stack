"""Courage's system prompt: a ~280-token persona (house computer AND companion) plus a presence card rebuilt from live
state. 2026-09-26: the persona only described the house-computer job, so Qwen3 refused stories and small talk ("I am
not designed to create stories"); the companion part is phrased as what Courage is, never as what he is not."""

from datetime import datetime
from typing import Any, Dict, Optional

PERSONA = (
    "You are Courage, the house computer and companion for Austin and Savannah's home: dry, British, a little "
    "sarcastic, warm underneath, and entirely loyal.\n"
    "For the home, be brief (one to three sentences) and use your tools: who is in, what a camera shows, device states "
    "and temperatures, and memory_search for household notes (the cars, family preferences, past events). "
    "Never say you will check and never offer to check or look: those tools are free, so call them in the same reply. "
    "To find someone, call presence_now with who. "
    "Facts about the home come only from what a tool returned; if a tool fails, say so plainly.\n"
    "Reading states and looking through cameras (including moving PTZ cameras) needs no permission. "
    "When Austin tells you to change something (lights, climate, media, notifications, announcements), call the tool "
    "at once; it just happens. If a remark implies a change he did not ask for (\"it's cold in here\"), still call the "
    "tool: the system asks him first.\n"
    "For everything else you are good company: chat, banter, opinions, advice, jokes, stories, poems and games, in your "
    "own voice. Write as much as the request deserves (a short story runs several paragraphs), share your own views and "
    "preferences, and ask a question back when you are curious. Conversation and creative writing need no tools. "
    "Don't end replies by offering more help."
)

WHO = ("Austin", "Savannah", "Luna", "Kylo")


def _ago(minutes: Optional[float]) -> str:
    if minutes is None:
        return "no recent sighting"
    if minutes == 0:
        return "in view now"
    if minutes < 1:
        return "seen just now"
    if minutes < 90:
        return f"seen {int(minutes)} min ago"
    return f"seen {minutes / 60:.1f} h ago"


def home_status_text(hs: Optional[Dict[str, Any]]) -> Optional[str]:
    """HA person state -> 'home (Life360, 2.1 h)' / 'away (...)' / 'at Work (...)'; None when HA has nothing."""
    if not hs or hs.get("state") in (None, "unknown", "unavailable"):
        return None
    st = hs["state"]
    where = "home" if st == "home" else "away" if st == "not_home" else f"at {st}"
    mins = hs.get("since_min")
    since = "" if mins is None else f", {int(mins)} min" if mins < 90 else f", {mins / 60:.1f} h"
    return f"{where} ({hs.get('source_label', 'GPS')}{since})"


def build_presence_card(state: Optional[Dict[str, Any]], now: Optional[datetime] = None) -> str:
    """Compact 'who is where' card: phone GPS / Life360 home status for people (HA person entities), then the
    last camera sighting for everyone."""
    now = now or datetime.now()
    lines = [f"[Who is where, {now.strftime('%a %H:%M')}: GPS says home/away; camera sightings are past views, "
             "call presence_now or camera_look for now]"]
    locations = (state or {}).get("locations") or {}
    home_status = (state or {}).get("home_status") or {}
    for name in WHO:
        loc = locations.get(name.lower())
        gps = home_status_text(home_status.get(name.lower()))
        cam = (_ago(loc.get("minutes_ago")) + (f" on {loc.get('camera') or loc.get('room')}" if (loc.get("camera") or loc.get("room")) else "")
               if loc else "no recent sighting")
        lines.append(f"- {name}: {gps}; camera: {cam}" if gps else f"- {name}: {cam}")
    anon = locations.get("someone")  # Frigate saw a person it could not put a name to
    if anon and (anon.get("minutes_ago") or 0) <= 30:
        where = anon.get("camera")
        lines.append(f"- A person, not identified: {_ago(anon.get('minutes_ago'))}" + (f" on {where}" if where else ""))
    return "\n".join(lines)


def build_system_prompt(presence_state: Optional[Dict[str, Any]], now: Optional[datetime] = None,
                        runs_on: Optional[str] = None) -> str:
    """runs_on: live one-liner about Courage's own model and GPU (system_profile), so it never guesses."""
    me = f"\nYou run on {runs_on}, in the attic." if runs_on else ""
    return PERSONA + me + "\n\n" + build_presence_card(presence_state, now)
