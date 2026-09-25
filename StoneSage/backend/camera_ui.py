"""
Camera tiles for the StoneSage LIVE tab: how each camera is shown, snapshots, HA HLS streams and PTZ.

Per camera (config.json camera_ui, keyed by HA camera entity):
  live: "webrtc"   go2rtc stream played over WebRTC: a Frigate camera (frigate.cameras), or any go2rtc stream
                   named by go2rtc: (the solar TCW90 via tapo://, which go2rtc only opens while someone watches)
        "hls"      Home Assistant's own stream (unreliable for the TCW90: HA's muxer fails on its first frame)
        "snapshot" still frame only, refreshed on demand (battery TC82s must not be kept awake)
  ptz:  HA entity prefix of a Tapo PTZ camera: button.<ptz>_move_up/down/left/right and
        select.<ptz>_move_to_preset (preset names are read from HA live, never hardcoded)
  min_refresh_s: snapshots newer than this are served from cache instead of waking the camera again
"""

import asyncio
import io
import json
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

MOVES = ("up", "down", "left", "right")
HLS_TOKEN = re.compile(r"^[A-Za-z0-9_-]{8,}$")
HLS_FILE = re.compile(r"^[A-Za-z0-9_./-]+\.(m3u8|m4s|mp4|ts)$")

_snap_cache: Dict[str, Tuple[float, bytes]] = {}
_snap_lock = threading.Lock()


def camera_entries(cfg: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return cfg.get("camera_ui") or {}


def presets(ptz: str, get_state: Callable[[str], Optional[Dict[str, Any]]]) -> List[str]:
    """Preset names exactly as HA spells them (the driveway's 'Driveway ' has a trailing space)."""
    st = get_state(f"select.{ptz}_move_to_preset") or {}
    return list((st.get("attributes") or {}).get("options") or [])


def list_cameras(cfg: Dict[str, Any], get_state: Callable[[str], Optional[Dict[str, Any]]],
                 webrtc_streams: Dict[str, str]) -> List[Dict[str, Any]]:
    """Tiles in config order. webrtc_streams: HA entity -> go2rtc stream for cameras Frigate serves."""
    out = []
    for entity, c in camera_entries(cfg).items():
        live = c.get("live", "snapshot")
        tile = {"entity": entity, "name": c.get("name", entity), "live": live,
                "min_refresh_s": int(c.get("min_refresh_s", 0))}
        if live == "webrtc":
            if entity not in webrtc_streams:
                tile["live"] = "snapshot"  # Frigate/go2rtc down: still show something
            else:
                tile["stream"] = webrtc_streams[entity]
        if c.get("ptz"):
            try:
                tile["ptz"] = {"presets": presets(c["ptz"], get_state)}
            except Exception:
                tile["ptz"] = {"presets": []}
        out.append(tile)
    return out


# ------------------------------------------------------------ snapshots ----
def snapshot(entity: str, cfg: Dict[str, Any], fetch: Callable[[str], Optional[bytes]],
             force: bool = False, width: int = 640, clock: Callable[[], float] = time.time) -> Tuple[Optional[bytes], float]:
    """(jpeg, age_s). A cached frame younger than the camera's min_refresh_s is returned even when force=True,
    so a refresh button cannot keep a battery camera awake."""
    c = camera_entries(cfg).get(entity)
    if c is None:
        raise KeyError(entity)
    min_age = int(c.get("min_refresh_s", 0))
    now = clock()
    with _snap_lock:
        cached = _snap_cache.get(entity)
    if cached and (not force or now - cached[0] < min_age):
        return cached[1], now - cached[0]
    raw = fetch(entity)
    if not raw:
        return (cached[1], now - cached[0]) if cached else (None, 0.0)
    img = _shrink(raw, width)
    with _snap_lock:
        _snap_cache[entity] = (now, img)
    return img, 0.0


def _shrink(raw: bytes, width: int) -> bytes:
    """Tapo snapshots are up to 4K; a tile needs ~640 px."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(raw))
        if im.width <= width:
            return raw
        im = im.convert("RGB").resize((width, round(im.height * width / im.width)))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=80)
        return buf.getvalue()
    except Exception:
        return raw


# ------------------------------------------------------------------ PTZ ----
def ptz_command(entity: str, cfg: Dict[str, Any], action: str, preset: str,
                get_state: Callable[[str], Optional[Dict[str, Any]]]) -> Tuple[str, str, Optional[str]]:
    """Validated HA call for a PTZ request: ('button', entity_id, None) or ('select', entity_id, option)."""
    c = camera_entries(cfg).get(entity) or {}
    ptz = c.get("ptz")
    if not ptz:
        raise ValueError("camera has no PTZ")
    if action in MOVES:
        return "button", f"button.{ptz}_move_{action}", None
    if action == "preset":
        if preset not in presets(ptz, get_state):
            raise ValueError(f"unknown preset '{preset}'")
        return "select", f"select.{ptz}_move_to_preset", preset
    raise ValueError(f"unknown PTZ action '{action}'")


# ------------------------------------------------------------------ HLS ----
def ha_hls_url(ha_url: str, token: str, entity: str, timeout: float = 20) -> str:
    """Ask HA (websocket camera/stream) for an HLS playlist of a camera; returns '/api/hls/<token>/master_playlist.m3u8'.
    HA starts the stream on request and stops it ~30 s after the last playlist fetch."""
    import websockets  # available on the StoneSage host (websockets 10.x)

    async def go() -> str:
        async with websockets.connect(ha_url.rstrip("/").replace("http", "ws", 1) + "/api/websocket", max_size=None) as ws:
            await ws.recv()
            await ws.send(json.dumps({"type": "auth", "access_token": token}))
            if json.loads(await ws.recv()).get("type") != "auth_ok":
                raise RuntimeError("Home Assistant rejected the token")
            await ws.send(json.dumps({"id": 1, "type": "camera/stream", "entity_id": entity, "format": "hls"}))
            res = json.loads(await ws.recv())
            if not res.get("success"):
                raise RuntimeError((res.get("error") or {}).get("message", "camera/stream failed"))
            return res["result"]["url"]

    return asyncio.run(asyncio.wait_for(go(), timeout))


def hls_proxy_path(rest: str) -> Optional[str]:
    """'/api/cameras/hls/<token>/<file>' tail -> HA path '/api/hls/<token>/<file>', or None if it is not HLS."""
    token, _, file = rest.partition("/")
    if not HLS_TOKEN.match(token) or ".." in file or not HLS_FILE.match(file):
        return None
    return f"/api/hls/{token}/{file}"
