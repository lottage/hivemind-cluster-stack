"""
A record of every Courage turn, for debugging ("why did Courage do that?") and, later, metrics and escalation
(plan Phase 6). One JSON line per turn in data/courage_trace.jsonl:

  at, session, user (first 300 chars), path, outcome, ms, llm {calls, ms, tokens}, steps [...], final (300 chars),
  triggers [...]

path     how the turn was handled: reflex | learned | approval_yes | approval_no | loop
outcome  answered | asked_approval | step_cap | llm_error | error | abandoned (client went away mid-turn)
steps    each model call ({"llm": ms, "tokens", "calls": n}) and tool call ({"tool", "args", "ok", "ms", "error"})
triggers the objective escalation signals of the stack-limits review, RECORDED ONLY (nothing acts on them yet):
         tool_error, invalid_args, repeated_call (same tool + arguments twice in a turn), nudged (the model described
         a tool call instead of making it), step_cap, llm_error, empty_answer

The file rotates at 5 MB (one old copy kept). Nothing here leaves LXC 120.
"""

import json
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

MAX_BYTES = 5 * 1024 * 1024
TEXT = 300
ARG_TEXT = 200


def _short(value: Any, limit: int) -> Any:
    s = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return s if len(s) <= limit else s[:limit] + "…"


def _tool_ok(result: str) -> Tuple[bool, Optional[str]]:
    """(ok, error) from a tool's JSON result; text results count as ok."""
    if not isinstance(result, str) or not result.startswith("{"):
        return True, None
    try:
        d = json.loads(result)
    except ValueError:
        return True, None
    if d.get("ok") is False or d.get("error"):
        return False, _short(d.get("error") or "failed", TEXT)
    return True, None


class TurnTrace:
    """Built up by the agent during one turn; `record()` is what gets written."""

    def __init__(self, session: str, user: str, clock: Callable[[], float] = time.time):
        self.clock = clock
        self.t0 = clock()
        self.session, self.user = session, user
        self.path = "loop"
        self.outcome: Optional[str] = None
        self.steps: List[Dict[str, Any]] = []
        self.triggers: List[str] = []
        self.tokens = 0
        self.llm_ms = 0.0
        self.llm_calls = 0
        self.final = ""
        self._seen_calls: set = set()
        self._tool_started: Optional[float] = None

    # ---- what the agent reports ------------------------------------------------
    def trigger(self, name: str) -> None:
        if name not in self.triggers:
            self.triggers.append(name)

    def llm(self, ms: float, tokens: int, calls: int) -> None:
        self.llm_calls += 1
        self.llm_ms += ms
        self.tokens += int(tokens or 0)
        self.steps.append({"llm": round(ms), "tokens": int(tokens or 0), "calls": calls})

    def tool_started(self) -> None:
        self._tool_started = self.clock()

    def tool(self, name: str, args: Dict[str, Any], result: str) -> None:
        ms = (self.clock() - self._tool_started) * 1000 if self._tool_started else None
        self._tool_started = None
        ok, err = _tool_ok(result)
        step = {"tool": name, "args": _short(args, ARG_TEXT), "ok": ok}
        if ms is not None:
            step["ms"] = round(ms)
        if err:
            step["error"] = err
            self.trigger("tool_error")
        self.steps.append(step)
        key = name + json.dumps(args, sort_keys=True, default=str)
        if key in self._seen_calls:
            self.trigger("repeated_call")
        self._seen_calls.add(key)

    def invalid(self, name: str, args: Dict[str, Any], error: str) -> None:
        self.steps.append({"tool": name, "args": _short(args, ARG_TEXT), "ok": False, "error": _short(error, TEXT),
                           "refused": True})
        self.trigger("invalid_args")

    def end(self, outcome: str, final: str = "") -> None:
        if self.outcome is None:              # the first reason wins
            self.outcome = outcome
            self.final = final or ""
            if outcome in ("step_cap", "llm_error"):
                self.trigger(outcome)

    # ---- output ------------------------------------------------------------------
    def record(self) -> Dict[str, Any]:
        return {"at": round(self.t0, 3), "session": self.session, "user": _short(self.user or "", TEXT),
                "path": self.path, "outcome": self.outcome or "error", "ms": round((self.clock() - self.t0) * 1000),
                "llm": {"calls": self.llm_calls, "ms": round(self.llm_ms), "tokens": self.tokens},
                "steps": self.steps, "final": _short(self.final, TEXT), "triggers": self.triggers}


class TraceLog:
    """Append-only JSONL with size rotation; reads for the StoneSage trace view."""

    def __init__(self, path: str, max_bytes: int = MAX_BYTES):
        self.path, self.max_bytes = path, max_bytes
        self._lock = threading.Lock()

    def write(self, rec: Dict[str, Any]) -> None:
        line = json.dumps(rec, ensure_ascii=False, default=str) + "\n"
        with self._lock:
            try:
                if os.path.exists(self.path) and os.path.getsize(self.path) + len(line) > self.max_bytes:
                    os.replace(self.path, self.path + ".1")
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(line)
            except OSError:
                pass  # tracing must never break a turn

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Newest first."""
        out: List[Dict[str, Any]] = []
        for p in (self.path, self.path + ".1"):
            try:
                with open(p, encoding="utf-8") as f:
                    lines = f.readlines()
            except OSError:
                continue
            for ln in reversed(lines):
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    continue
                if len(out) >= limit:
                    return out
        return out

    def summary(self, hours: float = 24, now: Optional[float] = None) -> Dict[str, Any]:
        """Counts over the last `hours`: turns, outcomes, paths, triggers, latency p50/p95, tools used and failing."""
        since = (now or time.time()) - hours * 3600
        recs = [r for r in self.recent(100000) if r.get("at", 0) >= since]
        out: Dict[str, Any] = {"hours": hours, "turns": len(recs), "outcomes": {}, "paths": {}, "triggers": {},
                               "tools": {}, "tool_errors": {}}
        for r in recs:
            out["outcomes"][r.get("outcome")] = out["outcomes"].get(r.get("outcome"), 0) + 1
            out["paths"][r.get("path")] = out["paths"].get(r.get("path"), 0) + 1
            for t in r.get("triggers", []):
                out["triggers"][t] = out["triggers"].get(t, 0) + 1
            for s in r.get("steps", []):
                if "tool" in s:
                    out["tools"][s["tool"]] = out["tools"].get(s["tool"], 0) + 1
                    if not s.get("ok"):
                        out["tool_errors"][s["tool"]] = out["tool_errors"].get(s["tool"], 0) + 1
        ms = sorted(r.get("ms", 0) for r in recs)
        out["ms_p50"] = ms[len(ms) // 2] if ms else None
        out["ms_p95"] = ms[min(len(ms) - 1, int(len(ms) * 0.95))] if ms else None
        return out
