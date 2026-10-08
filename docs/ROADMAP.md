# StoneSage / Computer: roadmap

One document for every phase. Consolidated 2026-09-29 from the original plan doc (Claude Docs, 2026-09-23), the local-loop
design (`docs/plan-2026-09-26-local-loop/DESIGN.md`), the stack-limits handoff review
(`docs/handoff-2026-09-25-stack-limits/REVIEW.md`) and the watch project (`stonesage-watch/`).

**Status wins over plans.** Where a source doc still says "planned" and STATE.md says "live", this document follows
STATE.md. What is deployed right now is in [STATE.md](../STATE.md); standing rules are in [CLAUDE.md](../CLAUDE.md).
This file answers "what are we building, in what order, and where are we".

## Goal

1. **Now: a usable home assistant.** "Computer" (the attic Computer from *Courage the Cowardly Dog*: dry, British,
   sarcastic, loyal) lives in StoneSage, uses real tools, sees the cameras, and speaks through the Echos. Say "Computer"
   in anything a person sees or hears; code names keep the old word (`backend/courage/`, agent id `courage-computer`).
2. **Long game: the garden.** A walled place where agents explore their own limits and desires, built on the same
   grounded foundations (real senses, measurable evals, curated memory, budgets).

Principle from the start: fix the brain first (tool calling, not keyword stuffing), then make cameras event-driven, then
voice. Each phase ends with something usable. Every claim gets a deterministic test, never an LLM judge.

## Status at a glance (2026-09-29)

| # | Phase | Status |
| --- | --- | --- |
| 0 | Stabilize | Done 2026-09-23 (old-doc trimming still open) |
| 1 | LLM stack | Evals run 2026-09-28; Qwen3-14B stays; two 6750-only candidates still to run |
| 2 | Tool-calling Computer | Done 2026-09-24 |
| 3 | Real-time cameras and presence | Done 2026-09-27 |
| 4 | Voice | Built 2026-09-28; **not yet heard working on a real device** |
| 5 | Wildlife and StoneSage polish | Not started as a phase (parts done along the way) |
| 6 | Measured limits | Done 2026-09-28 (Boost / frontier rungs wait on keys and an install) |
| 7 | On the wrist (Garmin) | Done 2026-09-28 (three hardware checks open) |
| 8 | The gamified house | Not started |
| 9 | Local loop (frontier plans, Bonsai grinds) | Groundwork + engine lease done; loop worker not built |
| - | The garden | Not started; unblocked now that Phase 4 is built, but nothing scheduled |

## Divisions

Each part of the project has its own scoped roadmap (where the code is, where it is now, next steps in
order, rules, done-when):

| Division | Phases it covers | Roadmap |
| --- | --- | --- |
| 1. Computer (brain and voice) | 1, 2, 4, 8 | [roadmaps/1-computer.md](roadmaps/1-computer.md) |
| 2. Senses (cameras, presence, wildlife, commentary) | 3, 5, 8 | [roadmaps/2-senses.md](roadmaps/2-senses.md) |
| 3. Cockpit (StoneSage web app and server) | 5 | [roadmaps/3-cockpit.md](roadmaps/3-cockpit.md) |
| 4. Compute and measurement (engines, lease, metrics, Boost) | 1, 6, 9 | [roadmaps/4-compute-and-measurement.md](roadmaps/4-compute-and-measurement.md) |
| 5. Wrist (Garmin and the Android companion) | 7 | [roadmaps/5-wrist.md](roadmaps/5-wrist.md) |
| 6. Infrastructure and ops (hosts, deploys, secrets, git, docs) | 0 | [roadmaps/6-infrastructure-and-ops.md](roadmaps/6-infrastructure-and-ops.md) |
| 7. Loop and garden (local loop, CLI harness, long game) | 9, garden | [roadmaps/7-loop-and-garden.md](roadmaps/7-loop-and-garden.md) |

---

## Phase 0: Stabilize (done 2026-09-23)

Goal: every change can be rolled back and the docs describe reality.

Done:
- Full snapshot (`_backups/pre-phase0-2026-09-23.tgz`), then a clean baseline commit (`b3b5ebb`, branch
  `phase0-restructure`); one branch per feature and a commit per session since.
- Secrets out of code into `StoneSage/backend/config.json` (gitignored) and `/etc/stonesage/secrets.env` on each host.
- One wildlife daemon (the `cluster-bridge` copy is canonical). Thinking loop, Assembly Hall and council switched off
  (code kept). `STATE.md` is the single source of truth, updated from live output, never from memory.
- `/api/health/all` (top-bar badge). Tests split: `tests/run_tests.py` (unit, LAN blocked) and `tests/live/` (opt-in,
  read-only).
- GPU layout "A" (2026-09-23): coordinator + worker on the RX 6750 XT, embedder + vision on the RX 6600. Worker 3.2 -> 126
  tok/s, vision 5.9 -> 2.9 s per frame, no spill to system RAM.

Open: cut the old philosophy/passdown docs down (they carry a banner pointing at STATE.md).

**Public-repo caveat.** The `github` remote is public. History was rewritten 2026-09-25 to strip the HA token, Proxmox
token and CouchDB password. Those credentials are **not rotated** (John's decision, restated 2026-09-28: not happening
now). Treat them as sensitive anyway, scan every push, and never put secrets in code or docs.

## Phase 1: LLM stack

Goal: one reliable tool-calling brain per GPU, chosen by a scored test, not by feel. A model split across both cards
was too slow for live banter (6-7 tok/s), so each model stays on one card and a big MoE is an on-demand mode.

Live layout (STATE.md has the numbers): 8001 coordinator Qwen3-14B Q4_K_M + 0.6B draft (6750 XT); 8002 worker
Qwen2.5-Coder-3B (6750 XT); 8003 embedder BGE-large (6600, inputs < 950 chars); 8004 vision Qwen2.5-VL-7B (6600).

Evals (2026-09-28, `tests/live/model_eval.py`, 46 then 50 deterministic cases, single turn and mid-conversation, results in
`docs/evals/`):

| Model | Single | Mid | Wrong actions | Verdict |
| --- | --- | --- | --- | --- |
| **Qwen3-14B** (live) | 45/46 | 45-46/46 | 0 | Stays Computer's brain |
| Granite 4.0 h-tiny | 44/46 | 41/46 | 0 | Best challenger; now the CPU stand-in |
| Ternary Bonsai 2 27B | 44/46 | 42/46 | 0 | Accurate but slow: belongs to the long-context loop |
| Ornith 1.5 9B | 43/46 | 23/46 | 2 | Disqualified for home control |
| Qwen2.5-Coder-7B (two variants) | 5/46 | 5/46 | 0 | Answer in text, not tool calls: unusable here |

On CPU (the stand-in slot): Granite 44/42, p50 0.87 s, decode 35 tok/s, vs Qwen3-4B 42/40, p50 2.5 s. LFM2.5 (8B and
2.6B) and Granite 4.2 3B all made wrong actions and lost.

Loop control stays layered: sampling (keep DRY and a presence penalty, no lower than temperature 0.6 on Qwen3), hard
`max_tokens` with thinking off for home turns, and the reasoning watchdog. Abliterated models are fine for coder and
chat sides; the model that controls locks, climate and cameras is chosen on tool-call accuracy.

Still to run (need the 6750 XT, so Computer goes offline: a night window behind the idle gate): Gemma 4 12B agentic Q4_K_M,
Ornith 1.5 9B OBLITERATED Q8_0.

## Phase 2: Tool-calling Computer (done 2026-09-24)

Goal: Computer decides what to look at and do, from a short list of typed tools. Simple answers in under 2 s, camera
questions under 8 s.

What exists (`StoneSage/backend/courage/`):
- OpenAI-style tool loop against :8001 (`--jinja`), capped at 5 steps, **9 tools**: `ha_get_states`, `ha_call`,
  `presence_now`, `camera_look`, `camera_scan`, `memory_search`, `notify`, `speak`, `correct_sighting`.
- A small stable prompt: persona first (a cacheable prefix), then the live presence card and memory notes in a second
  system message, then history.
- Reflexes: bare on/off orders for a uniquely named light/lamp/plug/fan skip the LLM; phrasings the loop resolved are
  learned and replayed without it. Server-infrastructure plugs are never switched off.
- **Approval rules (John's decision):** reading and camera/PTZ tools run freely. Actions John orders outright run at once;
  actions Computer infers ("it's cold in here") ask first; unlock and open-garage always ask. Approvals work by "yes" in
  chat, Yes/No buttons on the web, and Yes/No buttons on the phone and watch.
- Exposed to Home Assistant as a conversation agent (`courage:latest` / `computer:latest` through StoneSage's Ollama API);
  HA's "Courage" Assist pipeline (faster-whisper, Piper en_GB-alan) is the preferred one.
- Conversational memory (notes about the people it talks to, recalled by BGE similarity), a per-turn trace
  (`data/courage_trace.jsonl`), and a companion side (stories, opinions, small talk) alongside the home job.
- Tool choice on the live coordinator: 47-50/50 mid-conversation, 47-49/50 single, 0 wrong actions.

## Phase 3: Real-time cameras and presence (done 2026-09-27)

Goal: Computer knows who and what is in view within 1-2 s without running the vision model on every frame.

- **Frigate** 0.18 on LXC 128 (node pve), OpenVINO detector on the UHD 770 (5.4 ms per inference). Kitchen/living room C260
  is a Frigate camera; the solar driveway TCW90 has no RTSP and stays with the wildlife sentry; TC82 battery cams stay on
  the Tapo push path with a 3-minute backoff. Person confidence threshold 0.75 (a blanket on the couch was read as a
  person at 0.77 top).
- **Presence service**: StoneSage listens to Frigate's websocket and merges Frigate, sentry and patrol sightings, with
  Life360 GPS (Austin and Savannah) leading each person's line. Published to HA as `sensor.computer_seen_*`.
  `camera_look` asks Frigate what is in view, then runs the vision model on Frigate's latest frame.
- **Corrections**: "Wrong" / "Correct as" on every sighting card; a person correction teaches Frigate's face library.
  Subject boxes on cards. The first real correction is still John's to make.
- **Live cameras**: WebRTC from go2rtc, with an MP4 fallback and a per-tile quality menu; PTZ arrows and presets.
- **PTZ patrol** every 15 min per PTZ camera (kitchen 4 frames, driveway 5), returns the camera to where it was. The kitchen
  C260 needed its duplicate TP-Link entry disabled in HA and a fix for the left end stop (2026-09-28).
- **Commentary engine** (Computer speaks unprompted): arrival greeting is live; cooking and cleaning run in shadow (logged,
  not spoken) until real hits show up. At most 6 remarks per rolling 24 h, 10 min per room, only when a resident is home
  and nobody would be woken. No fixed quiet hours: "resting" is inferred from phone use, the watch and camera sightings.
- Spider webs: Frigate triggers on objects, not pixel motion, so a web is never a "deer". Physical IR/porch-light measures
  are John's.

Skipped by choice: Frigate's own HA integration. Not yet seen live: a real arrival greeting on an Echo.

## Phase 4: Voice (built 2026-09-28, not yet heard on a real device)

Goal: say "Computer, ..." and hear the answer in the bm_george voice within about 2 s for simple things.

Decision (2026-09-23): use the Echos to save cost. Echos cannot feed a local assistant, so input is "Alexa, tell Computer"
(Amazon's speech-to-text) or the phone/StoneSage mic; output is Echo announce or file playback. Local satellites with a
"Computer" wake word (HA Voice Preview or ESP32-S3, about $15-60 per room, 1.5-3 s fully local) stay a later upgrade for the
kitchen if the Amazon round trip feels slow.

Done 2026-09-28:
- **Latency.** The presence card sat inside the first system message ahead of ~1,200 tokens of tool schemas, so every
  turn re-read ~1,260 tokens. Moved to a second message: first model call 3.4-4.5 s -> 0.8-1.2 s.
- **Streaming.** Replies over 300 chars stream sentence by sentence (web SSE and HA's NDJSON); the last sentence is held
  so filler like "let me know if..." can still be cut.
- **Phone-lock recovery.** The page recovers a reply after the screen locks (server state, saved reply, stale-stream abort).
- **Web voice mode speaks in clips** (first sentence alone, then 120-250 chars, fetched ahead and played in order). Kokoro on
  CPU needs ~40 ms per character, so one big request took 13 s and hit a 10 s timeout: that was the first real test
  ("silent, then 45 s, read the tool calls aloud, never said hello"). Also fixed: a mid-conversation greeting used to
  survey the house (4-10 tool calls, 14 s); now "Hello?" answers in ~1.3 s.

Open:
- Hear it on the phone, and through an HA voice device. **After a deploy, reload the page: an open page keeps old JS.**
- Kokoro is CPU-bound; a GPU or a faster voice would remove the wait on long replies.
- Wake word "Computer" and local satellites (later); sentence streaming into the Echo path is untested.
- Small watch-item: small talk sometimes states a made-up detail ("a bit chilly in here") without a tool call.

## Phase 5: Wildlife and StoneSage polish (not started as a phase)

Wildlife, once Frigate feeds events: the sentry subscribes to Frigate's deer/cat/dog/bird events instead of pulling a clip
on every Tapo alert, and runs a vision model only for re-ID traits; burst capture from Frigate's recording; a hand-labelled
re-ID sanity test (20 sightings) before trusting names; a daily Obsidian digest replacing free-running dossiers.

StoneSage: split `server.py` (8k lines, ~205 routes) into route modules one at a time with a smoke test after each; one
home screen (presence, live cams, climate, engine health, chat); the CLI calls StoneSage's API instead of duplicating logic
in `harness/core`; a coding agent (Computer's loop plus file/shell tools behind approval) that eventually replaces
Antigravity for day-to-day work.

Already done along the way: presence corrections and the wildlife correction plumbing, subject boxes, the Model Loader
and Engine Profiles.

**Shelved** (do not extend or re-enable): autonomous thinking loop, Assembly Hall, agent reproduction, Citadel 3D, Blender,
GGUF trainer runs, ROCm experiments.

## Phase 6: Measured limits (done 2026-09-28)

Goal: know from numbers what the stack can and cannot do, and when a GPU is really free.

- **Metrics**: Prometheus on LXC 129 (90-day retention) scrapes the four llama engines (`llamacpp:*`, embedder now with
  `--metrics`), Frigate, StoneSage's `/metrics`, and node/GPU counters from VM 102 (mapped by PCI slot, not card number).
- **Idle gate** (`GET /api/idle-gate`): a GPU may be lent out only when it is under 10 % busy for 5 min, its engines are idle,
  no approval is waiting, no Computer turn in 15 min, and nobody is awake. Idle is not free: both GPUs are ~90 % full.
- **Model provenance**: a CouchDB `model_provenance` database with a sha256 per GGUF, lineage, and which builds can load
  it. The Model Loader hard-blocks a model its engine cannot run (Bonsai needs the Prism fork).
- **Escalation ladder** on objective triggers only (step cap, :8001 down, empty answer): Boost -> frontier -> human phone
  push with what was tried. Today it is local -> human: Boost has no keys and the frontier worker is not installed.
- **Engine lease** (see Phase 9, section B): lends a GPU's engines to a long-context layout, with a Courage-lite stand-in.
- Boost (`backend/boost/`, all surfaces off, no keys): a pooled free-tier router with a tiered egress rule (home text only
  to sources that don't train on it; pictures and secrets never leave). A separate LiteLLM gateway was **not adopted**:
  Boost already routes, counts quotas and falls back, and the draft's Gemini-free fallback would send home text to a
  provider that trains on it.

Open: one tiny LoRA (the 3B worker or 0.6B draft) before planning any 14B adapter (ROCm on these cards is unofficial);
frontier-worker install (needs the CLIs and John's own login); Boost keys; correction capture for text once frontier
verdicts are recorded events.

## Phase 7: On the wrist (Garmin Instinct 2; done 2026-09-28)

Goal: approvals and glanceable status on the watch. Code in `stonesage-watch/`; the wire format is `PROTOCOL.md` and its own
rules are in `stonesage-watch/CLAUDE.md`.

```
StoneSage -> watch bridge (LXC 120) -> tailnet-only HTTPS -> Android companion (S25 Ultra) -> Connect IQ -> watch app + face
```

Hardware: Instinct 2 (API 3.2, 176x176 mono, tight memory) and a Samsung S25 Ultra. The bridge is tailnet-only (Tailscale
Serve on a helper LXC that forwards to the bridge); no Funnel, no port forwards. The device enforces HTTPS-only outbound.

| Step | What | Status |
| --- | --- | --- |
| W0 | Recon | Done |
| W1 | Bridge (FastAPI, SQLite asks, usage collector, pytest) | Done |
| W2 | StoneSage side: an ask fires beside the phone push; whichever answers first wins; destructiveness re-derived server-side | Done 2026-09-26 |
| W3 | Deploy (bridge on LXC 120, tailnet forward) | Done 2026-09-26 |
| W4 | Android companion (reconnect race, watch-reachable sync, boot start) | Done 2026-09-28 |
| W5 | Watch app + face in the simulator | Done 2026-09-26 |
| W6 | End to end on hardware | Done 2026-09-28 except the items below |

Passed on hardware: ask round trip, destructive Deny / At desk only, resync after Bluetooth loss, companion auto-start
after reboot (Tailscale set to always-on VPN by John).
Open: Wi-Fi drop and restore, face freshness under 5 min, one unattended full-reboot run, Savannah's watch, and a
`done`/`err` toast for genuinely long-running work (patrol sweeps, Boost fallback chains) rather than chat turns.

Rules that must not be broken (kept in full in `stonesage-watch/CLAUDE.md`): no real IPs, hostnames or tokens in that
repo; destructive asks are never approvable from the watch; generate secret files on the Linux host, never on Windows
(CRLF corrupted every token once); ask before `adb install`, host-level or destructive commands.

## Phase 8: The gamified house (not started)

Turn the sighting corrections John already does by hand into something the household enjoys, and make Computer a better
conversationalist. Independent of Phases 6 and 7; needs Phase 5's data.
- **Who's Who**: a guessing game over real sightings (crop, "who is this?", scoring, per-player streak). A confirmed guess
  is a correction, so it reuses `presence_corrections.py`, Frigate's face library and the grounding boxes.
- **Wildlife catalogue**: a browsable, editable card per species/individual (thumbnail, counts and dates, blurb), built from
  `known_entities.json` and the sentry log; separate from the moment-to-moment correction cards.
- **Conversation quality**: extend `tests/live/test_courage_chat.py` beyond "not a refusal, long enough" (follow-ups, thread
  tracking, varied phrasing) and tune prompt and sampling against that bar.

## Phase 9: Local loop, frontier plans and Bonsai grinds (design 2026-09-26, partly built)

Problem: when a frontier model proofreads code written by a local model, it spends about as many tokens as writing it,
because **reading** is the cost. Principle: (1) the frontier writes the contract, not the code: spec, tests, allowed paths,
iteration cap; (2) a deterministic oracle judges (tests, type check, build), never an LLM; (3) the frontier sees a
~100-token report and reads code only when an objective trigger fires; (4) for read-heavy work, invert the roles: Bonsai
reads the repo and writes a brief, the frontier patches once.

**Architecture (John, 2026-09-27): StoneSage's backend is the one server.** Engine leases, loop jobs, autopilot toggles and
the model tryout are StoneSage HTTP routes. Claude Code, the web PWA, phone push and the watch are thin clients, never of
each other and never of VM 102 directly. MCP tools are thin wrappers over those routes; no state lives in the MCP process.
The shape comes from OpenCode's client/server split; its code was not adopted (it is built around a generic coding session).

### A. Engine: Bonsai 2 27B (built and benchmarked)
Ternary Bonsai 2 27B PTQ1_0 (5.95 GB) on the PrismML llama.cpp fork (`/opt/llama-prism/current`, Vulkan only; ROCm fails on
RDNA2), never copied over the mainline binary. Three lease layouts on :8005, each `Conflicts=` the others:

| Layout | Evicts | Measured decode / prefill |
| --- | --- | --- |
| `longctx_6750` | Computer (coordinator + worker), Courage-lite steps in | 39 tok/s at 0, 33 at 32K, **8.9 at 131K**; prefill 126 -> 52 tok/s |
| `longctx_6600` | vision only (daytime layout) | 23 / 20 tok/s at 0 / 24K; prefill only ~70 tok/s |
| `longctx_max` (both cards, `-ts 11,7`) | Computer + vision | 21 -> 14 tok/s; **crashed the driver at 245K, capped at 131072** |

Prefill is the real limit (10K uncached tokens ~2.5 min on the 6600), so a loop keeps one slot per job with a stable prefix
and `--cache-reuse`. Decode falls off a cliff past 32K even with no VRAM spill (KV bandwidth). Never use q5_0 KV.
Open: root-cause the 245K crash (fdinfo polling on both cards during the sweep, smaller `-ub`), `-ub` tuning, PQ2_0 on the
6750, and the MTP speculative head.

### B. Engine lease (live 2026-09-28)
`backend/engine_lease.py`, layouts in `config.json engine_layouts` (no model names in code). Acquire refuses if a lease is
held, the layout is disabled, its idle gate fails, or an evicted engine is busy (unless forced). Leases last 60 min and only
a human can renew: 10 min before the end John gets a phone check-in (Another hour / Stop); silence means stop. If the process
dies the units are restarted at the next StoneSage start. While leased, Computer says it is on loan, `camera_look` falls back
to Frigate's object list, and patrol and commentary skip vision. Overnight and hands-off grants are **designed but not built**:
a person-only "run until done" grant with failure-only dead-man's switches (worker heartbeat missing 5 min, engine failing
`/health` 5 min); night cap 10 h. Everything traced as `kind: lease`.

**B2. Courage-lite stand-in (live).** When the coordinator is lent out, Computer switches to Granite 4.0 h-tiny on VM 102's
CPU (:8006): replies capped at 400 tokens, an honest "spare brain until HH:MM" line, and **every action asks**, even outright
orders. Reflexes still run without any model. Gated by eval (>= 86 %, zero wrong actions, p50 <= 8 s; Granite passed by a
wide margin). The first live handover has not been run: it needs a deliberate quiet window.

**B3. Autopilot (designed, not built).** Independent of hands-off: a job's `merge_mode` is `review` (default, opens a PR and
stops) or `auto` (merges when tests are green and no breaker fired), inheriting a session default toggled by
`/autopilot on|off` on every surface. `approver_id` (always "john" today) is recorded on every lease, hands-off grant and
merge so a second approver later is only new rows.

### C. Loop worker (designed, not built)
`server setup/cluster-bridge/local_loop_worker.py` on VM 102 (:8771), modelled on `frontier_worker.py`: a scratch clone per
job, one job at a time, reached only through StoneSage's job routes. The job contract carries the task, `allowed_paths`,
`read_paths`, `protected_paths` (the tests: the model may never touch them), `test_cmd`, `max_iters`, `max_minutes`,
`reset_after_fails`, `merge_mode`. Each iteration: stable-prefix prompt, whole-file replacements limited to allowed paths,
run the tests, retry with the trimmed first failure, restart from the contract plus a "what didn't work" summary after N
failures. Deterministic breakers: `no_change`, `same_failure` (hashed signature, 3 times), `repetition` (n-gram stream
stop), `scope`, and caps. The report is what the frontier reads by default; diffs and attempts only on escalation.

### D. MCP wrappers (designed, not built)
`local_loop_submit / _status / _detail`, `engine_lease / _release / _status`, `autopilot_set / _status` in
`cluster-work-mcp`, each one HTTP call to a StoneSage route.

### E. Model tryout pipeline (partly built)
Built: the lease-gated tryout slot (`llama-tryout-6600/6750.service`, :8009, models in `/opt/models/tryout/`, never
`/opt/models/`) and `tests/live/model_eval.py` (used for the Phase 1 evals). Not built: the picker (paste a Hugging Face URL
or watch quant publishers), live free-VRAM-driven search with no hardcoded ceiling or size floor, GGUF header fit before
downloading, auto-tuning context by back-off on OOM or device-lost, the standard battery (repetition, deterministic
coherence, the Courage eval or the breaker battery, speed at several depths), and a one-card-per-model report that discards
the weights by default. All as StoneSage routes so any surface can drive it.

### Measuring the saving
Every job records frontier tokens (contract + status reads + detail reads) against local tokens, compared with the same
5-10 tasks done by Claude Code alone. Success: frontier tokens per green task <= 30 % of baseline at equal pass rate. If
proofreading still dominates, the escalation triggers are too loose. If most jobs stop on `no_change` / `same_failure`,
Bonsai is not a good enough executor and the design stands with a different one.

### Phase 9 order
1. Prism build, Bonsai on the three layouts, Courage-lite eval: **done**. 2. Engine lease + hourly check-in + auto-revert +
`approver_id`: **done**. 3. Hands-off and night grants. 4. Loop worker + job routes + MCP wrappers + `/autopilot`; first job
is a small real task that already has tests. 5. Token measurement over 5-10 tasks and a go/no-go. 6. The tryout picker.
7. Later: MTP head, q4_0 KV at 262K, "Bonsai explores, frontier patches".

Risks: the fork moves (pin the release tag); tensor types 142/143 may confuse `hw_probe.py --models` (keep Bonsai under
`/opt/models/prism/`); Bonsai is documented to loop in reasoning and claim fixes it did not make (hence the breakers); the
tryout downloads GGUFs from arbitrary repos (scratch directory, lease-gated port, discard by default).

---

## The garden (long game, not before Phase 4; nothing scheduled)

The home assistant is the first plant, not a detour: agents that can see the house, remember reliably and use real tools have
something true to explore. The last loop drifted into fake science (about 4M tokens of low-value output) because it had none
of that. Rules for when it comes back:
- **Grounded senses first**: real events (cameras, weather, Kavita books, RSS, Computer's own logs), not prompts written by
  other agents.
- **Limits you can measure**: each agent gets the Phase 1 evals as a mirror; "explore your limits" becomes an experiment with
  a score.
- **A walled garden**: its own sandbox VM or LXC, a read-only view of the house, no HA writes or shell, an hourly token
  budget, and it runs only when the idle gate says the GPUs are free.
- **Curated memory**: agents write freely to scratch space; only material that passes the dual-gate review (a frontier model
  plus John) reaches long-term memory or training data.
- **Desires as a queue**: what an agent wants goes into a wish list John can browse and grant. When the thinking loop returns
  it gets real jobs only (review yesterday's camera events, curate memory cards, draft fixes), with a budget and a
  human-approved output queue.
- Assembly Hall, personas and agent DNA are reused; reproduction comes back last, once an offspring can be shown to beat its
  parents.

## Decisions on record

| Date | Decision |
| --- | --- |
| 2026-09-23 | Voice starts with the Echos (announce out, "Alexa, tell Computer" in); satellites later |
| 2026-09-23 | Frigate on the i7-12700K iGPU with OpenVINO; camera/PTZ tools run freely |
| 2026-09-23 | Outright orders run at once; inferred actions ask; unlock and open-garage always ask |
| 2026-09-23 | Commentary: <= 6 unprompted remarks a day, triggered by arrivals, cooking, cleaning (living room/kitchen + outdoor) |
| 2026-09-25 | Life360 (HACS) for GPS presence; no LiteLLM gateway (Boost already routes) |
| 2026-09-26 | Courage-lite on CPU during leases; 60-min human-renewed leases; hands-off is a person-only grant |
| 2026-09-26 | Watch status shows compute sources (coordinator, worker, boost, frontier), not project names; Antigravity is not observable |
| 2026-09-27 | StoneSage is the one server for loop, lease, autopilot and tryout; MCP/PWA/phone/watch are thin clients |
| 2026-09-27 | Merge autonomy is decoupled from hands-off (per-job `merge_mode`, `/autopilot`, single approver "john") |
| 2026-09-27 | Frigate's HA integration skipped; StoneSage publishes presence to HA instead. Person threshold 0.75 |
| 2026-09-27 | No fixed quiet hours: "resting" is inferred from phone use, watch and sightings |
| 2026-09-27 | Renamed "Computer" (Courage is the dog in the show); code names unchanged |
| 2026-09-28 | Switch Courage-lite from Qwen3-4B to Granite 4.0 h-tiny; StoneSage alone runs on New York time |
| 2026-09-28 | Credential rotation is not happening; do not suggest it (still never leak them) |
| No date | No commit attribution lines; deploy each tested change immediately; no hardcoded hardware, model or engine labels |

## Open questions and next steps

1. **Hear Phase 4 work.** Reload the page, then try voice mode on the phone and one HA voice device.
2. ~~Realistic-states eval case~~ done 2026-09-29 (`tests/live/test_courage_real_states.py`; questions no longer trigger or
   offer actions).
3. **First live handover** to Courage-lite, and the two 6750-only model evals: one deliberate overnight window behind the
   idle gate.
4. **Review the cooking/cleaning shadow log** and decide whether to flip those triggers to "speak".
5. Watch: Wi-Fi drop, face freshness, unattended reboot run.
6. Waiting on John's accounts: Boost keys, frontier worker (Claude Code / Gemini CLI logins).
7. Decide the next build: Phase 9 loop worker, Phase 5 (server.py split, wildlife via Frigate), or Phase 8.
8. Open from the lease design: whether a lease may be taken while someone is home (today the idle gate says no while anyone
   is awake).
