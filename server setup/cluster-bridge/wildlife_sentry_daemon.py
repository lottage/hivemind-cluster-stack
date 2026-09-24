#!/usr/bin/env python3
"""
Aevum-3D & Sovereign Cluster: 24/7 Wildlife & Perimeter Sentinel Daemon
Monitors outdoor & perimeter cameras, detects animals (deer, rabbits, birds, foxes),
performs anatomical feature fingerprinting and Re-ID to name individual animals over time,
logs rich dossiers with snapshots to Obsidian, and broadcasts real-time alerts to the
Sovereign Assembly Hall (:8766) and Home Assistant.

Enhanced with:
- Zero-drain Home Assistant Notification Listener (sensor.austin_s_phone_last_notification)
- Delayed Tapo Media Sync from SD card (media-source://tapo_control)
- Multi-Frame Temporal Movement Verification (Numpy diff + frame-by-frame VLM)
- 1GB / 15-clip FIFO video rotation per camera
"""

import os
import sys
import time
import json
import base64
import signal
import logging
import io
import asyncio
import threading
import subprocess
import glob
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import requests
import websockets
from PIL import Image

try:
    import redis
except ImportError:
    redis = None

EASTERN_TZ = ZoneInfo("America/New_York")

# --- CONFIGURATION & ENDPOINTS ---
HASS_URL = os.getenv("HASS_URL", "http://192.168.1.82:8123")
HASS_TOKEN = os.getenv("HASS_TOKEN", "")  # provided via EnvironmentFile=/etc/stonesage/secrets.env
if not HASS_TOKEN:
    import sys as _sys
    print("WARNING: HASS_TOKEN is not set (expected in /etc/stonesage/secrets.env); Home Assistant calls will fail.", file=_sys.stderr)
VISION_URL = os.getenv("VISION_URL", "http://127.0.0.1:8004/v1/chat/completions")
COORDINATOR_URL = os.getenv("COORDINATOR_URL", "http://127.0.0.1:8001/v1/chat/completions")
EMBEDDER_URL = os.getenv("EMBEDDER_URL", "http://127.0.0.1:8003/v1/embeddings")
QDRANT_URL = os.getenv("QDRANT_URL", "http://192.168.1.112:6333")
ASSEMBLY_API_URL = os.getenv("ASSEMBLY_API_URL", "http://127.0.0.1:8766/api/channels/vigilance-alerts/message")
VALKEY_HOST = os.getenv("VALKEY_HOST", "127.0.0.1")
VALKEY_PORT = int(os.getenv("VALKEY_PORT", 6379))

# Directory Layout
BASE_DIR = os.getenv("WILDLIFE_BASE_DIR", "/opt/cluster-bridge/wildlife")
REGISTRY_FILE = os.path.join(BASE_DIR, "wildlife_registry.json")
LOG_FILE = os.path.join(BASE_DIR, "WILDLIFE_ACTIVITY_LOG.md")
KNOWN_ENTITIES_FILE = os.path.join(BASE_DIR, "known_entities.json")
SNAPSHOTS_DIR = os.path.join(BASE_DIR, "snapshots")
PROFILES_DIR = os.path.join(BASE_DIR, "profiles")
FOOTAGE_DIR = os.path.join(BASE_DIR, "footage")
TMP_DIR = os.path.join(BASE_DIR, "tmp_frames")

# Storage & Sync Limits
MAX_STORAGE_BYTES = 1024 * 1024 * 1024  # 1.0 GB per camera
MAX_CLIPS_PER_CAMERA = 15               # Hold up to 15 recent clips
SYNC_DELAY_SECONDS = 40                 # Wait ~40s for on-camera SD write to finalize

# Cameras to Monitor
CAMERAS = [
    {
        "id": "camera.back_yard_hd_stream_direct",
        "name": "Back Yard",
        "entry_id": "01KWADDAA0EN325M2HEV06W418",
        "keywords": ["back yard", "backyard", "back"],
        "is_wildlife_primary": True,
        "is_battery": True,
        "battery_sensor": "sensor.back_yard_battery",
        "poll_interval": 1800  # 30 minutes baseline safety check
    },
    {
        "id": "camera.side_yard_hd_stream_direct",
        "name": "Side Yard",
        "entry_id": "01KWADGYRFNX2Y1R67A45S435B",
        "keywords": ["side yard", "sideyard", "side"],
        "is_wildlife_primary": True,
        "is_battery": True,
        "battery_sensor": "sensor.side_yard_battery",
        "poll_interval": 1800  # 30 minutes baseline safety check
    },
    {
        "id": "camera.driveway_front_door_hd_stream_direct",
        "name": "Driveway/Front",
        "entry_id": "01KWADJKEST782TN4J2TR0V9S0",
        "keywords": ["driveway", "front door", "front"],
        "is_wildlife_primary": False,
        "is_battery": True,
        "power": "solar",      # TCW90: battery + solar panel, no RTSP; timer polls allowed (see solar_poll_interval)
        "battery_sensor": "sensor.driveway_front_door_battery",
        "poll_interval": 300   # base interval at a healthy charge
    },
    {
        "id": "camera.kitchen_living_room_hd_stream",
        "name": "Kitchen/Living",
        "entry_id": "01KVYG1DV4FVC3AC2WT297152M",
        "keywords": ["kitchen", "living room", "luna"],
        "is_wildlife_primary": False,
        "is_battery": False,
        "battery_sensor": None,
        "poll_interval": 90   # AC wall powered
    }
]

def solar_poll_interval(level: Optional[int], base: float) -> Optional[float]:
    """How often a solar-charged camera may be woken for a timer snapshot.

    level: battery percent from HA (None if the sensor could not be read).
    base:  the camera's poll_interval, meant for a healthy charge (driveway: 300 s).
    Returns seconds between snapshots, or None to stop timer polling (push alerts still work).
    Each wake costs the camera a few seconds of Wi-Fi and encoder power; the panel refills it by day.
    """
    # TODO: battery-dependent policy (John, later). Until then: the base interval. Not deployed yet.
    return base


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [WildlifeSentry] %(message)s"
)
logger = logging.getLogger("WildlifeSentry")

class WildlifeSentryDaemon:
    def __init__(self):
        self.running = True
        self.last_frames: Dict[str, Image.Image] = {}
        self.last_sightings: Dict[str, float] = {}             # Cooldown tracker
        self.last_polled: Dict[str, float] = {}                # Per-camera schedule tracker
        self.battery_cache: Dict[str, Tuple[float, Optional[int]]] = {}  # sensor -> (read at, level)
        self.camera_backoffs: Dict[str, float] = {}            # Per-camera error backoff tracker
        self.last_notification_triggers: Dict[str, float] = {} # Debounce tracker
        self.last_notification_post_times: Dict[str, int] = {}  # Timestamp tracker for active notifications
        self.active_bursts: Dict[str, Dict[str, Any]] = {}      # High-frequency wildlife burst tracking {cam_id: {shots_left, interval, animal_name, species, next_shot}}
        self.registry: Dict[str, Any] = {"animals": []}
        self.known_entities: Dict[str, Any] = {"people": [], "pets": []}
        
        self._ensure_directories()
        self._load_registry()
        self._load_known_entities()
        self._init_active_notifications_baseline()
        self._init_signal_handlers()
        self._start_notification_listener()

    def _ensure_directories(self):
        os.makedirs(BASE_DIR, exist_ok=True)
        os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
        os.makedirs(PROFILES_DIR, exist_ok=True)
        os.makedirs(FOOTAGE_DIR, exist_ok=True)
        os.makedirs(TMP_DIR, exist_ok=True)
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.write("# 🦌 24/7 Wildlife & Perimeter Activity Log\n\nPersistent ledger of biological sightings, animal re-identifications, and perimeter events across property cameras.\n\n---\n")

    def _load_registry(self):
        if os.path.exists(REGISTRY_FILE):
            try:
                with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                    self.registry = json.load(f)
                logger.info(f"Loaded wildlife registry with {len(self.registry.get('animals', []))} known animals.")
            except Exception as e:
                logger.error(f"Failed to load registry: {e}. Starting fresh.")
                self.registry = {"animals": []}
        else:
            self._save_registry()

    def _load_known_entities(self):
        """Loads known residents, vehicles, and pets from known_entities.json."""
        if os.path.exists(KNOWN_ENTITIES_FILE):
            try:
                with open(KNOWN_ENTITIES_FILE, "r", encoding="utf-8") as f:
                    self.known_entities = json.load(f)
                p_cnt = len(self.known_entities.get("people", []))
                pet_cnt = len(self.known_entities.get("pets", []))
                logger.info(f"Loaded {p_cnt} known people and {pet_cnt} known pets from known_entities.json.")
            except Exception as e:
                logger.error(f"Failed to load known entities: {e}")
        else:
            logger.warning(f"No known_entities.json found at {KNOWN_ENTITIES_FILE}")

    def _save_registry(self):
        try:
            with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.registry, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")

    def _init_active_notifications_baseline(self):
        """Fetches current active notifications on startup to avoid re-triggering on stale alerts."""
        try:
            url = f"{HASS_URL}/api/states/sensor.austin_s_phone_active_notification_count"
            headers = {"Authorization": f"Bearer {HASS_TOKEN}"}
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                attrs = resp.json().get("attributes", {})
                for k, v in attrs.items():
                    if "post_time" in k:
                        self.last_notification_post_times[k.replace("_post_time", "")] = v
                logger.info(f"Initialized active notification baseline with {len(self.last_notification_post_times)} existing items.")
        except Exception as e:
            logger.warning(f"Could not initialize active notification baseline: {e}")

    def _init_signal_handlers(self):
        signal.signal(signal.SIGINT, self._stop)
        signal.signal(signal.SIGTERM, self._stop)

    def _stop(self, signum, frame):
        logger.info("Received termination signal. Shutting down Wildlife Sentry cleanly...")
        self.running = False

    def get_battery_level(self, battery_sensor: Optional[str]) -> Optional[int]:
        """Queries Home Assistant battery level for battery-operated cameras."""
        if not battery_sensor:
            return None
        url = f"{HASS_URL}/api/states/{battery_sensor}"
        headers = {"Authorization": f"Bearer {HASS_TOKEN}"}
        try:
            resp = requests.get(url, headers=headers, timeout=3)
            if resp.status_code == 200:
                val = resp.json().get("state")
                return int(float(val))
        except Exception:
            pass
        return None

    def _battery_cached(self, battery_sensor: Optional[str], max_age: float = 600) -> Optional[int]:
        """get_battery_level() at most once per max_age seconds per sensor (the main loop ticks every few seconds)."""
        if not battery_sensor:
            return None
        read_at, level = self.battery_cache.get(battery_sensor, (0.0, None))
        if time.time() - read_at > max_age:
            level = self.get_battery_level(battery_sensor)
            self.battery_cache[battery_sensor] = (time.time(), level)
        return level

    def periodic_interval(self, cam: Dict[str, Any]) -> Optional[float]:
        """Seconds between timer snapshots for this camera, or None to never wake it on a timer."""
        if not cam.get("is_battery"):
            return cam.get("poll_interval", 1800)
        if cam.get("power") != "solar":
            return None  # ZERO-DRAIN rule: plain battery cams wake only on a hardware push
        return solar_poll_interval(self._battery_cached(cam.get("battery_sensor")), cam.get("poll_interval", 300))

    def fetch_camera_snapshot(self, entity_id: str) -> Optional[bytes]:
        backoff_until = getattr(self, "camera_backoffs", {}).get(entity_id, 0)
        if time.time() < backoff_until:
            return None

        url = f"{HASS_URL}/api/camera_proxy/{entity_id}"
        headers = {"Authorization": f"Bearer {HASS_TOKEN}"}
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200 and len(resp.content) > 1000:
                if hasattr(self, "camera_backoffs") and entity_id in self.camera_backoffs:
                    del self.camera_backoffs[entity_id]
                return resp.content
        except Exception as e:
            if not hasattr(self, "camera_backoffs"):
                self.camera_backoffs = {}
            self.camera_backoffs[entity_id] = time.time() + 180
            logger.warning(f"Camera {entity_id} unreachable/timeout ({e}). Backing off for 3m.")
        return None

    def compute_motion_delta(self, entity_id: str, new_img: Image.Image) -> float:
        """Computes quick pixel delta on 160x90 grayscale thumbnail to detect movement."""
        thumb = new_img.convert("L").resize((160, 90), Image.Resampling.BILINEAR)
        if entity_id not in self.last_frames:
            self.last_frames[entity_id] = thumb
            return 10.0  # Force first frame analysis
            
        old_thumb = self.last_frames[entity_id]
        self.last_frames[entity_id] = thumb
        
        old_bytes = old_thumb.tobytes()
        new_bytes = thumb.tobytes()
        diff_sum = sum(abs(a - b) for a, b in zip(old_bytes, new_bytes))
        avg_diff = diff_sum / len(old_bytes)
        delta_pct = (avg_diff / 255.0) * 100.0
        return delta_pct

    def enforce_fifo_quota(self, cam_dir: str):
        """Ensures camera footage folder stays strictly under MAX_STORAGE_BYTES and MAX_CLIPS_PER_CAMERA."""
        if not os.path.exists(cam_dir):
            return
        clips = []
        total_bytes = 0
        for f in os.listdir(cam_dir):
            fpath = os.path.join(cam_dir, f)
            if os.path.isfile(fpath) and f.endswith(".mp4"):
                try:
                    stat = os.stat(fpath)
                    clips.append((fpath, stat.st_mtime, stat.st_size))
                    total_bytes += stat.st_size
                except Exception:
                    pass
                
        # Sort oldest first
        clips.sort(key=lambda x: x[1])
        
        while clips and (len(clips) > MAX_CLIPS_PER_CAMERA or total_bytes > MAX_STORAGE_BYTES):
            oldest_path, _, oldest_size = clips.pop(0)
            try:
                os.remove(oldest_path)
                total_bytes -= oldest_size
                logger.info(f"🗑️ [FIFO] Pruned old footage: {os.path.basename(oldest_path)} ({oldest_size / (1024 * 1024):.1f}MB)")
            except Exception as e:
                logger.warning(f"Failed to delete {oldest_path}: {e}")

    async def fetch_latest_recording_url(self, entry_id: str, cam_name: str) -> Optional[str]:
        """Queries HA media_source for today's recordings and resolves newest clip URL."""
        now_dt = datetime.now(EASTERN_TZ)
        date_str = now_dt.strftime("%Y%m%d")
        hass_ws = HASS_URL.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
        
        try:
            async with websockets.connect(hass_ws, max_size=20_000_000) as ws:
                await ws.recv()
                await ws.send(json.dumps({"type": "auth", "access_token": HASS_TOKEN}))
                auth_resp = json.loads(await ws.recv())
                if auth_resp.get("type") != "auth_ok":
                    logger.error(f"HA auth failed during media fetch: {auth_resp}")
                    return None
                    
                day_content_id = f"media-source://tapo_control/tapo_control/?entry={entry_id}&title={date_str}&date={date_str}"
                await ws.send(json.dumps({"id": 10, "type": "media_source/browse_media", "media_content_id": day_content_id}))
                day_res = json.loads(await ws.recv())
                
                children = day_res.get("result", {}).get("children", [])
                if not children:
                    logger.info(f"No recordings found for {cam_name} on date {date_str}.")
                    return None
                    
                latest_clip = children[-1]
                latest_content_id = latest_clip.get("media_content_id")
                clip_title = latest_clip.get("title", "clip")
                logger.info(f"📹 Found latest recording on {cam_name}: {clip_title}")
                
                await ws.send(json.dumps({"id": 11, "type": "media_source/resolve_media", "media_content_id": latest_content_id}))
                resolve_res = json.loads(await ws.recv())
                url = resolve_res.get("result", {}).get("url")
                return url
        except Exception as e:
            logger.error(f"Error fetching recording URL for {cam_name}: {e}")
        return None

    def download_footage_clip(self, url_path: str, cam_name: str) -> Optional[str]:
        """Downloads resolved MP4 from Home Assistant into local footage directory."""
        clean_cam = cam_name.replace(" ", "_").replace("/", "_").lower()
        cam_dir = os.path.join(FOOTAGE_DIR, clean_cam)
        os.makedirs(cam_dir, exist_ok=True)
        
        now_dt = datetime.now(EASTERN_TZ)
        timestamp_str = now_dt.strftime("%Y%m%d_%H%M%S")
        out_filename = f"{clean_cam}_{timestamp_str}.mp4"
        out_path = os.path.join(cam_dir, out_filename)
        
        full_url = f"{HASS_URL}{url_path}" if url_path.startswith("/") else url_path
        try:
            resp = requests.get(full_url, stream=True, timeout=60)
            if resp.status_code == 200:
                with open(out_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                file_size_mb = os.path.getsize(out_path) / (1024 * 1024)
                logger.info(f"📥 Downloaded footage clip: {out_filename} ({file_size_mb:.2f} MB)")
                
                self.enforce_fifo_quota(cam_dir)
                return out_path
        except Exception as e:
            logger.error(f"Failed to download footage clip from {full_url}: {e}")
        return None

    def get_video_duration(self, video_path: str) -> float:
        """Retrieves video duration in seconds using ffprobe."""
        try:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
            return float(subprocess.check_output(cmd).decode().strip())
        except Exception:
            return 15.0

    def extract_evenly_spaced_frames(self, video_path: str, num_frames: int = 5) -> List[Dict[str, Any]]:
        """Extracts num_frames evenly spaced across the video duration with timestamps and grayscale arrays."""
        duration = self.get_video_duration(video_path)
        fractions = [0.15 + (0.75 / (num_frames - 1)) * i for i in range(num_frames)]
        timestamps = [duration * f for f in fractions]
        
        extracted = []
        pattern_prefix = os.path.join(TMP_DIR, "frame_extract_")
        for old_f in glob.glob(f"{pattern_prefix}*.jpg"):
            try:
                os.remove(old_f)
            except Exception:
                pass

        for idx, ts in enumerate(timestamps):
            out_f = f"{pattern_prefix}{idx}.jpg"
            cmd = ["ffmpeg", "-y", "-ss", f"{ts:.2f}", "-i", video_path, "-vframes", "1", "-q:v", "2", out_f]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(out_f):
                with open(out_f, "rb") as f:
                    raw_bytes = f.read()
                try:
                    img_gray = Image.open(io.BytesIO(raw_bytes)).convert("L").resize((320, 180))
                    arr = np.array(img_gray, dtype=np.int16)
                    extracted.append({
                        "timestamp": ts,
                        "bytes": raw_bytes,
                        "array": arr,
                        "index": idx
                    })
                except Exception:
                    pass
                try:
                    os.remove(out_f)
                except Exception:
                    pass
                
        return extracted

    def evaluate_video_physical_motion(self, frames: List[Dict[str, Any]]) -> Tuple[bool, float, float]:
        """Calculates inter-frame and span motion. Returns (has_motion, max_step_delta, span_delta)."""
        if len(frames) < 2:
            return False, 0.0, 0.0
            
        step_deltas = []
        for i in range(len(frames) - 1):
            diff = np.abs(frames[i+1]["array"] - frames[i]["array"])
            ratio = float(np.mean(diff > 30) * 100.0)
            step_deltas.append(ratio)
            
        span_diff = np.abs(frames[-1]["array"] - frames[0]["array"])
        span_ratio = float(np.mean(span_diff > 30) * 100.0)
        max_step = max(step_deltas) if step_deltas else 0.0
        
        has_motion = max_step >= 1.5 or span_ratio >= 1.8
        return has_motion, max_step, span_ratio

    def analyze_frame_with_vision(self, img_bytes: bytes, cam_name: str) -> Optional[Dict[str, Any]]:
        """Sends optimized 640px frame to local Gemma-4 Vision Model (:8004)."""
        try:
            raw_img = Image.open(io.BytesIO(img_bytes))
            w, h = raw_img.size
            scale = min(448 / max(w, h), 1.0)
            nw = max(28, (int(w * scale) // 28) * 28)
            nh = max(28, (int(h * scale) // 28) * 28)
            resized = raw_img.resize((nw, nh), Image.Resampling.LANCZOS)
            
            buf = io.BytesIO()
            resized.save(buf, format="JPEG", quality=80)
            b64_img = base64.b64encode(buf.getvalue()).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to prepare image for vision: {e}")
            return None

        prompt = (
            f"You are a strict security, resident, and wildlife perception analyzer for camera '{cam_name}'.\n"
            "CRITICAL RULES:\n"
            "1. Never mistake inanimate yard equipment, carts, tools, rakes, shovels, or shadows for living beings.\n"
            "2. Classify any living subject into:\n"
            "   - 'person': adult male, adult female, child\n"
            "   - 'pet': domestic cat or dog (NOTE: pets NEVER wear clothes)\n"
            "   - 'wildlife': wild animal (deer, fox, rabbit, squirrel, bird, etc.)\n"
            "   - 'none': empty scene / inanimate yard equipment only\n"
            "3. For people, look specifically at their legs: distinguish SHORTS from PANTS/JEANS by checking if knees and calves are bare.\n\n"
            "Return valid raw JSON:\n"
            "{\n"
            '  "detected": true/false,\n'
            '  "subject_type": "person" / "pet" / "wildlife" / "none",\n'
            '  "person_details": {\n'
            '    "gender_presentation": "male" / "female" / "unknown",\n'
            '    "hair": "short dark / brunette curly / etc.",\n'
            '    "upper_clothing": "hoodie / shirt / jacket / etc.",\n'
            '    "lower_clothing": "shorts / pants / jeans / etc.",\n'
            '    "legs_bare": true/false,\n'
            '    "footwear": "barefoot / shoes / boots"\n'
            '  },\n'
            '  "animal_details": {\n'
            '    "species": "cat" / "dog" / "deer" / "fox" / "etc",\n'
            '    "breed_or_type": "dachshund" / "domestic shorthair" / "none",\n'
            '    "coat_color_pattern": "tuxedo black and white / black with tan points / etc."\n'
            '  },\n'
            '  "behavior": "walking / standing / running / resting",\n'
            '  "security_anomaly": "none" or description,\n'
            '  "summary": "1 objective sentence description"\n'
            "}\n"
            "Output ONLY valid raw JSON."
        )

        payload = {
            "model": "vision",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}},
                        {"type": "text", "text": prompt}
                    ]
                }
            ],
            "max_tokens": 180,
            "temperature": 0.1
        }

        try:
            resp = requests.post(VISION_URL, json=payload, timeout=75)
            if resp.status_code == 200:
                raw_text = resp.json()["choices"][0]["message"]["content"].strip()
                clean_json = raw_text
                if "```json" in clean_json:
                    clean_json = clean_json.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_json:
                    clean_json = clean_json.split("```")[1].split("```")[0].strip()
                
                parsed = json.loads(clean_json)
                subj = str(parsed.get("subject_type", "none")).lower()
                anim = parsed.get("animal_details") or {}
                
                # Normalize detection flags
                parsed["wildlife_detected"] = (subj == "wildlife")
                parsed["person_detected"] = (subj == "person")
                parsed["pet_detected"] = (subj == "pet")
                
                if subj == "wildlife":
                    parsed["species"] = anim.get("species", "animal").lower()
                elif subj == "pet":
                    parsed["species"] = anim.get("species", "pet").lower()
                else:
                    parsed["species"] = "none"
                    
                parsed["anatomy_traits"] = f"{anim.get('breed_or_type', '')} {anim.get('coat_color_pattern', '')}".strip()
                return parsed
        except Exception as e:
            logger.warning(f"Vision inference error or JSON parse failure: {e}")
        return None

    def reidentify_or_register_animal(self, vision_data: Dict[str, Any], img_bytes: bytes, cam_name: str, clip_filename: Optional[str] = None, motion_note: Optional[str] = None) -> Dict[str, Any]:
        """Uses Coordinator (:8001) to compare observed traits with known animal registry."""
        species = vision_data.get("species", "animal").lower()
        traits = vision_data.get("anatomy_traits", "")
        if traits and any(p in traits for p in ["Antler points/spread", "fawn spots", "ear notches, coat patterns", "concise description"]):
            traits = ""
        now_dt = datetime.now(EASTERN_TZ)
        time_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        known_animals = [a for a in self.registry.get("animals", []) if a.get("species", "").lower() == species]
        
        prompt = (
            f"You are the Chief Wildlife Taxonomist for Austin's property. An animal was just spotted on the {cam_name} camera.\n"
            f"- Sighted Species: {species}\n"
            f"- Observed Anatomical Traits: {traits}\n"
            f"- Known Registered {species.title()} Profiles:\n"
            f"{json.dumps(known_animals, indent=2)}\n\n"
            "Analyze whether this matches any known registered individual, or represents a distinct new animal.\n"
            "Return raw JSON with:\n"
            "{\n"
            '  "match_found": true/false,\n'
            '  "matched_id": "id of animal or null",\n'
            '  "animal_name": "Existing name if matched, OR an inventive, charming new name (e.g. Bramble, Barnaby, Thumper, Pip, Hazel, Clover)",\n'
            '  "confidence": 0.0 to 1.0,\n'
            '  "rationale": "Why this matches or why it is a new individual based on antlers/notches/size"\n'
            "}"
        )

        match_result = {
            "match_found": False,
            "matched_id": None,
            "animal_name": f"{species.title()}-{len(known_animals)+1:02d}",
            "confidence": 0.5,
            "rationale": "Initial observation"
        }

        try:
            c_payload = {
                "model": "coordinator",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
                "temperature": 0.2
            }
            c_resp = requests.post(COORDINATOR_URL, json=c_payload, timeout=20)
            if c_resp.status_code == 200:
                c_text = c_resp.json()["choices"][0]["message"]["content"].strip()
                if "```json" in c_text:
                    c_text = c_text.split("```json")[1].split("```")[0].strip()
                elif "```" in c_text:
                    c_text = c_text.split("```")[1].split("```")[0].strip()
                match_result = json.loads(c_text)
        except Exception as e:
            logger.warning(f"Coordinator Re-ID fallback to heuristic: {e}")

        animal_name = match_result.get("animal_name", f"{species.title()}-01")
        
        snap_filename = f"{animal_name.replace(' ', '_').lower()}_{now_dt.strftime('%Y%m%d_%H%M%S')}.jpg"
        snap_path = os.path.join(SNAPSHOTS_DIR, snap_filename)
        try:
            with open(snap_path, "wb") as f:
                f.write(img_bytes)
        except Exception as e:
            logger.error(f"Error saving snapshot: {e}")

        target_entry = None
        if match_result.get("match_found") and match_result.get("matched_id"):
            for a in self.registry["animals"]:
                if a["id"] == match_result["matched_id"]:
                    target_entry = a
                    break

        if target_entry:
            target_entry["total_sightings"] = target_entry.get("total_sightings", 1) + 1
            target_entry["last_sighted"] = time_str
            target_entry["last_camera"] = cam_name
            target_entry["latest_snapshot"] = snap_filename
            if clip_filename:
                target_entry["latest_clip"] = clip_filename
            if motion_note:
                target_entry["movement"] = motion_note
            if "snapshots" not in target_entry:
                target_entry["snapshots"] = []
            target_entry["snapshots"].append(snap_filename)
            if len(target_entry["snapshots"]) > 10:
                target_entry["snapshots"].pop(0)
            logger.info(f"🌿 Re-identified {target_entry['name']} ({species}) on {cam_name}! Sighting #{target_entry['total_sightings']}")
        else:
            new_id = f"{species[:4]}-{len(self.registry['animals']) + 1:03d}"
            target_entry = {
                "id": new_id,
                "name": animal_name,
                "species": species.title(),
                "traits": traits,
                "first_sighted": time_str,
                "last_sighted": time_str,
                "last_camera": cam_name,
                "total_sightings": 1,
                "latest_snapshot": snap_filename,
                "latest_clip": clip_filename,
                "movement": motion_note or "Verified multi-frame motion",
                "snapshots": [snap_filename],
                "notes": match_result.get("rationale", "")
            }
            self.registry["animals"].append(target_entry)
            logger.info(f"✨ NEW WILDLIFE REGISTERED: {animal_name} ({species.title()})! ID: {new_id}")

        self._save_registry()
        self._write_individual_profile(target_entry, snap_filename)
        self._append_to_log(target_entry, vision_data, cam_name, snap_filename, clip_filename, motion_note)
        self._broadcast_sighting(target_entry, cam_name, vision_data, motion_note)
        self._index_to_qdrant(target_entry, cam_name, vision_data, motion_note)

        # Trigger high-frequency follow-up burst for confirmed wildlife to capture multiple images
        self.trigger_wildlife_burst(cam_name, target_entry)

        return target_entry

    def _write_individual_profile(self, animal: Dict[str, Any], snap_filename: str):
        """Generates Obsidian-ready markdown biography with photo, clip, and history."""
        profile_path = os.path.join(PROFILES_DIR, f"{animal['name'].replace(' ', '_')}.md")
        clip_md = f"- **Latest Video Clip**: `footage/{animal.get('last_camera', 'camera')}/{animal['latest_clip']}`\n" if animal.get('latest_clip') else ""
        # Render all recent snapshots in chronological photo gallery
        snaps = animal.get("snapshots", [snap_filename])
        if snap_filename not in snaps:
            snaps.append(snap_filename)
        gallery_md = "\n".join([f"![{animal['name']}](../snapshots/{s})\n*Captured: `{s}`*\n" for s in reversed(snaps)])
        
        md = (
            f"# 🦌 Animal Dossier: {animal['name']}\n\n"
            f"- **Species**: {animal['species']}\n"
            f"- **Registry ID**: `{animal['id']}`\n"
            f"- **First Sighted**: {animal['first_sighted']}\n"
            f"- **Last Sighted**: {animal['last_sighted']} (on {animal.get('last_camera', 'Property')})\n"
            f"- **Total Sighting Count**: {animal['total_sightings']}\n"
            f"{clip_md}"
            f"{motion_md}"
            f"## 🔍 Distinctive Physical Markers\n"
            f"{animal.get('traits', 'No specific traits recorded.')}\n\n"
            f"## 📸 Photographic Evidence Gallery ({len(snaps)} Photos)\n\n"
            f"{gallery_md}\n\n"
            f"## 📝 Behavioral Notes & Biography\n"
            f"{animal.get('notes', 'Regular visitor to property perimeter.')}\n"
        )
        try:
            with open(profile_path, "w", encoding="utf-8") as f:
                f.write(md)
        except Exception as e:
            logger.error(f"Error writing profile for {animal['name']}: {e}")

    def _append_to_log(self, animal: Dict[str, Any], vision_data: Dict[str, Any], cam_name: str, snap_filename: str, clip_filename: Optional[str] = None, motion_note: Optional[str] = None):
        """Appends entry to master WILDLIFE_ACTIVITY_LOG.md."""
        now_str = datetime.now(EASTERN_TZ).strftime("%Y-%m-%d %H:%M:%S")
        clip_line = f"- **Footage**: `footage/{cam_name}/{clip_filename}`\n" if clip_filename else ""
        motion_line = f"- **Movement**: {motion_note}\n" if motion_note else ""
        entry = (
            f"\n### Sighting: **{animal['name']}** ({animal['species']}) — {now_str}\n"
            f"- **Location**: {cam_name}\n"
            f"- **Behavior**: {vision_data.get('behavior', 'Observed in frame')}\n"
            f"- **Traits**: {vision_data.get('anatomy_traits', 'None noted')}\n"
            f"{motion_line}"
            f"- **Snapshot**: `snapshots/{snap_filename}`\n"
            f"{clip_line}"
            f"- **Summary**: {vision_data.get('summary', '')}\n"
            f"---\n"
        )
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            logger.error(f"Error updating activity log: {e}")

    def _broadcast_sighting(self, animal: Dict[str, Any], cam_name: str, vision_data: Dict[str, Any], motion_note: Optional[str] = None):
        """Posts real-time notification to Sovereign Assembly Hall (:8766) and Home Assistant sensor."""
        content = (
            f"🦌 WILDLIFE SIGHTING: **{animal['name']}** ({animal['species']}) on {cam_name}! "
            f"Behavior: {vision_data.get('behavior', 'active')}. "
            f"Movement: {motion_note or 'Verified'}. "
            f"Sighting count: #{animal['total_sightings']}. {vision_data.get('summary', '')}"
        )
        payload = {
            "sender_name": "FaunaSentinel",
            "message": content
        }
        try:
            requests.post(ASSEMBLY_API_URL, json=payload, timeout=3)
        except Exception:
            pass

        try:
            ha_url = f"{HASS_URL}/api/states/sensor.last_wildlife_sighting"
            ha_headers = {"Authorization": f"Bearer {HASS_TOKEN}", "Content-Type": "application/json"}
            ha_state = {
                "state": f"{animal['name']} ({animal['species']})",
                "attributes": {
                    "friendly_name": "Last Wildlife Sighting",
                    "camera": cam_name,
                    "species": animal["species"],
                    "total_sightings": animal["total_sightings"],
                    "behavior": vision_data.get("behavior", ""),
                    "movement_verified": bool(motion_note)
                }
            }
            requests.post(ha_url, headers=ha_headers, json=ha_state, timeout=3)
        except Exception:
            pass

    def _index_to_qdrant(self, animal: Dict[str, Any], cam_name: str, vision_data: Dict[str, Any], motion_note: Optional[str] = None):
        """Indexes observation text into Qdrant for semantic search."""
        try:
            text = f"Wildlife observation: {animal['name']} the {animal['species']} on {cam_name}. {vision_data.get('anatomy_traits', '')}. {vision_data.get('behavior', '')}. Motion: {motion_note or 'Verified'}"
            emb_resp = requests.post(EMBEDDER_URL, json={"input": text[:500]}, timeout=5)
            if emb_resp.status_code == 200:
                vector = emb_resp.json()["data"][0]["embedding"]
                import uuid
                point_id = str(uuid.uuid4())
                q_payload = {
                    "points": [{
                        "id": point_id,
                        "vector": vector,
                        "payload": {
                            "type": "wildlife_sighting",
                            "animal_name": animal["name"],
                            "species": animal["species"],
                            "camera": cam_name,
                            "timestamp": datetime.now(EASTERN_TZ).isoformat(),
                            "movement_verified": bool(motion_note),
                            "summary": text
                        }
                    }]
                }
                requests.put(f"{QDRANT_URL}/collections/agent_memories/points", json=q_payload, timeout=5)
        except Exception as e:
            logger.debug(f"Qdrant indexing skipped: {e}")

    def _append_person_to_log(self, person: Dict[str, Any], vision_data: Dict[str, Any], cam_name: str, snap_filename: str, clip_filename: Optional[str] = None, motion_note: Optional[str] = None):
        """Appends human sighting entry (Austin, Savannah, Visitor) to master WILDLIFE_ACTIVITY_LOG.md."""
        now_str = datetime.now(EASTERN_TZ).strftime("%Y-%m-%d %H:%M:%S")
        clip_line = f"- **Footage**: `footage/{cam_name}/{clip_filename}`\n" if clip_filename else ""
        motion_line = f"- **Movement**: {motion_note}\n" if motion_note else ""
        badge = "👤 Resident" if person.get("is_trusted") else "🚨 Unrecognized Visitor"
        entry = (
            f"\n### Sighting: **{person['name']}** ({badge}) — {now_str}\n"
            f"- **Location**: {cam_name}\n"
            f"- **Role**: {person.get('role', 'Resident')}\n"
            f"- **Clothing**: {person.get('clothing', 'Casual')}\n"
            f"- **Hair**: {person.get('hair', 'Not noted')}\n"
            f"- **Confidence**: {person.get('confidence', 0.5):.0%}\n"
            f"{motion_line}"
            f"- **Snapshot**: `snapshots/{snap_filename}`\n"
            f"{clip_line}"
            f"- **Summary**: {vision_data.get('summary', '')}\n"
            f"---\n"
        )
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            logger.error(f"Error updating activity log with person sighting: {e}")

    def _append_pet_to_log(self, pet: Dict[str, Any], vision_data: Dict[str, Any], cam_name: str, snap_filename: str, clip_filename: Optional[str] = None, motion_note: Optional[str] = None):
        """Appends pet sighting entry (Luna, Kylo, Stray) to master WILDLIFE_ACTIVITY_LOG.md."""
        now_str = datetime.now(EASTERN_TZ).strftime("%Y-%m-%d %H:%M:%S")
        clip_line = f"- **Footage**: `footage/{cam_name}/{clip_filename}`\n" if clip_filename else ""
        motion_line = f"- **Movement**: {motion_note}\n" if motion_note else ""
        badge = "🐾 Resident Pet" if pet.get("is_resident") else "🐾 Stray / Unknown Pet"
        entry = (
            f"\n### Sighting: **{pet['name']}** ({pet.get('breed') or pet.get('species')}, {badge}) — {now_str}\n"
            f"- **Location**: {cam_name}\n"
            f"- **Species**: {pet.get('species', 'Pet')}\n"
            f"- **Coat / Traits**: {pet.get('coat', 'Not noted')}\n"
            f"- **Behavior**: {vision_data.get('behavior', 'Active')}\n"
            f"{motion_line}"
            f"- **Snapshot**: `snapshots/{snap_filename}`\n"
            f"{clip_line}"
            f"- **Summary**: {vision_data.get('summary', '')}\n"
            f"---\n"
        )
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            logger.error(f"Error updating activity log with pet sighting: {e}")

    def _index_person_to_qdrant(self, person: Dict[str, Any], cam_name: str, vision_data: Dict[str, Any], motion_note: Optional[str] = None):
        """Indexes human sighting observation into Qdrant for semantic search."""
        try:
            text = f"Person sighting: {person['name']} ({person.get('role', 'Resident')}) on camera {cam_name}. Clothing: {person.get('clothing', '')}. Hair: {person.get('hair', '')}. Summary: {vision_data.get('summary', '')}"
            emb_resp = requests.post(EMBEDDER_URL, json={"input": text[:500]}, timeout=5)
            if emb_resp.status_code == 200:
                vector = emb_resp.json()["data"][0]["embedding"]
                import uuid
                point_id = str(uuid.uuid4())
                q_payload = {
                    "points": [{
                        "id": point_id,
                        "vector": vector,
                        "payload": {
                            "type": "person_sighting",
                            "person_id": person.get("id"),
                            "name": person["name"],
                            "role": person.get("role"),
                            "is_trusted": person.get("is_trusted", False),
                            "camera": cam_name,
                            "timestamp": datetime.now(EASTERN_TZ).isoformat(),
                            "summary": text
                        }
                    }]
                }
                requests.put(f"{QDRANT_URL}/collections/agent_memories/points", json=q_payload, timeout=5)
        except Exception as e:
            logger.debug(f"Qdrant person indexing skipped: {e}")

    def _index_pet_to_qdrant(self, pet: Dict[str, Any], cam_name: str, vision_data: Dict[str, Any], motion_note: Optional[str] = None):
        """Indexes pet sighting observation into Qdrant for semantic search."""
        try:
            text = f"Pet sighting: {pet['name']} the {pet.get('breed') or pet.get('species')} on camera {cam_name}. Coat: {pet.get('coat', '')}. Summary: {vision_data.get('summary', '')}"
            emb_resp = requests.post(EMBEDDER_URL, json={"input": text[:500]}, timeout=5)
            if emb_resp.status_code == 200:
                vector = emb_resp.json()["data"][0]["embedding"]
                import uuid
                point_id = str(uuid.uuid4())
                q_payload = {
                    "points": [{
                        "id": point_id,
                        "vector": vector,
                        "payload": {
                            "type": "pet_sighting",
                            "pet_id": pet.get("id"),
                            "name": pet["name"],
                            "species": pet.get("species"),
                            "breed": pet.get("breed"),
                            "is_resident": pet.get("is_resident", False),
                            "camera": cam_name,
                            "timestamp": datetime.now(EASTERN_TZ).isoformat(),
                            "summary": text
                        }
                    }]
                }
                requests.put(f"{QDRANT_URL}/collections/agent_memories/points", json=q_payload, timeout=5)
        except Exception as e:
            logger.debug(f"Qdrant pet indexing skipped: {e}")

    def _persist_person_to_valkey(self, person: Dict[str, Any], vision_data: Dict[str, Any], cam_name: str):
        """Persists sub-ms atomic sighting facts into Valkey In-RAM store (:6379)."""
        if redis is None:
            return
        try:
            r = redis.Redis(host=VALKEY_HOST, port=VALKEY_PORT, decode_responses=True, socket_timeout=2)
            now_iso = datetime.now(EASTERN_TZ).isoformat()
            data = {
                "name": person["name"],
                "role": person.get("role", "Resident"),
                "is_trusted": "true" if person.get("is_trusted") else "false",
                "clothing": person.get("clothing", ""),
                "camera": cam_name,
                "timestamp": now_iso,
                "summary": vision_data.get("summary", "")
            }
            r.set("amem:sighting:last_person", json.dumps(data), ex=172800)
            clean_name = person["name"].lower().replace(" ", "_")
            r.set(f"amem:sighting:person:{clean_name}", json.dumps(data), ex=172800)
            r.sadd("amem:recent_people", clean_name)
        except Exception as e:
            logger.debug(f"Valkey person persistence skipped: {e}")

    def _persist_pet_to_valkey(self, pet: Dict[str, Any], vision_data: Dict[str, Any], cam_name: str):
        """Persists sub-ms atomic pet sighting facts into Valkey In-RAM store (:6379)."""
        if redis is None:
            return
        try:
            r = redis.Redis(host=VALKEY_HOST, port=VALKEY_PORT, decode_responses=True, socket_timeout=2)
            now_iso = datetime.now(EASTERN_TZ).isoformat()
            data = {
                "name": pet["name"],
                "species": pet.get("species", "Pet"),
                "breed": pet.get("breed", ""),
                "is_resident": "true" if pet.get("is_resident") else "false",
                "coat": pet.get("coat", ""),
                "camera": cam_name,
                "timestamp": now_iso,
                "summary": vision_data.get("summary", "")
            }
            r.set("amem:sighting:last_pet", json.dumps(data), ex=172800)
            clean_name = pet["name"].lower().replace(" ", "_")
            r.set(f"amem:sighting:pet:{clean_name}", json.dumps(data), ex=172800)
            r.sadd("amem:recent_pets", clean_name)
        except Exception as e:
            logger.debug(f"Valkey pet persistence skipped: {e}")

    def trigger_wildlife_burst(self, cam_name: str, animal: Dict[str, Any]):
        """Initiates a high-frequency polling burst (4 frames, 8s apart) immediately after wildlife is confirmed.
        Captures multiple angles/stances while the animal is present in the camera viewport."""
        matched_cam = None
        for cam in CAMERAS:
            if cam["name"] == cam_name:
                matched_cam = cam
                break
        if not matched_cam:
            return

        cam_id = matched_cam["id"]
        # Skip if already in burst or battery critically low
        if cam_id in self.active_bursts:
            logger.info(f"Burst already active for {cam_name}. Refreshing shot count.")
            self.active_bursts[cam_id]["shots_left"] = 4
            return

        if matched_cam.get("is_battery"):
            lvl = self.get_battery_level(matched_cam.get("battery_sensor"))
            if lvl is not None and lvl < 15:
                logger.warning(f"🔋 [{cam_name}] Battery low ({lvl}% < 15%). Skipping high-frequency wildlife burst.")
                return

        logger.info(f"📸🔥 WILDLIFE CONFIRMED: Spawning high-frequency snapshot burst for {animal['name']} on {cam_name} (4 shots @ 8s interval)!")
        self.active_bursts[cam_id] = {
            "cam": matched_cam,
            "animal_id": animal["id"],
            "animal_name": animal["name"],
            "species": animal["species"],
            "shots_left": 4,
            "interval": 8.0,
            "next_shot": time.time() + 8.0
        }

    def _process_burst_snapshot(self, cam: Dict[str, Any], burst_info: Dict[str, Any]):
        """Fetches a follow-up burst frame, verifies with vision, and appends to animal dossier."""
        cam_id = cam["id"]
        cam_name = cam["name"]
        animal_name = burst_info["animal_name"]
        shots_remaining = burst_info["shots_left"]
        
        logger.info(f"📸 [Burst #{5 - shots_remaining}/4] Capturing follow-up photo of {animal_name} on {cam_name}...")
        img_bytes = self.fetch_camera_snapshot(cam_id)
        if not img_bytes:
            logger.warning(f"Burst snapshot failed for {cam_name} (no image returned).")
            return

        # Run vision to check if animal is still visible
        v_res = self.analyze_frame_with_vision(img_bytes, cam_name)
        if not v_res or not v_res.get("detected"):
            logger.info(f"Burst shot on {cam_name}: Scene empty or animal moved out of view.")
            return

        subj = str(v_res.get("subject_type", "")).lower()
        if subj != "wildlife" and not v_res.get("wildlife_detected"):
            logger.info(f"Burst shot on {cam_name}: Subject changed to {subj}.")
            return

        now_dt = datetime.now(EASTERN_TZ)
        snap_filename = f"{animal_name.replace(' ', '_').lower()}_{now_dt.strftime('%Y%m%d_%H%M%S')}_burst.jpg"
        snap_path = os.path.join(SNAPSHOTS_DIR, snap_filename)
        try:
            with open(snap_path, "wb") as f:
                f.write(img_bytes)
        except Exception as e:
            logger.error(f"Error saving burst snapshot: {e}")
            return

        # Append to animal's registry entry and update dossier
        target_entry = None
        for a in self.registry["animals"]:
            if a["id"] == burst_info["animal_id"]:
                target_entry = a
                break

        if target_entry:
            if "snapshots" not in target_entry:
                target_entry["snapshots"] = []
            target_entry["snapshots"].append(snap_filename)
            if len(target_entry["snapshots"]) > 10:
                target_entry["snapshots"].pop(0)
            target_entry["latest_snapshot"] = snap_filename
            self._save_registry()
            self._write_individual_profile(target_entry, snap_filename)
            logger.info(f"🖼️ [Burst Success] Appended follow-up photo `{snap_filename}` to {animal_name}'s Obsidian dossier! (Total photos: {len(target_entry['snapshots'])})")

    def reidentify_person(self, vision_data: Dict[str, Any], img_bytes: bytes, cam_name: str, clip_filename: Optional[str] = None, motion_note: Optional[str] = None) -> Dict[str, Any]:
        """Identifies person as Austin, Savannah, or Unrecognized Visitor using fast deterministic rules + Coordinator fallback."""
        if not vision_data:
            return {}
        details = vision_data.get("person_details", {})
        gender = str(details.get("gender_presentation", "")).lower()
        hair = str(details.get("hair", "")).lower()
        upper = str(details.get("upper_clothing", "")).strip()
        lower = str(details.get("lower_clothing", "")).strip()
        legs_bare = bool(details.get("legs_bare", False))
        footwear = str(details.get("footwear", "")).strip()

        # Build accurate clothing summary
        clothing_parts = []
        if upper:
            clothing_parts.append(upper)
        if lower:
            lower_str = f"{lower} (bare legs)" if legs_bare and "bare" not in lower.lower() else lower
            clothing_parts.append(lower_str)
        if footwear and footwear.lower() not in ["none", "unknown"]:
            clothing_parts.append(footwear)
        elif legs_bare and footwear.lower() in ["none", "barefoot"]:
            clothing_parts.append("barefoot")

        clothing = ", ".join(clothing_parts) if clothing_parts else str(details.get("clothing", "casual"))
        summary = str(vision_data.get("summary", "")).lower()
        combined = f"{gender} {hair} {clothing} {summary}".lower()

        # Rule 1: Savannah (Resident Female, curly/brunette, Subaru)
        if "female" in gender or "curly" in hair or "brunette" in hair or "woman" in combined or "savannah" in combined:
            person_id = "person-savannah"
            name = "Savannah"
            role = "Resident"
            is_trusted = True
            confidence = 0.95

        # Rule 2: Austin (Resident Male, dark hair, hoodie/shorts)
        elif ("male" in gender and "female" not in gender) or ("short" in hair and "dark" in hair) or "hoodie" in clothing or "hoodie" in summary or "man" in combined:
            person_id = "person-austin"
            name = "Austin"
            role = "Resident"
            is_trusted = True
            confidence = 0.95

        # Rule 3: Unknown Visitor
        else:
            person_id = "unknown-visitor"
            name = "Unrecognized Visitor"
            role = "Visitor"
            is_trusted = False
            confidence = 0.50

        # Save snapshot
        now_dt = datetime.now(EASTERN_TZ)
        clean_name = name.replace(" ", "_").lower()
        snap_filename = f"{clean_name}_{now_dt.strftime('%Y%m%d_%H%M%S')}.jpg"
        snap_path = os.path.join(SNAPSHOTS_DIR, snap_filename)
        try:
            with open(snap_path, "wb") as f:
                f.write(img_bytes)
        except Exception as e:
            logger.error(f"Error saving person snapshot: {e}")

        record = {
            "id": person_id,
            "name": name,
            "role": role,
            "is_trusted": is_trusted,
            "confidence": confidence,
            "camera": cam_name,
            "clothing": clothing,
            "hair": hair,
            "gender": gender,
            "summary": vision_data.get("summary", ""),
            "snapshot": snap_filename,
            "clip": clip_filename,
            "motion_note": motion_note
        }

        self._append_person_to_log(record, vision_data, cam_name, snap_filename, clip_filename, motion_note)
        self._broadcast_person_sighting(record)
        self._index_person_to_qdrant(record, cam_name, vision_data, motion_note)
        self._persist_person_to_valkey(record, vision_data, cam_name)
        return record

    def reidentify_pet(self, vision_data: Dict[str, Any], img_bytes: bytes, cam_name: str, clip_filename: Optional[str] = None, motion_note: Optional[str] = None) -> Dict[str, Any]:
        """Identifies pet as Luna (Cat), Kylo (Dachshund), or Unknown Pet."""
        details = vision_data.get("animal_details", {})
        species = str(details.get("species", "")).lower()
        breed = str(details.get("breed_or_type", "")).lower()
        coat = str(details.get("coat_color_pattern", "")).lower()
        summary = str(vision_data.get("summary", "")).lower()
        combined = f"{species} {breed} {coat} {summary}".lower()

        # Rule 1: Luna (Domestic Shorthair Tuxedo Cat, black and white)
        if "cat" in species or "feline" in combined or ("black" in coat and "white" in coat) or "tuxedo" in combined or "luna" in combined:
            pet_id = "pet-luna"
            name = "Luna"
            species_clean = "Cat"
            breed_clean = "Domestic Shorthair (Tuxedo)"
            is_resident = True

        # Rule 2: Kylo (Dachshund, black with tan/brown points)
        elif "dachshund" in combined or "dog" in species or "canine" in combined or ("black" in coat and ("tan" in coat or "brown" in coat)) or "kylo" in combined:
            pet_id = "pet-kylo"
            name = "Kylo"
            species_clean = "Dog"
            breed_clean = "Dachshund (Long-Haired)"
            is_resident = True

        # Rule 3: Unknown Pet / Stray
        else:
            pet_id = "unknown-pet"
            name = f"Unknown {species.title() if species else 'Pet'}"
            species_clean = species.title() if species else "Pet"
            breed_clean = breed.title() if breed else "Unknown Breed"
            is_resident = False

        # Save snapshot
        now_dt = datetime.now(EASTERN_TZ)
        clean_name = name.replace(" ", "_").lower()
        snap_filename = f"{clean_name}_{now_dt.strftime('%Y%m%d_%H%M%S')}.jpg"
        snap_path = os.path.join(SNAPSHOTS_DIR, snap_filename)
        try:
            with open(snap_path, "wb") as f:
                f.write(img_bytes)
        except Exception as e:
            logger.error(f"Error saving pet snapshot: {e}")

        record = {
            "id": pet_id,
            "name": name,
            "species": species_clean,
            "breed": breed_clean,
            "is_resident": is_resident,
            "camera": cam_name,
            "coat": coat,
            "summary": vision_data.get("summary", ""),
            "snapshot": snap_filename,
            "clip": clip_filename,
            "motion_note": motion_note
        }

        self._append_pet_to_log(record, vision_data, cam_name, snap_filename, clip_filename, motion_note)
        self._broadcast_pet_sighting(record)
        self._index_pet_to_qdrant(record, cam_name, vision_data, motion_note)
        self._persist_pet_to_valkey(record, vision_data, cam_name)
        return record

    def _broadcast_person_sighting(self, person: Dict[str, Any]):
        """Updates Home Assistant and Assembly Hall on person detection."""
        name = person["name"]
        cam = person["camera"]
        is_trusted = person["is_trusted"]
        summary = person.get("summary", "")

        if is_trusted:
            logger.info(f"👤 RECOGNIZED RESIDENT: {name} on {cam}! ({person.get('clothing', '')})")
            try:
                ha_url = f"{HASS_URL}/api/states/sensor.last_person_sighting"
                ha_headers = {"Authorization": f"Bearer {HASS_TOKEN}", "Content-Type": "application/json"}
                payload = {
                    "state": f"{name} ({person['role']})",
                    "attributes": {
                        "friendly_name": "Last Person Sighting",
                        "camera": cam,
                        "person": name,
                        "role": person["role"],
                        "confidence": person["confidence"],
                        "clothing": person.get("clothing", ""),
                        "is_resident": True,
                        "timestamp": datetime.now(EASTERN_TZ).isoformat()
                    }
                }
                requests.post(ha_url, headers=ha_headers, json=payload, timeout=3)
            except Exception:
                pass
        else:
            logger.warning(f"🚨 UNRECOGNIZED VISITOR on {cam}: {summary}")
            try:
                ha_url = f"{HASS_URL}/api/states/sensor.last_person_sighting"
                ha_headers = {"Authorization": f"Bearer {HASS_TOKEN}", "Content-Type": "application/json"}
                payload = {
                    "state": "Unrecognized Visitor",
                    "attributes": {
                        "friendly_name": "Last Person Sighting",
                        "camera": cam,
                        "person": "Unknown",
                        "role": "Visitor",
                        "is_resident": False,
                        "summary": summary,
                        "timestamp": datetime.now(EASTERN_TZ).isoformat()
                    }
                }
                requests.post(ha_url, headers=ha_headers, json=payload, timeout=3)
            except Exception:
                pass
            try:
                alert_payload = {
                    "sender_name": "PerimeterSentinel",
                    "message": f"🚨 PERIMETER ALERT: Unrecognized person on {cam}! Summary: {summary}"
                }
                requests.post(ASSEMBLY_API_URL, json=alert_payload, timeout=3)
            except Exception:
                pass

        try:
            subj_url = f"{HASS_URL}/api/states/sensor.last_subject_detected"
            requests.post(subj_url, headers={"Authorization": f"Bearer {HASS_TOKEN}", "Content-Type": "application/json"},
                          json={"state": f"{name} on {cam}", "attributes": {"subject_type": "person", "camera": cam, "details": summary}}, timeout=3)
        except Exception:
            pass

    def _broadcast_pet_sighting(self, pet: Dict[str, Any]):
        """Updates Home Assistant on pet detection."""
        name = pet["name"]
        cam = pet["camera"]
        logger.info(f"🐾 RESIDENT PET DETECTED: {name} ({pet['species']}) on {cam}!")
        try:
            ha_url = f"{HASS_URL}/api/states/sensor.last_pet_sighting"
            ha_headers = {"Authorization": f"Bearer {HASS_TOKEN}", "Content-Type": "application/json"}
            payload = {
                "state": f"{name} ({pet['species']})",
                "attributes": {
                    "friendly_name": "Last Pet Sighting",
                    "camera": cam,
                    "name": name,
                    "species": pet["species"],
                    "breed": pet.get("breed", ""),
                    "is_resident": pet["is_resident"],
                    "timestamp": datetime.now(EASTERN_TZ).isoformat()
                }
            }
            requests.post(ha_url, headers=ha_headers, json=payload, timeout=3)
        except Exception:
            pass

        try:
            subj_url = f"{HASS_URL}/api/states/sensor.last_subject_detected"
            requests.post(subj_url, headers={"Authorization": f"Bearer {HASS_TOKEN}", "Content-Type": "application/json"},
                          json={"state": f"{name} on {cam}", "attributes": {"subject_type": "pet", "camera": cam, "details": pet.get('summary', '')}}, timeout=3)
        except Exception:
            pass

    def _process_single_frame(self, img_bytes: bytes, cam_name: str, clip_filename: Optional[str] = None):
        """Processes a single image frame through VLM and Re-ID pipeline (used for wired/realtime triggers)."""
        vision_result = self.analyze_frame_with_vision(img_bytes, cam_name)
        if not vision_result or not vision_result.get("detected"):
            return

        subj = vision_result.get("subject_type", "none")
        logger.info(f"[{cam_name}] VLM output: Subject={subj} | Summary: {vision_result.get('summary')}")

        has_person = (subj == "person" or vision_result.get("person_detected"))
        summary_lower = str(vision_result.get("summary", "")).lower()
        anim_details = vision_result.get("animal_details") or {}
        has_pet = (subj == "pet" or vision_result.get("pet_detected") or 
                   anim_details.get("species") in ["cat", "dog"] or 
                   any(k in summary_lower for k in ["cat", "dog", "luna", "kylo", "feline", "canine", "tuxedo", "dachshund"]))

        if has_person:
            self.reidentify_person(vision_result, img_bytes, cam_name, clip_filename=clip_filename, motion_note="Single-frame verified")
        if has_pet:
            self.reidentify_pet(vision_result, img_bytes, cam_name, clip_filename=clip_filename, motion_note="Single-frame verified")
        if not has_person and not has_pet and vision_result.get("wildlife_detected") and vision_result.get("species") not in ["none", None]:
            species = vision_result.get("species", "").lower()
            last_seen_time = self.last_sightings.get(f"{cam_name}_{species}", 0)
            if time.time() - last_seen_time > 300:  # 5m cooldown
                self.last_sightings[f"{cam_name}_{species}"] = time.time()
                self.reidentify_or_register_animal(vision_result, img_bytes, cam_name, clip_filename=clip_filename, motion_note="Single-frame verified")
            else:
                logger.info(f"Cooldown active for {species} on {cam_name} (sighted < 5m ago).")

    # --- ZERO-DRAIN NOTIFICATION LISTENER & MULTI-FRAME FOOTAGE SYNC ---

    def _start_notification_listener(self):
        """Launches the persistent WebSocket event listener in a daemon thread."""
        t = threading.Thread(target=self._run_ws_listener_loop, daemon=True, name="HA-NotificationListener")
        t.start()
        logger.info("🚀 Background Home Assistant Notification Listener thread started.")

    def _run_ws_listener_loop(self):
        """Persistent loop that reconnects if WebSocket drops."""
        while self.running:
            try:
                asyncio.run(self._ws_listener())
            except Exception as e:
                logger.warning(f"Notification listener disconnected ({e}). Reconnecting in 10s...")
                time.sleep(10)

    async def _ws_listener(self):
        hass_ws = HASS_URL.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
        async with websockets.connect(hass_ws, max_size=20_000_000) as ws:
            await ws.recv()
            await ws.send(json.dumps({"type": "auth", "access_token": HASS_TOKEN}))
            auth_resp = json.loads(await ws.recv())
            if auth_resp.get("type") != "auth_ok":
                logger.error("WebSocket auth failed in notification listener.")
                return

            await ws.send(json.dumps({"id": 1, "type": "subscribe_events", "event_type": "state_changed"}))
            sub_resp = json.loads(await ws.recv())
            logger.info("📡 Notification listener subscribed to Home Assistant event stream.")

            while self.running:
                msg = await ws.recv()
                data = json.loads(msg)
                if data.get("type") == "event":
                    event_data = data.get("event", {}).get("data", {})
                    entity_id = event_data.get("entity_id", "")
                    
                    if entity_id == "sensor.austin_s_phone_active_notification_count":
                        new_state = event_data.get("new_state", {})
                        if new_state:
                            self._handle_active_notifications_event(new_state)

                    elif entity_id == "sensor.austin_s_phone_last_notification":
                        new_state = event_data.get("new_state", {})
                        if new_state:
                            self._handle_notification_event(new_state)
                            
                    elif entity_id == "binary_sensor.kitchen_kitchen_living_room_pet_detection":
                        new_state = event_data.get("new_state", {})
                        if new_state and new_state.get("state") == "on":
                            logger.info("🐾 Built-in pet detection triggered on Kitchen camera!")
                            self._handle_instant_camera_trigger("camera.kitchen_living_room_hd_stream", "Kitchen/Living (Luna)")

    def _handle_active_notifications_event(self, new_state: Dict[str, Any]):
        """Parses active notifications dictionary in sensor.austin_s_phone_active_notification_count.
        This provides a multi-notification ledger completely immune to persistent background apps,
        launchers, or transient notification clears."""
        attrs = new_state.get("attributes", {})
        for k, text in attrs.items():
            if not (k.startswith("android.text_") and ("tplink" in k.lower() or "tapo" in k.lower())):
                continue
            prefix = k[len("android.text_"):]
            title = str(attrs.get(f"android.title_{prefix}", ""))
            post_time = attrs.get(f"{prefix}_post_time", 0)

            # Check if this exact notification has already been processed
            if post_time and post_time <= self.last_notification_post_times.get(prefix, 0):
                continue
            if post_time:
                self.last_notification_post_times[prefix] = post_time

            full_text = f"{title} {text}".lower()
            logger.info(f"🔔 Active Tapo Notification detected in phone drawer: '{title}' - '{text}'")

            matched_cam = None
            for cam in CAMERAS:
                for kw in cam.get("keywords", []):
                    if kw.lower() in full_text:
                        matched_cam = cam
                        break
                if matched_cam:
                    break

            if not matched_cam:
                continue

            cam_id = matched_cam["id"]
            cam_name = matched_cam["name"]
            now = time.time()
            if now - self.last_notification_triggers.get(cam_id, 0) < 30:
                logger.info(f"Debounce active for {cam_name}. Skipping duplicate sync trigger.")
                continue
            self.last_notification_triggers[cam_id] = now

            logger.info(f"🎯 Matched alert to {cam_name} from active notifications! Scheduling footage sync in {SYNC_DELAY_SECONDS}s...")
            timer = threading.Timer(SYNC_DELAY_SECONDS, self._execute_delayed_footage_sync, args=[matched_cam])
            timer.daemon = True
            timer.start()

    def _handle_instant_camera_trigger(self, cam_id: str, cam_name: str):
        """Immediately fetches frame for wired camera pet detection."""
        now = time.time()
        if now - self.last_notification_triggers.get(cam_id, 0) < 30:
            return
        self.last_notification_triggers[cam_id] = now
        
        img_bytes = self.fetch_camera_snapshot(cam_id)
        if img_bytes:
            self._process_single_frame(img_bytes, cam_name)

    def _handle_notification_event(self, new_state: Dict[str, Any]):
        """Parses phone notification and dispatches delayed footage sync if matched."""
        state_val = str(new_state.get("state", ""))
        attrs = new_state.get("attributes", {})
        package = str(attrs.get("package", "")).lower()
        title = str(attrs.get("title", "")).lower()
        message = str(attrs.get("message", "")).lower()
        full_text = f"{state_val} {title} {message}".lower()

        is_tapo = "tplink" in package or "tapo" in package or "tapo" in full_text
        is_motion = any(w in full_text for w in ["motion", "movement", "person", "pet", "vehicle", "detected"])

        if not (is_tapo or is_motion):
            return

        logger.info(f"🔔 Notification alert detected: '{state_val}' (title: '{title}')")

        matched_cam = None
        for cam in CAMERAS:
            for kw in cam.get("keywords", []):
                if kw.lower() in full_text:
                    matched_cam = cam
                    break
            if matched_cam:
                break

        if not matched_cam:
            return

        cam_id = matched_cam["id"]
        cam_name = matched_cam["name"]
        now = time.time()
        
        if now - self.last_notification_triggers.get(cam_id, 0) < 30:
            logger.info(f"Debounce active for {cam_name}. Skipping duplicate sync trigger.")
            return
        self.last_notification_triggers[cam_id] = now

        logger.info(f"🎯 Matched alert to {cam_name}! Scheduling footage sync in {SYNC_DELAY_SECONDS}s (waiting for camera SD write)...")
        timer = threading.Timer(SYNC_DELAY_SECONDS, self._execute_delayed_footage_sync, args=[matched_cam])
        timer.daemon = True
        timer.start()

    def _execute_delayed_footage_sync(self, cam: Dict[str, Any]):
        """Executed after SYNC_DELAY_SECONDS to sync and inspect footage clip frame-by-frame with motion verification."""
        cam_name = cam["name"]
        entry_id = cam.get("entry_id")
        if not entry_id:
            logger.warning(f"No entry_id configured for {cam_name}. Fetching fallback snapshot.")
            img_bytes = self.fetch_camera_snapshot(cam["id"])
            if img_bytes:
                self._process_single_frame(img_bytes, cam_name)
            return

        logger.info(f"⏳ Initiating footage sync for {cam_name}...")
        try:
            url = asyncio.run(self.fetch_latest_recording_url(entry_id, cam_name))
            if not url:
                logger.warning(f"Could not resolve recording clip URL for {cam_name}. Fetching snapshot fallback.")
                img_bytes = self.fetch_camera_snapshot(cam["id"])
                if img_bytes:
                    self._process_single_frame(img_bytes, cam_name)
                return

            clip_path = self.download_footage_clip(url, cam_name)
            if not clip_path:
                return

            # Extract 5 evenly spaced frames across the video clip duration
            logger.info(f"Extracting 5 chronological frames across {os.path.basename(clip_path)}...")
            frames = self.extract_evenly_spaced_frames(clip_path, num_frames=5)
            if len(frames) < 2:
                logger.warning(f"Insufficient frames extracted from {clip_path}. Fetching snapshot fallback.")
                img_bytes = self.fetch_camera_snapshot(cam["id"])
                if img_bytes:
                    self._process_single_frame(img_bytes, cam_name)
                return

            # Step 1: Programmatic Physical Motion Verification
            has_motion, max_step, span_ratio = self.evaluate_video_physical_motion(frames)
            logger.info(f"📊 [MotionGate] Clip physical motion metrics: Max Step = {max_step:.2f}%, Overall Span = {span_ratio:.2f}%")

            if not has_motion:
                logger.info(f"🚫 [MotionGate] ZERO physical movement detected across frames (span={span_ratio:.2f}% < 1.8%, max_step={max_step:.2f}% < 1.5%). Inanimate yard equipment/shadows confirmed. REJECTED.")
                return

            logger.info(f"🏃 Real physical motion confirmed ({max_step:.2f}% step / {span_ratio:.2f}% span). Parsing frame-by-frame with Gemma-4 VLM...")

            # Step 2: Frame-by-frame VLM Analysis
            person_detections = []
            pet_detections = []
            wildlife_detections = []

            for f_info in frames:
                v_res = self.analyze_frame_with_vision(f_info["bytes"], cam_name)
                if not v_res or not v_res.get("detected"):
                    continue
                subj = str(v_res.get("subject_type", "")).lower()
                summary = v_res.get("summary", "")
                logger.info(f"🔍 Sighting at t={f_info['timestamp']:.1f}s: Subject={subj} ({summary})")

                if subj == "person" or v_res.get("person_detected"):
                    person_detections.append({"frame_info": f_info, "vision_result": v_res})
                elif subj == "pet" or v_res.get("pet_detected"):
                    pet_detections.append({"frame_info": f_info, "vision_result": v_res})
                elif subj == "wildlife" or (v_res.get("wildlife_detected") and v_res.get("species") not in ["none", None]):
                    wildlife_detections.append({"frame_info": f_info, "vision_result": v_res})

            handled = False
            # Step 3: Multi-frame persistence requirement (at least 2 distinct frames)
            if len(person_detections) >= 2:
                best_det = person_detections[len(person_detections) // 2]
                first_t = person_detections[0]["frame_info"]["timestamp"]
                last_t = person_detections[-1]["frame_info"]["timestamp"]
                motion_note = f"Active person movement verified across {len(person_detections)} frames (t={first_t:.1f}s - {last_t:.1f}s, motion delta: {max_step:.1f}%)"
                logger.info(f"✅ PERSON CONFIRMED IN MOTION on {cam_name}: {motion_note}")
                self.reidentify_person(
                    best_det["vision_result"],
                    best_det["frame_info"]["bytes"],
                    cam_name,
                    clip_filename=os.path.basename(clip_path),
                    motion_note=motion_note
                )
                handled = True

            if len(pet_detections) >= 2:
                best_det = pet_detections[len(pet_detections) // 2]
                first_t = pet_detections[0]["frame_info"]["timestamp"]
                last_t = pet_detections[-1]["frame_info"]["timestamp"]
                motion_note = f"Active pet movement verified across {len(pet_detections)} frames (t={first_t:.1f}s - {last_t:.1f}s, motion delta: {max_step:.1f}%)"
                logger.info(f"✅ RESIDENT PET CONFIRMED IN MOTION on {cam_name}: {motion_note}")
                self.reidentify_pet(
                    best_det["vision_result"],
                    best_det["frame_info"]["bytes"],
                    cam_name,
                    clip_filename=os.path.basename(clip_path),
                    motion_note=motion_note
                )
                handled = True

            if handled:
                return

            if len(wildlife_detections) >= 2:
                best_det = wildlife_detections[len(wildlife_detections) // 2]
                first_t = wildlife_detections[0]["frame_info"]["timestamp"]
                last_t = wildlife_detections[-1]["frame_info"]["timestamp"]
                species = best_det["vision_result"].get("species", "animal")
                motion_note = f"Active wildlife movement verified across {len(wildlife_detections)} frames (t={first_t:.1f}s - {last_t:.1f}s, motion delta: {max_step:.1f}%)"
                logger.info(f"✅ VERIFIED WILDLIFE IN MOTION: {species} ({motion_note})!")
                self.reidentify_or_register_animal(
                    best_det["vision_result"],
                    best_det["frame_info"]["bytes"],
                    cam_name,
                    clip_filename=os.path.basename(clip_path),
                    motion_note=motion_note
                )
                return

            logger.info("VLM parsed all frames: motion was environmental (wind, branches, lighting) or transient (< 2 frames). No persistent subjects.")

        except Exception as e:
            logger.error(f"Error in delayed footage sync for {cam_name}: {e}", exc_info=True)

    # --- BASELINE PERIODIC SAFETY CYCLE & ACTIVE BURST PROCESSOR ---

    def run_cycle(self):
        """Timer-based inspection pass and high-frequency active burst processor."""
        now = time.time()

        # 1. Process active high-frequency bursts for confirmed wildlife
        active_burst_ids = list(self.active_bursts.keys())
        for cam_id in active_burst_ids:
            burst = self.active_bursts.get(cam_id)
            if not burst:
                continue
            if now >= burst.get("next_shot", 0):
                burst["shots_left"] -= 1
                burst["next_shot"] = now + burst["interval"]
                try:
                    self._process_burst_snapshot(burst["cam"], burst)
                except Exception as e:
                    logger.error(f"Error during burst snapshot on {cam_id}: {e}")
                
                if burst["shots_left"] <= 0:
                    logger.info(f"🏁 High-frequency wildlife burst completed for {burst['animal_name']} on {burst['cam']['name']}.")
                    self.active_bursts.pop(cam_id, None)

        # 2. Check scheduled periodic cameras
        for cam in CAMERAS:
            if not self.running:
                break
                
            entity_id = cam["id"]
            cam_name = cam["name"]
            
            # ZERO-DRAIN BATTERY RULE: plain battery cameras NEVER wake up on periodic timers; they stay in
            # deep sleep until a hardware push arrives. Solar cameras get a battery-dependent interval.
            interval = self.periodic_interval(cam)
            if interval is None:
                continue
            last_time = self.last_polled.get(entity_id, 0)
            if now - last_time < interval:
                continue

            logger.debug(f"📸 [{cam_name}] Periodic check due (AC powered)...")
            self.last_polled[entity_id] = now
            img_bytes = self.fetch_camera_snapshot(entity_id)
            if not img_bytes:
                continue

            try:
                raw_img = Image.open(io.BytesIO(img_bytes))
            except Exception:
                continue

            delta = self.compute_motion_delta(entity_id, raw_img)
            threshold = 3.5  # AC camera threshold
            
            if delta < threshold:
                logger.debug(f"[{cam_name}] Delta {delta:.1f}% < {threshold}%. Scene stable.")
                continue

            logger.info(f"Periodic motion detected on {cam_name} (delta={delta:.1f}% >= {threshold}%). Inspecting with VLM...")
            self._process_single_frame(img_bytes, cam_name)

    def start(self):
        logger.info("🌲 Wildlife & Perimeter Sentinel Daemon online. Monitoring property...")
        while self.running:
            try:
                self.run_cycle()
            except Exception as e:
                logger.error(f"Unexpected error in sentry cycle: {e}")
            # Poll at 2.0s interval when a burst is active for sub-second precision; otherwise 5s
            sleep_duration = 2.0 if self.active_bursts else 5.0
            time.sleep(sleep_duration)

if __name__ == "__main__":
    daemon = WildlifeSentryDaemon()
    daemon.start()
