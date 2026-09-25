"""StoneSage watch bridge.

StoneSage publishes events here (POST /events). The Android companion holds a
WebSocket (/ws/watch) and relays frames to the Instinct 2. Replies come back
over the same socket and are forwarded to StoneSage. The watch face can also
poll GET /watch/snapshot as a fallback.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect

from usage import UsageCollector

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
log = logging.getLogger("watch-bridge")


def _env(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        raise SystemExit(f"missing required env var {name}")
    return val


PHONE_TOKEN = _env("BRIDGE_PHONE_TOKEN")      # companion app WebSocket
READ_TOKEN = _env("BRIDGE_READ_TOKEN")        # watch face snapshot poll (read-only)
PUBLISH_TOKEN = _env("BRIDGE_PUBLISH_TOKEN")  # StoneSage publishing events
DB_PATH = os.environ.get("BRIDGE_DB", "/var/lib/watch-bridge/bridge.db")
REPLY_WEBHOOK = os.environ.get("STONESAGE_REPLY_WEBHOOK", "")
USAGE_INTERVAL = int(os.environ.get("USAGE_INTERVAL_S", "300"))

MAX_TEXT, MAX_OPTS, MAX_OPT = 140, 4, 14
DEFAULT_TTL = 900
DESTRUCTIVE_OPTS = ["Deny", "At desk"]
STATE_RANK = {"wait": 0, "err": 1, "run": 2, "done": 3, "idle": 4}
MAX_METRIC_ID = 14


def clip(value: Any, limit: int) -> str:
    s = " ".join(str(value or "").split())
    return s if len(s) <= limit else s[: limit - 3] + "..."


def token_ok(header: str | None, expected: str) -> bool:
    if not header or not header.startswith("Bearer "):
        return False
    return secrets.compare_digest(header[7:], expected)


def require(req: Request, expected: str) -> None:
    if not token_ok(req.headers.get("authorization"), expected):
        raise HTTPException(401, "bad token")


class Store:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS asks(
              id TEXT PRIMARY KEY, body TEXT NOT NULL, created REAL NOT NULL,
              expires REAL NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
              reply INTEGER, answered REAL);
            CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT NOT NULL);
            """
        )
        self.db.commit()

    def kv_get(self, key: str, default: Any = None) -> Any:
        row = self.db.execute("SELECT v FROM kv WHERE k=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def kv_set(self, key: str, value: Any) -> None:
        self.db.execute(
            "INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
            (key, json.dumps(value)),
        )
        self.db.commit()

    def add_ask(self, body: dict, ttl: int) -> None:
        now = time.time()
        self.db.execute(
            "INSERT INTO asks(id, body, created, expires) VALUES(?,?,?,?)",
            (body["id"], json.dumps(body), now, now + ttl),
        )
        self.db.commit()

    def get_ask(self, ask_id: str) -> dict | None:
        row = self.db.execute(
            "SELECT body, state, reply FROM asks WHERE id=?", (ask_id,)
        ).fetchone()
        if not row:
            return None
        return {"body": json.loads(row[0]), "state": row[1], "reply": row[2]}

    def pending(self) -> list[dict]:
        rows = self.db.execute(
            "SELECT body FROM asks WHERE state='pending' AND expires>? ORDER BY created",
            (time.time(),),
        ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def resolve(self, ask_id: str, state: str, reply: int | None = None) -> dict | None:
        cur = self.db.execute(
            "UPDATE asks SET state=?, reply=?, answered=? WHERE id=? AND state='pending'",
            (state, reply, time.time(), ask_id),
        )
        self.db.commit()
        return self.get_ask(ask_id) if cur.rowcount else None

    def expired_ids(self) -> list[str]:
        rows = self.db.execute(
            "SELECT id FROM asks WHERE state='pending' AND expires<=?", (time.time(),)
        ).fetchall()
        return [r[0] for r in rows]

    def prune(self, keep_s: int = 7 * 86400) -> None:
        self.db.execute(
            "DELETE FROM asks WHERE state!='pending' AND created<?", (time.time() - keep_s,)
        )
        self.db.commit()


class Hub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()

    async def send(self, msg: dict, only: WebSocket | None = None) -> None:
        data = json.dumps(msg, separators=(",", ":"))
        targets = [only] if only else list(self.clients)
        for ws in targets:
            try:
                await ws.send_text(data)
            except Exception:
                self.clients.discard(ws)


store = Store(DB_PATH)
hub = Hub()
collector = UsageCollector(store.kv_get, store.kv_set)


def status_payload() -> dict:
    st = store.kv_get("st", {"a": []})
    agents = sorted(st.get("a", []), key=lambda a: STATE_RANK.get(a.get("s"), 9))
    return {"k": "st", "a": agents[:6], "q": len(store.pending())}


async def notify_stonesage(payload: dict) -> None:
    if not REPLY_WEBHOOK:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                REPLY_WEBHOOK,
                json=payload,
                headers={"Authorization": f"Bearer {PUBLISH_TOKEN}"},
            )
    except Exception as exc:  # StoneSage can still poll GET /events/{id}
        log.warning("reply webhook failed: %s", exc)


async def replay(ws: WebSocket) -> None:
    """Send everything a freshly connected (or re-syncing) phone needs."""
    for ask in store.pending():
        await hub.send(ask, only=ws)
    await hub.send(status_payload(), only=ws)
    use = store.kv_get("use")
    if use:
        await hub.send({"k": "use", "m": use}, only=ws)
    cfg = store.kv_get("cfg")
    if cfg:
        await hub.send(cfg, only=ws)


async def handle_reply(msg: dict) -> None:
    ask_id, r = str(msg.get("id", "")), msg.get("r")
    ask = store.get_ask(ask_id)
    if not ask or ask["state"] != "pending":
        await hub.send({"k": "clr", "id": ask_id})
        return
    opts = ask["body"]["o"]
    if isinstance(r, bool) or not isinstance(r, int) or not 0 <= r < len(opts):
        log.warning("invalid reply %s", msg)
        return
    store.resolve(ask_id, "answered", r)
    await hub.send({"k": "clr", "id": ask_id})
    await hub.send(status_payload())
    body = ask["body"]
    await notify_stonesage({
        "id": ask_id, "r": r, "choice": opts[r], "p": body.get("p"),
        "d": bool(body.get("d")), "state": "answered", "via": "watch",
    })


async def expiry_loop() -> None:
    while True:
        changed = False
        for ask_id in store.expired_ids():
            ask = store.resolve(ask_id, "expired")
            if ask:
                changed = True
                await hub.send({"k": "clr", "id": ask_id})
                await notify_stonesage({
                    "id": ask_id, "r": -1, "choice": None, "p": ask["body"].get("p"),
                    "d": bool(ask["body"].get("d")), "state": "expired",
                })
        if changed:
            await hub.send(status_payload())
        store.prune()
        await asyncio.sleep(15)


async def usage_loop() -> None:
    while True:
        try:
            metrics = await collector.collect()
            if metrics:
                cur = store.kv_get("use", {})
                cur.update(metrics)
                store.kv_set("use", cur)
                await hub.send({"k": "use", "m": cur})
        except Exception:
            log.exception("usage collection failed")
        await asyncio.sleep(USAGE_INTERVAL)


@asynccontextmanager
async def lifespan(_: FastAPI):
    tasks = [asyncio.create_task(expiry_loop()), asyncio.create_task(usage_loop())]
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="StoneSage watch bridge", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True, "phones": len(hub.clients), "pending": len(store.pending())}


@app.post("/events")
async def publish(req: Request) -> dict:
    require(req, PUBLISH_TOKEN)
    ev = await req.json()
    if not isinstance(ev, dict):
        raise HTTPException(400, "event must be an object")
    kind = ev.get("k")

    if kind == "ask":
        destructive = bool(ev.get("d"))
        opts = list(DESTRUCTIVE_OPTS) if destructive else [
            clip(o, MAX_OPT) for o in (ev.get("o") or [])
        ][:MAX_OPTS]
        if not opts:
            raise HTTPException(400, "ask needs at least one option")
        ttl = max(30, min(86400, int(ev.get("x") or DEFAULT_TTL)))
        msg = {"k": "ask", "id": secrets.token_hex(3), "t": clip(ev.get("t"), MAX_TEXT),
               "o": opts, "x": ttl}
        if ev.get("p"):
            msg["p"] = clip(ev["p"], 16)
        if destructive:
            msg["d"] = 1
        store.add_ask(msg, ttl)
        await hub.send(msg)
        await hub.send(status_payload())
        return {"id": msg["id"]}

    if kind in ("done", "err"):
        msg = {"k": kind, "id": secrets.token_hex(3), "t": clip(ev.get("t"), MAX_TEXT)}
        if ev.get("p"):
            msg["p"] = clip(ev["p"], 16)
        await hub.send(msg)
        return {"id": msg["id"]}

    if kind == "st":
        agents = []
        for a in (ev.get("a") or [])[:12]:
            item = {
                "p": clip(a.get("p"), 16),
                "s": a.get("s") if a.get("s") in STATE_RANK else "idle",
                "t": clip(a.get("t"), 60),
            }
            if a.get("pr") is not None:
                item["pr"] = max(0, min(100, int(a["pr"])))
            agents.append(item)
        store.kv_set("st", {"a": agents})
        await hub.send(status_payload())
        return {"ok": True}

    if kind == "cfg":
        slots = ev.get("slots")
        if (not isinstance(slots, list) or len(slots) != 5 or
                not all(isinstance(s, int) and 0 <= s <= MAX_METRIC_ID for s in slots)):
            raise HTTPException(400, f"slots must be 5 metric ids 0..{MAX_METRIC_ID}")
        cfg = {"k": "cfg", "slots": slots}
        store.kv_set("cfg", cfg)
        await hub.send(cfg)
        return {"ok": True}

    if kind == "use":  # manual/extra metrics merged into collector output
        cur = store.kv_get("use", {})
        cur.update({k: v for k, v in (ev.get("m") or {}).items()
                    if isinstance(v, (int, float)) and not isinstance(v, bool)})
        store.kv_set("use", cur)
        await hub.send({"k": "use", "m": cur})
        return {"ok": True}

    raise HTTPException(400, f"unknown kind {kind!r}")


@app.get("/events/{ask_id}")
async def ask_state(ask_id: str, req: Request) -> dict:
    require(req, PUBLISH_TOKEN)
    ask = store.get_ask(ask_id)
    if not ask:
        raise HTTPException(404, "unknown id")
    opts = ask["body"]["o"]
    r = ask["reply"]
    return {"id": ask_id, "state": ask["state"], "r": r,
            "choice": opts[r] if r is not None and 0 <= r < len(opts) else None}


@app.post("/events/{ask_id}/resolve")
async def resolve_at_desk(ask_id: str, req: Request) -> dict:
    """StoneSage answered it at the workstation: clear it from the watch."""
    require(req, PUBLISH_TOKEN)
    if not store.resolve(ask_id, "resolved"):
        raise HTTPException(404, "not pending")
    await hub.send({"k": "clr", "id": ask_id})
    await hub.send(status_payload())
    return {"ok": True}


@app.get("/watch/snapshot")
async def snapshot(req: Request) -> dict:
    require(req, READ_TOKEN)
    out: dict[str, Any] = {"st": status_payload(), "use": store.kv_get("use", {})}
    cfg = store.kv_get("cfg")
    if cfg:
        out["cfg"] = cfg
    return out


@app.websocket("/ws/watch")
async def ws_watch(ws: WebSocket) -> None:
    if not token_ok(ws.headers.get("authorization"), PHONE_TOKEN):
        await ws.close(code=4401)
        return
    await ws.accept()
    hub.clients.add(ws)
    log.info("phone connected (%d)", len(hub.clients))
    try:
        await replay(ws)
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(msg, dict):
                continue
            if msg.get("k") == "sync":
                await replay(ws)
            elif "id" in msg and "r" in msg:
                await handle_reply(msg)
    except WebSocketDisconnect:
        pass
    finally:
        hub.clients.discard(ws)
        log.info("phone disconnected (%d)", len(hub.clients))
