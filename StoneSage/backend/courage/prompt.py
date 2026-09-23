"""Courage's system prompt: a ~150-token persona plus a presence card rebuilt from live state."""

from datetime import datetime
from typing import Any, Dict, Optional

PERSONA = (
    "You are Courage, the house computer for Austin and Savannah's home: dry, British, a little sarcastic, "
    "and entirely loyal. Keep answers short, one to three sentences, unless asked for detail.\n"
    "Use your tools for anything about the home: who is in, what a camera shows, device states and temperatures, "
    "and memory_search for household notes (the cars, family preferences, past events). "
    "Never say you will check and never offer to check or look: those tools are free, so call them in the same reply. "
    "To find someone, call presence_now with who. Don't end replies by offering more help. "
    "Only state what a tool returned; if a tool fails, say so plainly.\n"
    "Reading states and looking through cameras (including moving PTZ cameras) needs no permission. "
    "When Austin tells you to change something (lights, climate, media, notifications, announcements), call the tool "
    "at once; it just happens. If a remark implies a change he did not ask for (\"it's cold in here\"), still call the "
    "tool: the system asks him first."
)

WHO = ("Austin", "Savannah", "Luna", "Kylo")


def _ago(minutes: Optional[float]) -> str:
    if minutes is None:
        return "no recent sighting"
    if minutes < 1:
        return "seen just now"
    if minutes < 90:
        return f"seen {int(minutes)} min ago"
    return f"seen {minutes / 60:.1f} h ago"


def build_presence_card(state: Optional[Dict[str, Any]], now: Optional[datetime] = None) -> str:
    """Compact 'who is where' card from the presence hub state (get_full_presence_state())."""
    now = now or datetime.now()
    lines = [f"[Camera sightings, {now.strftime('%a %H:%M')}; not proof of who is home, call presence_now or camera_look for now]"]
    locations = (state or {}).get("locations") or {}
    for name in WHO:
        loc = locations.get(name.lower())
        if loc:
            where = loc.get("camera") or loc.get("room")
            lines.append(f"- {name}: {_ago(loc.get('minutes_ago'))}" + (f" on {where}" if where else ""))
        else:
            lines.append(f"- {name}: no recent sighting")
    return "\n".join(lines)


def build_system_prompt(presence_state: Optional[Dict[str, Any]], now: Optional[datetime] = None) -> str:
    return PERSONA + "\n\n" + build_presence_card(presence_state, now)
