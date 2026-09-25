# StoneSage Stack: Current State

> Single source of truth for what is actually deployed. Update it from live output
> (`server setup/phase0_vm102_report.sh`, llama.cpp `/props`), never from memory.
> Philosophy and history docs (COMPANION_MANIFESTO, COLLECTIVE_SOUL_FOUNDATION,
> PROJECT_MASTER_PASSDOWN) are background reading, not operational truth.

Last updated: 2026-09-23 (node IPs from the Proxmox `/cluster/status` API; were wrong before)
Previously: 2026-09-23 13:20 EDT (VM 102 from `phase0_vm102_report.sh`, `systemctl show`, per-process VRAM from amdgpu fdinfo, and a benchmark; all services from StoneSage `/api/health/all`)

## Goal (current)
A usable home assistant: Courage (tool-calling, camera-aware, voice via Echo) inside StoneSage.
Long game: a walled "garden" where agents explore their own limits, built on the same grounded foundations.
Plan: https://claude.ai/code/artifact/1b6a0188-feca-4e2f-ae48-16f768b3524b

## Hosts
| Host | IP | Role |
| --- | --- | --- |
| Proxmox API | 192.168.1.245:8006 | Cluster API (any node serves it; .245 is bigserv) |
| pve (node 1) | 192.168.1.222 | i7-12700K, RX 6750 XT 12 GB + RX 6600 8 GB (Navi 23, reported as non-XT); UHD 770 iGPU free (reserved for Frigate) |
| VM 102 ubu | 192.168.1.105 | LLM engines, cluster MCP, wildlife sentry, Valkey |
| LXC 117 qdrant | 192.168.1.112:6333 | Vector DB |
| bigserv (node 2) | 192.168.1.245 | Hosts HA OS VM 103 (192.168.1.82:8123) and app LXCs |
| LXC 120 stonesage | 192.168.1.167:8888 | StoneSage cockpit (+ :8080 redirect, HTTPS for mic) |
| LXC 121 voice | 192.168.1.121 | Whisper :8200 / :10300, Kokoro :8300, Piper :10200 |
| LXC 116 couchdb | 192.168.1.230:5984 | Obsidian LiveSync |
| LXC 128 frigate (on pve) | 192.168.1.150 | Frigate 0.18.0 (Docker): UI :8971 (auth), API :5000 (LAN), go2rtc :1984/:8554/:8555 |

## LLM engines (VM 102)
GPU pinning is done by `Environment=GGML_VK_VISIBLE_DEVICES=N` in each unit, so every unit says
`--device Vulkan0` but that means "first visible device": VISIBLE=0 is the RX 6750 XT, VISIBLE=1 is the RX 6600.
Layout "A" installed 2026-09-23 12:50 (pre-change units: `/root/unit-backup-2026-09-23/` on VM 102).

| Port | Role | Model (live /props) | GPU (real) | ctx per slot × slots | VRAM |
| --- | --- | --- | --- | --- | --- |
| 8001 | Coordinator / Courage | qwen3-14b-q4_k_m + qwen3-0.6b-q8_0 draft, KV q4_0 | RX 6750 XT (VISIBLE=0) | 6144 × 2 (`-c 12288 -np 2`) | 8.96 GB |
| 8002 | Worker | qwen2.5-coder-3b-instruct-q5_k_m, KV q8_0 | RX 6750 XT (VISIBLE=0) | 4096 × 2 | 2.35 GB |
| 8003 | Embedder | bge-large-en-v1.5 f16 (inputs < 950 chars) | RX 6600 (VISIBLE=1) | 512 × 4 | 0.59 GB |
| 8004 | Vision | qwen2.5-vl-7b-instruct q4_k_m + mmproj f16 | RX 6600 (VISIBLE=1), `-ngl 99` | 4096 × 1 | 6.44 GB |

VRAM used: RX 6750 XT 11.36 / 12.27 GB; RX 6600 7.05 / 8.18 GB. No GTT (system RAM) spill.
Stress test (both coordinator slots at 5.2k tokens + both worker slots + vision at once): no errors, no restarts.

Benchmark (`gpu_bench.py`, 160-token generation, 640×360 camera frame):
| | Before (12:40) | Layout A |
| --- | --- | --- |
| Coordinator, 1 request | 41.8 tok/s | 41.4 tok/s |
| Coordinator, 2 parallel | 38.3 tok/s each | 38.6 tok/s each |
| Worker | 3.2 tok/s (1 GB spilled to RAM) | 126 tok/s |
| Vision, fresh frame | 5.9 s | 2.9 s |

Before layout A, worker + embedder + vision all sat on the RX 6600 (~1.7 GB spilled to system RAM) and
vision crashed at 12:28 with `ggml_vulkan: device lost`.
Fallback layout "B" if the 6750 ever runs out: worker to CPU (`-ngl 0`), coordinator alone on the 6750.
Native tool calling works on 8001: this llama.cpp build enables `--jinja` by default (verified 2026-09-23).
`llama-moe` (Ornith 35B across both GPUs, :8001) is installed but disabled.

## Services
| Service | Status (intended) |
| --- | --- |
| llama-coordinator / worker / embed / vision-server | running |
| cluster-mcp (:8765) | running. Thinking loop no longer auto-starts (`AUTONOMOUS_AUTOSTART=1` to enable); stopped at cycle 1717. Repo and live `mcp_server.py` reconciled 13:15 (md5 e0f0f82b…). Reads `HASS_*` from `/etc/stonesage/secrets.env` |
| agent-assembly (:8766) | stopped + disabled 2026-09-23 (code kept) |
| wildlife-sentry | running; canonical source is `server setup/cluster-bridge/wildlife_sentry_daemon.py` (live = repo since 2026-09-24). Reads `HASS_*` from `/etc/stonesage/secrets.env` via drop-in `wildlife-sentry.service.d/secrets.conf`; the live script had the HA token hardcoded until then (pre-change copy `/opt/cluster-bridge/wildlife_sentry_daemon.py.bak-2026-09-24`, 600: delete after rotating) |
| valkey | running |
| pve-watchdog (LXC 120) | running, armed (power-cycles pve via Kasa plug .109 after 120 s of all probes failing). Probes pve .222 + VM 102; source `server setup/watchdog/` (live md5 dd0555a3…, 2026-09-23). Tokens from `/etc/stonesage/secrets.env` |
| stonesage + stonesage-ws (LXC 120) | running; `/api/health/all` live since 13:05. `stonesage-ws` only polls loop status, makes no LLM calls |

VM 102 memory 26000 -> 22528 MB on 2026-09-24 (room for Frigate on pve; pre-change conf `/root/102.conf.bak-2026-09-24-frigate`
on pve). VM 102 ignores ACPI shutdown (no guest agent): power it off from inside (`sudo systemctl poweroff`), not `qm shutdown`.
Boot race found on that reboot: llama-coordinator started 1 s before amdgpu had the 6750 XT up and silently ran on CPU
(0.8 tok/s, /health still 200). Fix: `/usr/local/bin/wait-for-gpus.sh` (repo `server setup/vm-setup/`) as ExecStartPre via
drop-in `<unit>.service.d/wait-gpus.conf` on llama-coordinator, llama-worker, llama-embed, vision-server. Waits until Vulkan
sees as many AMD GPUs as the PCI bus has (max 90 s).

## Frigate (Phase 3, LXC 128 on pve, 2026-09-24)
Unprivileged Debian 13 LXC, 4 cores, 3 GB, 64 GB, `dev0: /dev/dri/renderD128` (UHD 770). Docker (Debian packages), compose
in `/opt/frigate`; repo `server setup/frigate/` (docker-compose.yml, config.yml with `version: 0.18-0` so Frigate does not
rewrite it). Secrets `FRIGATE_*` in `/etc/stonesage/secrets.env` on LXC 128 (Tapo camera account, HA user `frigate` for MQTT).
- Detector: OpenVINO on GPU, SSDLite MobileNet v2, 5.4 ms/inference; iGPU ~2.4 % with one camera; Frigate ~0.9 GB RAM.
- MQTT to Mosquitto on HA (.82:1883), `frigate/available online` verified.
- Cameras: kitchen_living_room (C260 .146; stream2 h264 1280x720 detect at 5 fps, stream1 HEVC 4K record, alerts 7 d,
  detections 3 d, snapshots 14 d). Driveway TCW90 (.228) is solar and has no RTSP server (554 closed): stays in
  wildlife_sentry. TC82 battery cams (.214, .130) stay on the Tapo push path.
- Tapo locks the RTSP login out after repeated failures: stop Frigate before retrying a bad password.
- Presence service (live 2026-09-24, `StoneSage/backend/frigate_presence.py`): StoneSage listens to Frigate's websocket
  (`ws://192.168.1.150:5000/ws`, same payloads as MQTT; no credentials) and replays `/api/events?limit=100` on start.
  Identity: Frigate sub_label (face) wins, else `config.json frigate.identities` (cat -> luna, dog -> kylo); a person
  without a face match is "someone" (card: "A person, not identified"). An event without end_time = "in view now".
  `_courage_presence()` merges Frigate over the hub per identity (newest wins) on every read. Status:
  `GET /api/frigate/presence`. Verified live: "Where's Kylo?" answered in 5.4 s from a 4.5-min-old Frigate sighting (no
  camera look). In memory only (no Valkey keys or HA sensors from Frigate yet).
- camera_look via Frigate (live 2026-09-24, `_courage_camera_look` in server.py, `config.json frigate.cameras` maps HA
  entity -> Frigate camera): asks Frigate what is in view (`/api/events?in_progress=1`, ~0.1 s), names it, and runs the
  VLM on Frigate's `latest.jpg` (~0.1 s) instead of an HA snapshot (~1.5 s). The VLM is skipped only for presence_now's
  stale-sighting look (`people_only=True`) when Frigate sees nobody. camera_look itself always runs the VLM: a live eval
  showed Qwen3-14B does not reliably ask for a "full" look on object questions (package, stove), and Frigate only tracks
  people/dogs/cats, so a skipped look would answer wrong. Frigate unreachable -> old HA snapshot path.
  Live: object question 5.3 s end to end; tool choice unchanged (42/42, 41/42).
- Live cameras (2026-09-24): F5 Smart Home & CCTV, Courage card, tab [📹 LIVE CAMERAS] next to [👥 RESIDENTS & PETS].
  WebRTC from go2rtc (sub stream, H.264 720p); StoneSage only relays the SDP (`POST /api/cameras/webrtc`, stream must be
  in `GET /api/cameras/live`), media goes go2rtc :8555 -> browser, so it also works from the HTTPS page (not yet tried on
  :8443/phone). Streams close when the tab is switched or the page is hidden. Verified in the browser: 1280x720 at
  24 fps, audio + video. `config.json frigate.go2rtc_url`.
  Residents & Pets now reads the merged hub + Frigate view (`/api/presence/status` = `_courage_presence()`); Frigate
  sightings show their event snapshot via `GET /api/frigate/snapshot/<event_id>` and an extra "Someone" card.
- LIVE tab tiles (2026-09-25, `backend/camera_ui.py`, `config.json camera_ui` keyed by HA camera entity): kitchen =
  WebRTC (Frigate sub stream); driveway TCW90 = WebRTC from go2rtc `tapo://` (port 8800, TP-Link cloud password as
  `FRIGATE_TAPO_CLOUD_PASSWORD` on LXC 128; not a Frigate camera, so go2rtc only opens it while someone watches; HA's
  HLS for it failed ~half the time: "Error muxing first keyframe"); side/back yard = snapshot + Refresh, at most one
  camera wake per `min_refresh_s` (180 s; driveway 60 s), frames shrunk to 640 px. PTZ arrows + presets on kitchen and
  driveway via HA `button.<ptz>_move_*` / `select.<ptz>_move_to_preset`, preset names read live from HA (driveway's is
  "Driveway " with a trailing space; `camera_scan` now uses HA's spelling too). Driveway camera clock is hours off.
  WebRTC from John's phone failed: Firefox 156 on Android 16 sends no ICE checks at all (`req=0` on every pair;
  Android's local-network permission); Chrome on the same phone works. Fallback (2026-09-25): if WebRTC is not
  connected within 6 s, the tile plays `GET /api/cameras/mp4?stream=` = go2rtc's fragmented MP4 (H.264 copied, no
  transcoding, video only) relayed by StoneSage over the page's own connection, and the browser remembers it
  (`localStorage stonesage.live.mp4`). Measured: kitchen sub ~250 kbit/s (720p, 24 fps), driveway ~1.6 Mbit/s
  (1296p, ~15 fps). Failed WebRTC attempts still post ICE stats to `/api/cameras/webrtc-report`. The temporary
  `go2rtc: log: webrtc: debug` in Frigate's config never logged anything; remove it at the next Frigate change.
- LIVE quality menu per tile (2026-09-25, remembered per browser): Auto (WebRTC, MP4 if blocked) | WebRTC | MP4 |
  MP4 + sound (go2rtc `mp4=flac`) | Low data 720p (driveway: go2rtc `driveway_front_door_720`, ~450 kbit/s) | HD 1080p
  (kitchen: `kitchen_living_room_1080` from the 4K HEVC stream). Variants are go2rtc `ffmpeg:` sources with CPU libx264,
  only while watched (+~10% / +~33% of a core). GPU encoding did not work: `#hardware=vaapi` lacks the device,
  scale_vaapi runs out of surfaces on the tapo stream, and `exec:` sources are blocked by Frigate 0.18 (would need
  GO2RTC_ALLOW_ARBITRARY_EXEC=true; go2rtc's API has no auth, so not enabled). Frigate formats go2rtc streams with
  str.format: a literal `{x}` must be written `{{x}}` or go2rtc crash-loops (KeyError).
- PTZ patrol (2026-09-25, `backend/patrol.py`, `config.json patrol`, LIVE tab line "🛡️ Patrol" + "Sweep now"):
  every 15 min per PTZ camera: 3 x 120 deg left to the end stop, then 30 deg steps right with a frame each until the
  picture stops changing (right end stop) or 9 frames, then home preset (kitchen "Living Room", driveway "Doors").
  Vision model gets each frame (kitchen only when Frigate tracks someone) and names known profiles (JSON, names
  checked); sightings merge into presence as source "patrol". Kitchen pauses while Austin or Savannah is home
  (`person.austin` GPS; Savannah has no HA tracker, so camera sightings within 90 min); driveway battery-gated
  (daylight and >= 60 % -> 15 min, else hourly, < 30 % never). A camera moved by hand is left alone for 5 min.
  Routes: `GET /api/patrol/status`, `GET /api/patrol/frame?entity=&i=`, `POST /api/patrol/run {entity}`.
- Presence corrections (2026-09-25, `backend/presence_corrections.py`, cards in Residents & Pets): "✗ Wrong" and
  "Correct as ▾" (+ New profile). Frigate sightings: false_positive / sub_label; correcting to a person moves that event's
  face attempts into Frigate's face library (face_recognition enabled, model small, library empty until corrections).
  Sentry sightings: `wildlife_admin.py` on VM 102 (/opt/cluster-bridge, args on stdin) renames the snapshot prefix or
  moves it to `wildlife/rejected/`, logs `wildlife/corrections.jsonl`; a person correction also uploads the snapshot to
  Frigate's face library. Profiles = `wildlife/known_entities.json` (backup per write); the sentry re-reads it on change,
  the hub matches the activity log by snapshot timestamp so renames keep camera/activity. Identity key everywhere:
  `norm_name` ('Aunt May' -> 'aunt-may'). Deployed; no real correction made yet (first one is John's).
  Solar driveway timer polling stays OFF (`solar_poll_interval` returns None) until John picks thresholds.
- Still open (Phase 3): commentary engine, HA Frigate integration.

## A-MEM (Valkey :6379 on VM 102)
248 cards on 2026-09-23. Hardware, topology and loop-status cards were rewritten to match this file,
a `cluster.hardware.vision` card was added, and 3 `aevu-test-gen2` test cards were removed. The seed text lives in
`server setup/cluster-bridge/amem_engine.py` and `harness/data_fabric/valkey_amem.py` (core cards; `core_topology` is
built from the live system profile). Update both when hardware changes.
`amem_engine.py` seeds only when an `AMEMEngine` is constructed, and its only caller is the disabled Assembly Hall, so
`cluster-mcp` restarts do NOT re-seed. To apply seed edits on VM 102:
`cd /opt/cluster-bridge && /opt/cluster-env/bin/python3 -c 'from amem_engine import AMEMEngine; AMEMEngine()'`.
Done 2026-09-23 20:13 for the node-IP fix (`cluster.topology.management_vip` now says pve .222 / bigserv .245;
previous engine at `/opt/cluster-bridge/amem_engine.py.bak-2026-09-23-nodeips`). No card mentions .229 any more.
Pre-change backup of all 250 cards: `_backups/valkey_cards_backup_2026-09-23.jsonl` (gitignored; old engine at
`/opt/cluster-bridge/amem_engine.py.bak-2026-09-23`).
85 `agent_contract` cards (agent reproduction) and ~110 `curated_*` cards (thinking loop) remain untouched.

## Secrets
Real values live only in `StoneSage/backend/config.json` (gitignored) and `/etc/stonesage/secrets.env`
on each host (template: `server setup/secrets.env.example`). Nothing secret goes in code or docs.
VM 102: `/etc/stonesage/secrets.env` (root, 600) holds `HASS_URL`/`HASS_TOKEN`; `cluster-mcp.service` loads it via `EnvironmentFile=` (no inline token).
LXC 120: `/etc/stonesage/secrets.env` (root, 600) holds `PVE_TOKEN`/`HASS_TOKEN`; `pve-watchdog.service` loads it via
`EnvironmentFile=-` (2026-09-23). The live watchdog script had both tokens hardcoded as fallbacks until then; the pre-change copy
(still holding them) is in `/root/pve-watchdog-backup-2026-09-23/` on LXC 120. Delete it once the tokens are rotated.
**Rotate** the HA long-lived token, the Proxmox `StoneSage` API token and the CouchDB/config password:
they appear in local git history (commits 67fe717..fb5e327) and sat in plain text in the live LXC 120 watchdog until 2026-09-23.

## Live system profile (2026-09-23)
Hardware, model and engine labels are no longer written in code. Sources, in order:
- `server setup/cluster-bridge/hw_probe.py` on VM 102 (`/opt/cluster-bridge/hw_probe.py`, run as `sudo -n python3` over SSH):
  GPU names (vulkaninfo), VRAM (sysfs), engine per GPU (fdinfo), engine flags and systemd unit (cmdline/cgroup);
  `--models` reads every GGUF header (architecture, trained context, layers, KV heads, size label).
- `StoneSage/backend/system_profile.py` + `GET /api/system/profile` (30 s cache, `?fresh=1`): labels like "Qwen3 14B · RX 6750 XT".
- Web UI `js/profile.js` (page load, every minute, 3/15/45 s after any engine change), harness `fleet_config.label()/gpu()`,
  Courage's prompt ("You run on ..."), A-MEM `core_topology`/`core_hierarchy` cards, Ollama `/api/tags`, telemetry, engine settings.
- The user's own devices (edge nodes like the ROG Ally, workstation) and their specs live in `config.json` `harness_instances`
  (`"hardware": {...}`, `"engine": true`). ROG Ally = original Ally, Ryzen Z1 Extreme, 16 GB (not an Ally X).
- Preset "cluster mode" switching (`switch_cluster_mode.py`) is retired (HTTP 410): it rewrote units unreviewed and its presets
  named models that are no longer loaded. Still hardcoded (shelved, not extended): Citadel 3D, trainer/HF browser, thinking-loop topics.

## Model Loader (Engine Studio → Engine Console → 🚀 MODEL LOADER, 2026-09-23)
Replaces the old "Parameters & Sampling" and "VRAM Sizer & Models" tabs (their HTML is still in index.html, hidden,
until `harness.js`/`engine_studio.js` are retired). Backend `model_loader.py` + `engine_options.py`, routes `/api/loader/*`.
- Targets: every engine on the inference host (embedder locked) and every LM Studio node in `harness_instances`.
- Library per node: GGUF headers on VM 102; LM Studio `/api/v1/models` on edge nodes.
- Options: every flag of the installed llama-server build, parsed from its `--help` (220 options; re-read when the build
  changes); LM Studio's 8 load fields, found by probing its strict validator. Limits narrowed to the model and hardware.
- Memory plan against the chosen GPU(s) or unified RAM; calibrated by the live fdinfo figure when the model is already loaded.
- Apply: diff of the unit, token-checked apply, backup `<unit>.bak-loader-<ts>`, restart, /health + /props check,
  automatic rollback. `--metrics`, `--slots`, `--props` cannot be removed (StoneSage reads them). Not yet exercised on a
  live engine (first real apply is John's).
- Engine Profiles (live 2026-09-24, `backend/engine_profiles.py`, routes `/api/engine-profiles[/job|/apply]`, strip at the
  top of the Model Loader): named "which model on which target" bundles from `config.json engine_profiles`, applied one
  target at a time through the loader's preview + apply (so the same backup/rollback). A profile only touches the
  targets it lists; sizing it leaves out is copied from the live engine; a target already running the model is skipped;
  a failing target does not stop the rest (job status `partial`). `min_phase` gates a profile on `config.json project_phase`
  (live: 2). Profiles live: `courage_default` (= current layout, shows "live"), `ally_coding` (no model picked yet),
  `ally_agents_free` (min_phase 4). Verified live with a no-op apply of `courage_default` (both targets skipped, no restart).
  Live config pre-change: `/opt/stonesage/backend/config.json.bak-engine-profiles-20260924-080452` on LXC 120.

## Boost: free extra inference (branch `boost-free`, 2026-09-24, NOT deployed yet)
`StoneSage/backend/boost/` pools free cloud sources behind one router. Local :8001 stays the default and the last fallback.
- Sources (free tiers, no card): Groq and Cloudflare Workers AI (tier `no_training`), Gemini API free, OpenCode Zen free models,
  OpenRouter `:free` (tier `training`), plus opt-in edge nodes (`harness_instances[].boost: true`, tier `local`).
  Limits are defaults in `boost/providers.py`, overridable in `config.json boost.providers`; 429s set cooldowns.
- Egress (John's tiered rule): home text only to `local`/`no_training`; `training` gets general/code only; pictures and
  secrets never leave. A deterministic scan (`boost/egress.py`) raises the class (HA entity ids, LAN IPs, family/pet/camera
  names, tokens). Boost chat gets no A-MEM, hardware grounding, RAG or tool registry.
- Surfaces, each off by default (`config.json boost.surfaces`): chat (topbar model menu "⚡ Boost"), courage (`think_harder`
  tool), loops (harness `/node use boost` via the LAN-only proxy `/api/boost/v1/chat/completions`), workspaces.
  `boost.loop_share` (0.5) caps background use of each daily quota. UI: Engine Console → ⚡ BOOST.
- Frontier worker (`server setup/cluster-bridge/frontier_worker.py`, unit `frontier-worker.service`, VM 102 :8770): John's
  Claude Code / Gemini CLI logins run tasks in scratch clones and return a diff; 10 jobs/engine/day; no MCP, scrubbed env.
  Not installed yet (needs the CLIs installed and John's own login as user `frontier`).
- `GET /api/config` now masks secret fields (`backend/config_mask.py`); POSTs ignore masked values.
- Keys: `/etc/stonesage/secrets.env` on LXC 120 (drop-in `server setup/stonesage.service.d/secrets.conf`) or config.json.

## Known issues
- Qdrant (2026-09-24): the two `home_automation_registry` device-map points were corrected in place (backup
  `_backups/qdrant_registry_points_backup_2026-09-24.json`). Do NOT re-run `backup_to_qdrant.py`: it upserts with random
  ids and duplicates every document. `codebase_knowledge` still holds 25 stale file snapshots (old IPs, and old layouts
  such as "Ubuntu VM at .229" or MCP at .229:8765); it needs a re-index from current files, not an IP swap.
- **Secret in Qdrant**: the current HA long-lived token is stored in plain text in 4 points (`codebase_knowledge`,
  `companion_profile`, `obsidian_brain`, `obsidian_vault`), ingested from the Obsidian notes `Tokens.md` and
  `Junk/Tokens - Logins.md`. Any RAG query can surface it. Rotate the HA token, remove those points, and exclude
  credential notes from vault ingestion.
- `ws_broker.py` banner text still describes the old topology.
- `thinking_state.json` on VM 102 still says `is_running: true` (written before the old process was killed); the live
  `autonomous_thinking_status` tool correctly reports false.
- `cluster-mcp` takes ~90 s to stop (hits systemd's stop timeout, then SIGKILL).
- Courage chat (agent `courage-computer` and aliases) now runs the `backend/courage` tool loop (live 2026-09-23):
  tool choice 41/42 single-turn and mid-conversation, decision p50 0.85 s. Actions (HA calls, phone notify to
  Austin, Echo announcements) run at once when ordered outright; inferred ones, unlocks and opening covers wait for a
  "yes" (`is_direct_command` in `courage/tools.py`). "Where is X" is one step: `presence_now(who)` looks through the
  camera itself when the sighting is > 10 min old. Bare on/off orders for a uniquely named light/lamp/plug/fan
  skip the LLM (`courage/reflex.py`; replaces the harness System-1 path, whose prototypes named nonexistent entities).
  Server-infrastructure plugs are never switched off. Web chat shows Yes/No buttons for approvals.
  HA: StoneSage's Ollama API (`/api/tags`, `/api/chat` on :8888) offers model `courage:latest` = the same tool loop
  (one approval slot per calling host). HA (2026-09-23 via API): Ollama entry `http://192.168.1.167:8888` with agent
  `conversation.courage`; new assist pipeline "Courage" (faster-whisper STT, Piper `en_GB-alan-medium`, local intents
  first) is the preferred pipeline. The old Ollama entry `:8080` (only 302-redirected, POST failed) and its pipeline
  "Local Homelab Voice Stack" were deleted the same day. Pre-change backup: `_backups/ha_assist_backup_2026-09-23.json`.
  Phone approvals (2026-09-24, `courage/push_approvals.py`): an approval raised in an HA conversation also goes to Austin's
  phone as a notification with Yes/No buttons; StoneSage listens on HA's websocket for `mobile_app_notification_action`
  (log line "listening for approval taps from the phone"). Policy `config.json courage.push_approvals`: voice (default) |
  always | never. Learned phrasings (`LearnedReflexes`, `/opt/stonesage/data/courage_reflexes.json`, list at
  `GET /api/courage/reflexes`, drop with `POST /api/courage/reflexes/forget {key}`): a direct on/off order the LLM resolved
  (exactly one action, no timers/compounds) is replayed without the LLM next time. Web chat shows the tool's status text.
  Phase 2 checklist complete. Other agents still use keyword grounding and keyword-triggered device actions.
- Camera questions were 15-100 s; vision is now ~3 s per frame on GPU, so PTZ settle and snapshot fetch dominate. Frigate planned (Phase 3).
- Night motion from spider webs on outdoor cams.
- Tests: `python tests/run_tests.py` (unit, LAN blocked) = 197 tests, 1 known failure (`test_ally_model_manager` context sizing).
  `python tests/run_tests.py live` = read-only checks against the real stack.
- Git: Phase 0 baseline (b3b5ebb), Phase 2 and the node-IP fix are merged into `main` (2026-09-24); `phase2-courage-tools`
  tracks `main`. No remote.
  Submodule `server setup/obsidian-vault-cli` has uncommitted changes of its own. Snapshot: `_backups/pre-phase0-2026-09-23.tgz`.
