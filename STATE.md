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
| wildlife-sentry | running; canonical source is `server setup/cluster-bridge/wildlife_sentry_daemon.py` |
| valkey | running |
| pve-watchdog (LXC 120) | running, armed (power-cycles pve via Kasa plug .109 after 120 s of all probes failing). Probes pve .222 + VM 102; source `server setup/watchdog/` (live md5 dd0555a3…, 2026-09-23). Tokens from `/etc/stonesage/secrets.env` |
| stonesage + stonesage-ws (LXC 120) | running; `/api/health/all` live since 13:05. `stonesage-ws` only polls loop status, makes no LLM calls |

## A-MEM (Valkey :6379 on VM 102)
248 cards on 2026-09-23. Hardware, topology and loop-status cards were rewritten to match this file,
a `cluster.hardware.vision` card was added, and 3 `aevu-test-gen2` test cards were removed. The seed text lives in
`server setup/cluster-bridge/amem_engine.py` (re-seeded when `cluster-mcp` starts) and
`harness/data_fabric/valkey_amem.py` (core cards). Update both when hardware changes.
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

## Known issues
- `/api/cluster/telemetry` in `server.py` and the `ws_broker.py` banner text hardcode old topology (16k ctx, "RX 6600 XT",
  Ornith models). The top-bar badge now uses `/api/health/all` instead.
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
  Other agents still use keyword grounding and keyword-triggered device actions.
- Camera questions were 15-100 s; vision is now ~3 s per frame on GPU, so PTZ settle and snapshot fetch dominate. Frigate planned (Phase 3).
- Night motion from spider webs on outdoor cams.
- Tests: `python tests/run_tests.py` (unit, LAN blocked) = 121 tests, 1 known failure (`test_ally_model_manager` context sizing).
  `python tests/run_tests.py live` = read-only checks against the real stack.
- Git: Phase 0 baseline committed 2026-09-23 on branch `phase0-restructure` (b3b5ebb); not merged to `main`, no remote.
  Submodule `server setup/obsidian-vault-cli` has uncommitted changes of its own. Snapshot: `_backups/pre-phase0-2026-09-23.tgz`.
