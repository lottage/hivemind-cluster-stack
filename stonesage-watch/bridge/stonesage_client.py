"""Drop-in helper for StoneSage to talk to the watch bridge.

    from stonesage_client import WatchBridge
    wb = WatchBridge()                       # reads WATCH_BRIDGE_URL / BRIDGE_PUBLISH_TOKEN
    ask_id = wb.ask("Deploy build to prod?", ["Approve", "Deny", "Later"], project="easydash")
    result = wb.wait(ask_id, timeout=900)    # {"state": "answered", "r": 0, "choice": "Approve"}
    wb.status([{"p": "stonesage", "s": "run", "t": "refactor usage.py", "pr": 42}])
    wb.notify("Tests green", kind="done", project="easydash")
    wb.layout([1, 8, 2, 6, 7])               # watch face upper-half slots
"""
from __future__ import annotations

import os
import time

import httpx


class WatchBridge:
    def __init__(self, base_url: str | None = None, token: str | None = None,
                 timeout: float = 10):
        self.base = (base_url or os.environ.get("WATCH_BRIDGE_URL",
                                                "http://127.0.0.1:8890")).rstrip("/")
        tok = token or os.environ["BRIDGE_PUBLISH_TOKEN"]
        self.client = httpx.Client(timeout=timeout,
                                   headers={"Authorization": f"Bearer {tok}"})

    def _post(self, path: str, body: dict | None = None) -> dict:
        resp = self.client.post(self.base + path, json=body or {})
        resp.raise_for_status()
        return resp.json()

    def ask(self, text: str, options: list[str], project: str | None = None,
            ttl: int = 900, destructive: bool = False) -> str:
        """Destructive asks are forced to ["Deny", "At desk"] by the bridge."""
        body = {"k": "ask", "t": text, "o": options, "x": ttl, "d": destructive}
        if project:
            body["p"] = project
        return self._post("/events", body)["id"]

    def wait(self, ask_id: str, timeout: float | None = None, poll: float = 2.0) -> dict:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            resp = self.client.get(f"{self.base}/events/{ask_id}")
            resp.raise_for_status()
            state = resp.json()
            if state["state"] != "pending":
                return state
            if deadline and time.monotonic() > deadline:
                return state
            time.sleep(poll)

    def resolve(self, ask_id: str) -> None:
        """Mark an ask handled at the workstation so the watch clears it."""
        self._post(f"/events/{ask_id}/resolve")

    def notify(self, text: str, kind: str = "done", project: str | None = None) -> str:
        body = {"k": kind, "t": text}
        if project:
            body["p"] = project
        return self._post("/events", body)["id"]

    def status(self, agents: list[dict]) -> None:
        """agents: [{"p": name, "s": wait|err|run|done|idle, "t": text, "pr": 0-100}]"""
        self._post("/events", {"k": "st", "a": agents})

    def layout(self, slots: list[int]) -> None:
        """Set the 5 upper-half watch face slots (metric IDs, see PROTOCOL.md)."""
        self._post("/events", {"k": "cfg", "slots": slots})

    def metrics(self, **values: float) -> None:
        self._post("/events", {"k": "use", "m": values})
