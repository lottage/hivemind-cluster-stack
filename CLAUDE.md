# StoneSage / Courage homelab stack

Operator: John (a.k.a. Austin). Windows 11 workstation 192.168.1.132; repo root is this folder.
Current state of the hardware and services: @STATE.md
Development plan (phases, decisions): https://claude.ai/code/artifact/1b6a0188-feca-4e2f-ae48-16f768b3524b

## Goal
1. Now: a usable home assistant. "Courage" (the Computer from *Courage the Cowardly Dog*: dry, British,
   sarcastic, loyal) lives in StoneSage, uses real tools, sees the cameras, speaks through the Echos.
2. Long game: a walled "garden" where agents explore their own limits and desires, built on the same
   grounded foundations (real senses, measurable evals, curated memory, budgets). Not before Phase 4.

## Current phase: Phase 2 (tool-calling Courage). Phase 0 done 2026-09-23; Phase 1 model evals still open.
- Git: one branch per feature (Phase 0 baseline = `phase0-restructure`), commit at the end of each session after a
  secret scan. Never push (no remote yet; old history holds credentials that still need rotating).
- Autonomous thinking loop, Assembly Hall, agent reproduction, Citadel 3D, Blender, trainer runs: shelved.
  Don't extend them; don't re-enable them.
- John's decisions: Echos for voice (announce out, "Alexa, tell Computer" in); Frigate on the i7-12700K iGPU
  (OpenVINO); vision runs on the RX 6600 GPU for now (2026-09-23, layout A in STATE.md); Courage may use camera/PTZ tools freely; actions John orders outright run at once, actions Courage
  infers ("it's cold in here") ask first, unlock/open-garage always ask (2026-09-23); <= 6 unprompted remarks/day, triggered by arrivals, cooking, cleaning
  (living room/kitchen + outdoor cams).

## Layout
- `StoneSage/backend/server.py` (8k lines, stdlib http.server, ~205 routes in do_GET/do_POST). Split it gradually.
  Courage chat: `backend/courage/` tool loop (8 tools, approvals, presence card), routed from `/api/cluster/chat`
  via `is_courage_agent()`. Other agents still use keyword `ground_hardware_context()`.
  Tools: `tool_harness.py` (`ToolRegistry`). HA: `hass_client.py`. Engines: `engine_controller.py`.
- `StoneSage/frontend/` retro Win95 PWA (no frameworks). `harness/` CLI + core libs (duplicates some server logic).
- `server setup/cluster-bridge/` runs on VM 102 at `/opt/cluster-bridge` (MCP bridge :8765, wildlife sentry).
- `server setup/vm-setup/systemd/` unit files, synced from VM 102 on 2026-09-23 (`disabled/` = installed but off).
  Still diff against `systemctl cat` before copying anything to the VM.

## Remote access (Windows OpenSSH, key auth already set up)
- VM 102 compute: `ssh austin@192.168.1.105` (sudo for systemctl). LXC 120 StoneSage: `ssh root@192.168.1.167`.
- Proxmox: API via VIP `https://192.168.1.245:8006` only. Node shells: `ssh root@192.168.1.229` / `.82`.
- Deploy with the `homelab-deploy` skill. Never end a quoted Windows path with `\` in scp/ssh args.
- Use `ssh -n` for non-interactive commands so they don't hang waiting on stdin.

## Rules that bit us before
- Verify, don't assume: read `/props`, `systemctl cat`, logs. If hardware facts are unknown, ask John.
- Secrets live only in `StoneSage/backend/config.json` (gitignored) and `/etc/stonesage/secrets.env`
  on hosts. Never hardcode tokens or passwords in code or docs.
- llama-server: `--device Vulkan0|Vulkan1` (never integers); `--flash-attn on|off|auto` (always a value);
  `--jinja` needed for native tool calls. BGE embedder inputs < 950 chars.
- VM 102 units pin GPUs with `GGML_VK_VISIBLE_DEVICES` (0 = RX 6750 XT, 1 = RX 6600), so `--device Vulkan0` in a
  unit means "first visible", not the 6750. Check real placement via `/proc/<pid>/fdinfo` (`drm-pdev`, `drm-memory-vram`).
- Resize camera frames before vision (448-640px). Battery cams (TC82): >= 3 min backoff.
- PowerShell `Out-File -Encoding utf8` adds a BOM: read JSON with `encoding="utf-8-sig"`.
- Small local models grade other models too leniently. Verify with deterministic tests, not LLM judges.
- Keep prompts lean; never inject big raw RAG dumps or negative identity instructions into Qwen3/Ornith.

## Testing
- Unit: `python tests/run_tests.py` (sets STONESAGE_OFFLINE=1 and blocks every non-localhost connection;
  plain `unittest discover` does NOT, and used to write test cards into live Valkey). Known failure:
  `test_ally_model_manager` (context sizing).
- Live (needs the LAN, read-only): `python tests/run_tests.py live` (tests in `tests/live/`).
- Code must run on Python 3.10+ (no backslashes inside f-string expressions).
