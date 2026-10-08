"""Phase 1 checklist (see ../CLAUDE.md): auth, ask/reply flow, destructive rewrite,
cfg validation, st sorting, snapshot shape, replay on sync, and ask expiry.
"""
import asyncio

import pytest
from fastapi.testclient import TestClient

from tests.conftest import PHONE_TOKEN, PUBLISH_TOKEN, READ_TOKEN, auth


# ---------------------------------------------------------------------------
# Auth: every endpoint must 401 without (or with the wrong) bearer token.
# ---------------------------------------------------------------------------

def test_publish_requires_publish_token(client):
    assert client.post("/events", json={"k": "st", "a": []}).status_code == 401
    assert client.post("/events", json={"k": "st", "a": []}, headers=auth("wrong")).status_code == 401


def test_event_state_requires_publish_token(client):
    assert client.get("/events/abc123").status_code == 401


def test_resolve_requires_publish_token(client):
    assert client.post("/events/abc123/resolve").status_code == 401


def test_snapshot_requires_read_token(client):
    assert client.get("/watch/snapshot").status_code == 401
    assert client.get("/watch/snapshot", headers=auth(PUBLISH_TOKEN)).status_code == 401
    assert client.get("/watch/snapshot", headers=auth(READ_TOKEN)).status_code == 200


def test_ws_requires_phone_token(client):
    from starlette.websockets import WebSocketDisconnect

    # No Authorization header at all: server closes with 4401 before accepting,
    # which the test client surfaces as a WebSocketDisconnect on connect.
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/watch"):
            pass
    assert exc_info.value.code == 4401


# ---------------------------------------------------------------------------
# Ask publish -> WebSocket delivery, and the reply round trip.
# ---------------------------------------------------------------------------

def test_ask_publish_ws_receives(client):
    with client.websocket_connect("/ws/watch", headers=auth(PHONE_TOKEN)) as ws:
        ws.receive_json()  # initial replay: status snapshot sent on connect, even with 0 pending

        resp = client.post(
            "/events",
            json={"k": "ask", "t": "Deploy build to prod?", "o": ["Yes", "No"]},
            headers=auth(PUBLISH_TOKEN),
        )
        assert resp.status_code == 200
        ask_id = resp.json()["id"]

        frame = ws.receive_json()
        assert frame == {"k": "ask", "id": ask_id, "t": "Deploy build to prod?",
                          "o": ["Yes", "No"], "x": 900}
        status = ws.receive_json()
        assert status == {"k": "st", "a": [], "q": 1}


def test_reply_clears_ask_and_updates_status(client, app_module, monkeypatch):
    notified = []
    monkeypatch.setattr(app_module, "REPLY_WEBHOOK", "http://example.invalid/reply")

    async def fake_notify(payload):
        notified.append(payload)

    monkeypatch.setattr(app_module, "notify_stonesage", fake_notify)

    with client.websocket_connect("/ws/watch", headers=auth(PHONE_TOKEN)) as ws:
        ws.receive_json()  # initial replay: status snapshot sent on connect
        resp = client.post("/events", json={"k": "ask", "t": "Restart worker?", "o": ["Yes", "No"]},
                            headers=auth(PUBLISH_TOKEN))
        ask_id = resp.json()["id"]
        ws.receive_json()  # ask
        ws.receive_json()  # st

        ws.send_json({"id": ask_id, "r": 0})
        clr = ws.receive_json()
        assert clr == {"k": "clr", "id": ask_id}
        status = ws.receive_json()
        assert status["q"] == 0

    assert notified == [{"id": ask_id, "r": 0, "choice": "Yes", "p": None,
                          "d": False, "state": "answered", "via": "watch"}]

    state = client.get(f"/events/{ask_id}", headers=auth(PUBLISH_TOKEN)).json()
    assert state == {"id": ask_id, "state": "answered", "r": 0, "choice": "Yes"}


def test_invalid_reply_index_is_ignored(client):
    with client.websocket_connect("/ws/watch", headers=auth(PHONE_TOKEN)) as ws:
        ws.receive_json()  # initial replay: status snapshot sent on connect
        resp = client.post("/events", json={"k": "ask", "t": "Proceed?", "o": ["Yes", "No"]},
                            headers=auth(PUBLISH_TOKEN))
        ask_id = resp.json()["id"]
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"id": ask_id, "r": 5})  # out of range: silently dropped
        ws.send_json({"k": "sync"})
        replayed = ws.receive_json()
        assert replayed["id"] == ask_id  # still pending, replayed as-is

    state = client.get(f"/events/{ask_id}", headers=auth(PUBLISH_TOKEN)).json()
    assert state["state"] == "pending"


# ---------------------------------------------------------------------------
# Destructive asks are always rewritten to Deny / At desk.
# ---------------------------------------------------------------------------

def test_destructive_ask_forces_deny_at_desk(client):
    resp = client.post(
        "/events",
        json={"k": "ask", "t": "Wipe the volume?", "o": ["Sure", "Go ahead"], "d": True},
        headers=auth(PUBLISH_TOKEN),
    )
    assert resp.status_code == 200
    ask_id = resp.json()["id"]
    state = client.get(f"/events/{ask_id}", headers=auth(PUBLISH_TOKEN)).json()
    assert state["state"] == "pending"

    snap = client.get("/watch/snapshot", headers=auth(READ_TOKEN)).json()
    assert snap == {"st": {"k": "st", "a": [], "q": 1}, "use": {}}
    # o isn't in the snapshot shape; confirm the rewrite via the raw pending store instead.


def test_destructive_ask_options_are_deny_at_desk(client, app_module):
    client.post("/events", json={"k": "ask", "t": "Wipe it", "o": ["ok"], "d": True},
                headers=auth(PUBLISH_TOKEN))
    pending = app_module.store.pending()
    assert len(pending) == 1
    assert pending[0]["o"] == ["Deny", "At desk"]
    assert pending[0]["d"] == 1


# ---------------------------------------------------------------------------
# cfg validation: exactly 5 ints, each 0..14.
# ---------------------------------------------------------------------------

def test_cfg_accepts_five_valid_slots(client):
    resp = client.post("/events", json={"k": "cfg", "slots": [1, 8, 2, 6, 9]},
                        headers=auth(PUBLISH_TOKEN))
    assert resp.status_code == 200
    snap = client.get("/watch/snapshot", headers=auth(READ_TOKEN)).json()
    assert snap["cfg"] == {"k": "cfg", "slots": [1, 8, 2, 6, 9]}


def test_cfg_rejects_wrong_length(client):
    resp = client.post("/events", json={"k": "cfg", "slots": [1, 2, 3]},
                        headers=auth(PUBLISH_TOKEN))
    assert resp.status_code == 400


def test_cfg_rejects_out_of_range_id(client):
    resp = client.post("/events", json={"k": "cfg", "slots": [1, 2, 3, 4, 18]},
                        headers=auth(PUBLISH_TOKEN))
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# st sorting (wait, err, run, done, idle) and pending-ask count.
# ---------------------------------------------------------------------------

def test_status_sorts_agents_by_state_rank(client):
    agents = [
        {"p": "c", "s": "idle", "t": "napping"},
        {"p": "a", "s": "wait", "t": "needs you"},
        {"p": "b", "s": "run", "t": "working"},
    ]
    client.post("/events", json={"k": "st", "a": agents}, headers=auth(PUBLISH_TOKEN))
    snap = client.get("/watch/snapshot", headers=auth(READ_TOKEN)).json()
    assert [a["p"] for a in snap["st"]["a"]] == ["a", "b", "c"]
    assert snap["st"]["q"] == 0


# ---------------------------------------------------------------------------
# Snapshot shape and replay-on-connect / replay-on-sync.
# ---------------------------------------------------------------------------

def test_snapshot_shape(client):
    snap = client.get("/watch/snapshot", headers=auth(READ_TOKEN)).json()
    assert set(snap.keys()) == {"st", "use"}
    assert snap["st"] == {"k": "st", "a": [], "q": 0}


def test_replay_sends_pending_asks_on_connect(client):
    resp = client.post("/events", json={"k": "ask", "t": "Approve?", "o": ["Yes", "No"]},
                        headers=auth(PUBLISH_TOKEN))
    ask_id = resp.json()["id"]

    with client.websocket_connect("/ws/watch", headers=auth(PHONE_TOKEN)) as ws:
        first = ws.receive_json()
        assert first["id"] == ask_id
        second = ws.receive_json()
        assert second == {"k": "st", "a": [], "q": 1}


# ---------------------------------------------------------------------------
# Ask expiry: an unanswered ask past its TTL is cleared and reported r=-1.
#
# The bridge's expiry_loop (app.py) polls every 15s in real time, which is too
# slow to await directly in a test. Decide how to exercise it without a real
# 15s sleep, and implement it here.
# ---------------------------------------------------------------------------

def test_ask_expires_and_notifies_stonesage(app_module, monkeypatch):
    notified = []

    async def fake_notify(payload):
        notified.append(payload)

    monkeypatch.setattr(app_module, "notify_stonesage", fake_notify)

    # Collapse the loop's 15s poll to near-zero so the background task (already
    # started by the app's lifespan once we open TestClient below) catches the
    # expired ask on its next iteration instead of a real 15s wall-clock wait.
    real_sleep = asyncio.sleep

    async def fast_sleep(_seconds):
        await real_sleep(0)

    monkeypatch.setattr(app_module.asyncio, "sleep", fast_sleep)

    with TestClient(app_module.app) as client:
        resp = client.post(
            "/events",
            json={"k": "ask", "t": "Approve?", "o": ["Yes", "No"], "x": 30},
            headers=auth(PUBLISH_TOKEN),
        )
        ask_id = resp.json()["id"]

        with client.websocket_connect("/ws/watch", headers=auth(PHONE_TOKEN)) as ws:
            ws.receive_json()  # initial replay: the pending ask
            ws.receive_json()  # initial replay: status snapshot

            # The publish API clamps TTL to a 30s minimum, so force this one
            # past its expiry directly rather than waiting on real time.
            app_module.store.db.execute("UPDATE asks SET expires=0 WHERE id=?", (ask_id,))
            app_module.store.db.commit()

            clr = ws.receive_json()
            assert clr == {"k": "clr", "id": ask_id}
            status = ws.receive_json()
            assert status["q"] == 0

    assert len(notified) == 1
    assert notified[0]["id"] == ask_id
    assert notified[0]["r"] == -1
    assert notified[0]["choice"] is None
    assert notified[0]["state"] == "expired"

    state = app_module.store.get_ask(ask_id)
    assert state["state"] == "expired"
