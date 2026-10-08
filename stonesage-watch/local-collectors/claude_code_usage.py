"""Sums today's Claude Code token usage from local session transcripts and posts
it to the watch bridge. Runs on the workstation (where ~/.claude/projects lives),
not on the bridge host -- see bridge/usage.py's module docstring for why.

Intended to run on a schedule (e.g. every 5 min via Windows Task Scheduler):
    python claude_code_usage.py

Env:
    CLAUDE_PROJECTS_DIR   default: ~/.claude/projects
    LOCAL_TZ              default: America/New_York (day boundary for "today")
    WATCH_BRIDGE_URL       )
    BRIDGE_PUBLISH_TOKEN   ) read by stonesage_client.WatchBridge
"""
from __future__ import annotations

import json
import os
import sys
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bridge"))
from stonesage_client import WatchBridge  # noqa: E402

PROJECTS_DIR = Path(os.environ.get("CLAUDE_PROJECTS_DIR", str(Path.home() / ".claude" / "projects")))
TZ = ZoneInfo(os.environ.get("LOCAL_TZ", "America/New_York"))


def todays_usage() -> tuple[int, dict[str, int]]:
    """Returns (fresh tokens today, {model: tokens}) from every project's transcripts.

    "Fresh" = input + output tokens only, excluding cache reads/writes. Claude Code
    writes one JSONL line per content block in a response (text, each tool_use, ...),
    all sharing the same message.id and the same (whole-message) usage -- so lines
    must be deduped by message.id or usage gets counted once per block, not once
    per message. Cache reads are excluded here because prompt caching means the
    same context gets re-read (at a steep discount) on nearly every turn of a long
    session; including it at face value inflates the total by 100-400x into a
    number that's neither a real cost figure nor legible on a watch face.
    """
    today = dt.datetime.now(TZ).date()
    total = 0
    by_model: dict[str, int] = {}
    seen_message_ids: set[str] = set()

    for jsonl_path in PROJECTS_DIR.glob("*/*.jsonl"):
        try:
            # Cheap pre-filter: a file untouched since before today can't hold
            # today's messages, and these transcripts can run into the tens of MB.
            mtime = dt.datetime.fromtimestamp(jsonl_path.stat().st_mtime, TZ)
            if mtime.date() < today:
                continue
        except OSError:
            continue

        try:
            with jsonl_path.open(encoding="utf-8") as fh:
                for line in fh:
                    tokens, model, message_id = _line_tokens(line, today)
                    if not tokens or message_id in seen_message_ids:
                        continue
                    seen_message_ids.add(message_id)
                    total += tokens
                    by_model[model] = by_model.get(model, 0) + tokens
        except OSError:
            continue

    return total, by_model


def _line_tokens(line: str, today: dt.date) -> tuple[int, str, str]:
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        return 0, "", ""
    if entry.get("type") != "assistant":
        return 0, "", ""
    message = entry.get("message")
    if not isinstance(message, dict):
        return 0, "", ""
    usage = message.get("usage")
    message_id = message.get("id")
    if not isinstance(usage, dict) or not message_id:
        return 0, "", ""
    ts = entry.get("timestamp")
    if not ts:
        return 0, "", ""
    try:
        when = dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(TZ)
    except ValueError:
        return 0, "", ""
    if when.date() != today:
        return 0, "", ""

    tokens = int(usage.get("input_tokens") or 0) + int(usage.get("output_tokens") or 0)
    return tokens, str(message.get("model") or "unknown"), message_id


def main() -> None:
    total, by_model = todays_usage()
    wb = WatchBridge()
    wb.metrics(tok=total)
    print(f"posted tok={total} today: {by_model}")


if __name__ == "__main__":
    main()
