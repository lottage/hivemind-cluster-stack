# Review of the stack-limits handoff against the live stack (2026-09-25)

The files in this folder are John's design handoff from another Claude conversation, kept as written
(`ai-stack-handoff.md` + four drafts). This note checks each section against what is actually deployed
(STATE.md, live `/metrics`, VM 102 sysfs) and says what changes before any of it is built. It feeds
**Phase 6** in the plan doc and CLAUDE.md. Nothing here is deployed.

## Facts checked live (2026-09-25)

| Handoff says | Live | Consequence |
| --- | --- | --- |
| Run `gpu_idle_collector.sh` on the Proxmox host; amdgpu sysfs is there | Both GPUs are passed through to VM 102 (vfio). The counters are in VM 102: `card0` = 0000:01:00.0 (RX 6750 XT, 11.97 GB VRAM used), `card1` = virtual display, `card2` = 0000:02:00.0 (RX 6600, 7.39 GB used) | The collector runs in VM 102. The script's `0 -> 6750, 1 -> 6600` map would label the virtual display as the worker GPU. Map by PCI slot, as `hw_probe.py` already does |
| Roles: coordinator on the 6750, worker on the "6600 XT" | Layout A: coordinator + worker share the 6750 XT; embedder + vision share the RX 6600 (non-XT) | Idle means per GPU, and each GPU has two engines |
| Metric `llamacpp_requests_processing` | `llamacpp:requests_processing` (colon) on :8001, :8002, :8004; the embedder :8003 exports no `/metrics` | The recording rules as written never match, so `safe_to_finetune` would never be true |
| Prometheus + node_exporter | Neither is installed anywhere (node_exporter inactive on VM 102) | Metric tracking needs a home: a small Prometheus LXC, or StoneSage's own poller |
| Push channel undecided | HA companion app push to Austin's phone with Yes/No actions is live (`courage/push_approvals.py`) | Recommend that channel. The watch (Phase 7) mirrors those notifications and adds replies |

## Section by section

**1. LiteLLM gateway.** Boost (`backend/boost/`, live since today) already is an OpenAI-compatible router,
with sources, quotas, 429 cooldowns and fallback to local, behind the LAN-only `/api/boost/v1/chat/completions`.
A second router would duplicate it. Two points in the draft also conflict with John's rules:
- The `local-coordinator -> frontier-director` fallback sends home text to Gemini's free tier, which trains on its inputs
  (tier `training` in `boost/providers.py`). John's egress rule sends home text only to `local`/`no_training`.
  Any fallback must go through Boost's `egress.classify` first.
- `host: 0.0.0.0` contradicts the "Tailscale interface only" comment above it.
The guardrails already exist upstream: frames are resized to <= 640 px before every vision call, and the
embedder callers slice to < 950 chars (`qdrant_brain.py`).
**Proposal:** no LiteLLM for now. Add per-request metrics (latency, tokens, source, class) to Boost and the Courage
loop instead, exported in Prometheus format if Phase 6 adds Prometheus. `gemini-3.8-flash` is an unverified model id.

**2. Idle detection.** The idea is sound; the draft needs the fixes in the table. There is also a bigger gap:
**idle is not free.** Both GPUs are nearly full of loaded models (11.4 / 12.3 GB and 7.1 / 8.2 GB). A LoRA run needs
the engines on that GPU stopped, so Courage (or vision) is down for the run. The gate therefore also needs:
quiet hours, nobody awake (HA person + presence), no pending approvals, and a run that stops and restarts units
through the Model Loader's backup/rollback path. ROCm training on gfx1031/gfx1032 is unofficial
(`HSA_OVERRIDE_GFX_VERSION=10.3.0`), and QLoRA of a 14B in 12 GB is tight. Prove one tiny LoRA
(the 0.6B draft or the 3B worker) before designing around 14B adapters.

**3. Model provenance (CouchDB).** This fits what exists. The loader already reads GGUF headers
(`hw_probe.py --models`), and every apply is preview + explicit click + backup/rollback, so `human_approved` maps to the
existing apply step. To add:
- a sha256 per GGUF, cached by (path, size, mtime); hashing a 9 GB file takes ~30-60 s once
- DB `model_provenance` on LXC 116, separate from the LiveSync DB (agreed)
- engine detection from `llama-server --version` (build, commit, fork) next to the `--help` parse the loader already does,
  with a hard, no-override block when a model needs a fork
The Bonsai / "Qwen3.8" details are unverified here; check them when the work starts. A 27B coding model on the 6750
means unloading the coordinator, so it is an Engine Profile swap (like `ally_coding`), not a model that runs alongside.

**4. Escalation ladder.** Objective triggers only: agreed. They already exist in the Courage tool loop: tool-argument
validation failures, tool errors, the step cap, and the deterministic tool-choice eval (42/42). `think_harder` (Boost)
is today's manual "bigger brain" step. The "nudge tool" is MCP `nudge_agent` from the shelved agent system; loop detection
belongs in the Courage/harness loop instead (repeated identical tool calls, n-gram repeats in the stream).
Frontier verdicts need a recorded event (prompt, local answer, frontier answer, verdict) before anything can use them.
For the rented-GPU tier, extend Boost's `egress.py` (it already classifies secrets, LAN IPs and home names, and pictures
never leave) rather than writing a new sanitizer. Tailscale appears only in the watch scaffold; nothing in STATE.md
confirms it runs on bigserv yet.

**5. Correction capture.** StoneSage already captures corrections in three places: presence corrections (`wildlife/corrections.jsonl`
+ Frigate's face library), `data/patrol_corrections.jsonl`, and Courage's learned reflexes. These are identity/vision
corrections, a natural first adapter category (vision) once a frontier-verdict event exists for text.

## Zero-leak note

The draft's rule "never hardcode 192.168.x.x" is stricter than this repo's: STATE.md and CLAUDE.md name LAN IPs on
purpose, on the assumption that the repo is private with no remote. **That assumption no longer holds.** The checkout
has a `github` remote, `lottage/hivemind-cluster-stack`. Checked 2026-09-25 through the unauthenticated GitHub API:
the repo is **public** (created 2026-09-09, last push 2026-09-25 11:08 UTC, branches `main` and `ui-accent-tokens`),
and commit 67fe717, one of the commits holding the HA long-lived token, the Proxmox `StoneSage` API token and the
CouchDB password, is publicly reachable. Treat those three credentials as leaked: rotate them now (John, by hand).
Only after that, decide whether the repo stays public. If it does, it needs a fresh history (no old commits) and
LAN addresses kept out of the docs.
