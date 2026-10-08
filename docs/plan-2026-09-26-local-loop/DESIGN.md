> Consolidated into [docs/ROADMAP.md](../ROADMAP.md) (Phase 9) and [docs/roadmaps/7-loop-and-garden.md](../roadmaps/7-loop-and-garden.md) on 2026-09-29. This file stays as the detailed design reference.

# Local loop: frontier plans, Bonsai grinds, tests judge

Draft 2026-09-26. Status: design only, nothing deployed. Research sources are listed at the end.

## Problem
Measured so far: when the frontier model (Claude Code) proofreads and fixes code written by the local models, it
spends about as many tokens as writing the code itself. The cause is **reading**. Reviewing means loading the
generated code plus enough surrounding code to judge it, which is the same input as writing it. Moving the writing
to a local model saves little while the frontier model still reads everything.

## Principle
1. **Frontier writes the contract, not the code.** Spec, **tests**, allowed paths, iteration cap. This is a small
   output.
2. **A deterministic oracle judges** (tests, type check, build). Never an LLM judge (CLAUDE.md: small models grade
   too leniently).
3. **Frontier sees signals, not code**: a short report (about 100 tokens). It reads code only when an objective
   escalation trigger fires.
4. For read-heavy work, invert the roles (AI21's "open models explore, frontier models patch"): Bonsai reads the
   repo and writes a brief, and frontier writes the patch once from the brief.

## Architecture: one server, thin clients (2026-09-27, John's call)
"I want to be able to access the same harness everywhere" settles a question this doc had left implicit: **StoneSage's
backend is the one server** for all of this - engine leases, loop jobs, the autopilot/hands-off toggles, the model
tryout pipeline (section E). Claude Code, the web PWA, phone push and the watch are thin clients of it, never of each
other and never of VM 102 directly.

Checked against OpenCode's actual architecture (github.com/opencode-ai/opencode, docs at opencode.ai) before adopting
the pattern: a local server holds the real session/tool loop, and every surface - TUI, desktop app, IDE extension,
SDK - talks to it over HTTP; local models plug in by pointing the model endpoint at `localhost` (llama.cpp, Ollama,
LM Studio, vLLM, all OpenAI-compatible). **The shape is right, the codebase isn't ours to take.** Its server is built
around a generic coding session - LSP integration, plan/build modes, multi-provider chat - none of which carries
Courage's actual value (HA grounding, camera/PTZ tools, presence, approvals, the trace, the watch bridge). Forking it
would mean re-plumbing all of that into a foreign framework, or running two harnesses side by side - the opposite of
"the same harness everywhere." So: copy the pattern, not the code.

Concretely:
- `local_loop_submit` / `_status` / `_detail`, `engine_lease` / `_release` / `_status`, and the autopilot/hands-off
  toggles (section B3) are **StoneSage HTTP routes**. The loop worker still runs on VM 102 - it needs to run scratch
  clones and tests there - but StoneSage owns the job/lease state and is the only thing that talks to it directly.
- The `cluster-work-mcp` tools (section D) become thin wrappers: each one is a call to a StoneSage route, the same
  relationship OpenCode's SDK has to its server. No state lives in the MCP process, so a crashed or restarted Claude
  Code session never orphans a job or a lease - the web UI or a phone can see and stop the same job.
- The web PWA gets the same toggle as a checkbox, hitting the same route. The watch shows loop status and a Stop
  button through the existing bridge. One state, several views of it - never a second copy to go stale.
- State lives where it already does - Valkey/A-MEM or the JSONL trace - not a new store, and not a file only one
  client can see (mirrors OpenCode's per-server SQLite idea without actually adding a new database).

## Pieces

### A. Engine: Bonsai 2 27B in three lease layouts
- Model: `Ternary-Bonsai-2-27B-PTQ1_0.gguf` (5.95 GB, Qwen3.8-27B, hybrid attention: 16 full-attention layers
  with 4 KV heads × 256, plus 48 linear-attention layers with fixed state). No mmproj (saves 0.63 GB).
- Runtime: PrismML fork, branch `prism`, **>= prism-b10735** (Vulkan int-dot PTQ1_0 kernel, PR #188 -> #238,
  benchmarked on a 6750 XT: ~40 tok/s decode, 34 tok/s at 8K). Built into `/opt/llama-prism/` and never copied over
  `/usr/local/bin/llama-server`: the other engines stay on mainline. ROCm is a known failure on RDNA2, so it's
  Vulkan only. Draft build script: `server setup/vm-setup/04_build_llama_prism.sh`.
- KV cost per token: f16 64 KiB, q8_0 34 KiB, q8_0 K / q4_0 V 26 KiB, q4_0 18 KiB. Never q5_0 KV (PrismML:
  several times slower). Every figure below is a paper estimate: confirm with fdinfo `drm-memory-vram` after start.

Three layouts, one unit each in `server setup/vm-setup/systemd/disabled/`. All listen on :8005, and each
`Conflicts=` the others plus whatever it evicts, so systemd enforces "one layout at a time" by itself:

| Layout / unit | GPUs | Evicts | Context (start) | Speed |
| --- | --- | --- | --- | --- |
| `longctx_6750` / `llama-longctx.service` | 6750 XT | Courage (coordinator + worker) | 131072, q8_0/q8_0 (~4.3 GiB free: up to ~250K at q4_0) | ~40 tok/s short-ctx (measured upstream on a 6750 XT) |
| `longctx_6600` / `llama-longctx-6600.service` | RX 6600 | vision (camera look, patrol vision) | 32768, q8_0/q4_0 (~0.85 GiB free with the embedder kept) | unmeasured; 6600 has ~half the bandwidth (224 vs 432 GB/s) |
| `longctx_max` / `llama-longctx-max.service` | both, layer split `-ts 11,7` | Courage + vision | **262144, q8_0/q8_0** (~15.2 of ~18.5 GiB) | unmeasured; between the two |

**Measured 2026-09-27 00:13, `longctx_6600`** (PTQ1_0, prism-b10743, RX 6600, K q8_0 / V q4_0, FA on;
results `/root/bench-longctx-6600-20260927-001331` on VM 102):

| depth | prefill (pp512) | decode (tg128) |
| --- | --- | --- |
| 0 | 77.1 tok/s | 22.8 tok/s |
| 8K | 70.9 tok/s | 21.6 tok/s |
| 24K | 61.6 tok/s | 19.8 tok/s |

- Server at `-c 32768`: **6.40 GiB VRAM** on the 6600, 59 MiB GTT (no spill). With the embedder that leaves ~1 GiB
  free, so `-c 65536` should fit (+0.8 GiB of KV at 26 KiB/token); verify with fdinfo before trusting it.
- Needle at 22.6K tokens: **found**; 329 s prefill (68.7 tok/s), then 19.8 tok/s decode.
- Decode is fine for a loop. **Prefill is the bottleneck: ~70 tok/s** means every uncached 10K tokens costs ~2.5
  min on this card. The loop must reuse the cached prefix (`--cache-reuse`, one slot per job, append-only
  context), or a context reset costs minutes. Next checks: `-ub 1024/2048` for prefill, and PQ2_0 (upstream: faster
  on compute-bound cards) on the 6750 XT, where it fits.
- The log line "common_fit_params: failed to fit params ... n_gpu_layers already set by user" is llama.cpp skipping
  its automatic fit because `-ngl 99` is explicit; not an error.

- `longctx_6600` is the daytime layout: Courage keeps working, only camera vision goes dark. It is the smallest
  context; if 32K proves too tight for real tasks, moving the embedder to CPU during the lease frees ~0.55 GiB
  (~+20K at q8_0/q4_0).
- `longctx_max` is the overnight / `stonesage:stack_idle` layout. The split works for context because each GPU
  holds the KV of its own layers, so both cards' free memory pools.
- Later experiment: `longctx_6600` + mmproj could answer camera questions with Bonsai's own vision, but a camera
  look would queue behind multi-minute loop prefills on a single slot. Not in the first version.

**Measured 2026-09-27 06:46, `longctx_6750`** (PTQ1_0, prism-b10743, RX 6750 XT alone, K/V q8_0, FA on;
results `/root/bench-longctx-6750-20260927-054606`):

| depth | prefill (pp512) | decode (tg128) |
| --- | --- | --- |
| 0 | 126.4 tok/s | 39.4 tok/s |
| 8K | 117.9 tok/s | 37.2 tok/s |
| 32K | 94.9 tok/s | 33.3 tok/s |
| 131K | 51.6 tok/s | **8.9 tok/s** |

- Server at `-c 131072`: **10.16 GiB VRAM** on the 6750 XT, 155 MiB GTT (no meaningful spill). Matches the upstream
  PR #188 numbers at short context (39.4 vs their ~40 tok/s); this card holds up much better than the 6600.
- Needle at 84.5K tokens: **found**; 15.8 min prefill (89.3 tok/s average), then 26.6 tok/s decode for the answer.
- **Decode falls off a cliff past 32K** (33 -> 8.9 tok/s from 32K to 131K) even though VRAM never spills. That is
  the memory-bandwidth cost of the growing KV cache dominating the ternary weights' tiny compute cost, not a bug.
  A loop task that fills most of 131K will feel this: budget accordingly, or try q4_0 KV (smaller cache, same
  bandwidth problem but less data moved) and re-measure before treating 131072 as the default `-c`.
- Coordinator + worker came back healthy after the run (confirmed `/health` 200, and a live chat completion).

**Measured 2026-09-27 06:39-08:49, `longctx_max`** (PTQ1_0, prism-b10743, split RX 6750 XT + RX 6600, `-ts 11,7`,
K/V q8_0, FA on; results `/root/bench-longctx-max-20260927-063929`):

| depth | prefill (pp512) | decode (tg128) |
| --- | --- | --- |
| 0 | 101.3 tok/s | 20.7 tok/s |
| 32K | 77.9 tok/s | 18.3 tok/s |
| 131K | 41.4 tok/s | 13.9 tok/s |
| 245K | **crashed** | **crashed** |

- **The 245760-depth step crashed the whole `llama-bench` process**: `vk::DeviceLostError` / "The CS has been
  cancelled because the context is lost" from RADV, aborted (core dump). The split layout never reached the server
  start or needle steps at 245K, so **`longctx_max`'s advertised 262144 context is unconfirmed and currently
  unsafe to schedule as a lease**: back it down to something proven (131072 for now) until this is root-caused.
  The script's cleanup trap still fired correctly: coordinator, worker and vision all came back and were verified
  healthy afterwards (`/health` 200 on all four ports, a live coordinator chat completion, GPU temps back down to
  51 °C / 37 °C). No VM reboot or GPU reset was needed - RADV recovered the lost context on its own.
- Splitting genuinely costs short-context speed relative to the 6750 XT alone (39.4 -> 20.7 tok/s decode at depth
  0): the 6600 side of the split is the slower partner and the layer split makes every token cross both cards.
  So `longctx_max` buys context ceiling, not speed - use it only when a task actually needs more than ~131K.
- Likely causes to check before retrying at 245K: whether `-ts 11,7` is right at this depth (one card may be
  running out of VRAM first and hitting a driver-level failure instead of llama.cpp's own OOM handling); try a
  smaller batch (`-ub 256`) at high depth; instrument the bench script to poll fdinfo on both cards every 10 s
  during the depth sweep (not just after), so a future crash shows which GPU ran out first.

- **Prefill is the real limit**: ~200-300 tok/s (6750) means 128K tokens takes 7-10 min. The loop keeps one slot per
  task (`-np 1`), keeps the prompt prefix stable (contract + files first, attempts appended), and never re-sends a
  context (`--cache-reuse`).

### B. Engine lease (StoneSage, `backend/engine_lease.py`, new)
Why not an engine profile: `model_loader` keeps each unit's existing binary and reads its option schema from
`/usr/local/bin/llama-server`, so it can't move the coordinator onto the fork binary. It also can't express "stop
two units, start a third". The lease is a small, separate mechanism with a dead man's switch:

- Layouts live in `config.json engine_layouts` (no model or unit names in code):
  ```json
  "engine_layouts": {
    "longctx_6750": {"unit": "llama-longctx.service", "evicts": ["llama-coordinator.service", "llama-worker.service"],
                     "stand_in": "courage_lite", "url": "http://192.168.1.105:8005", "when": "idle"},
    "longctx_6600": {"unit": "llama-longctx-6600.service", "evicts": ["vision-server.service"],
                     "url": "http://192.168.1.105:8005", "when": "any"},
    "longctx_max":  {"unit": "llama-longctx-max.service",
                     "evicts": ["llama-coordinator.service", "llama-worker.service", "vision-server.service"],
                     "stand_in": "courage_lite", "url": "http://192.168.1.105:8005", "when": "idle"}
  },
  "engine_stand_ins": {
    "courage_lite": {"unit": "llama-courage-lite.service", "url": "http://192.168.1.105:8006",
                     "replaces": "coordinator", "eval_passed": null}
  }
  ```
- `POST /api/engines/lease {layout, ttl_s, reason}` checks that nobody holds a lease and that the layout's `when`
  gate holds, and refuses if an evicted engine is in use (Courage turn < 60 s old for coordinator; a camera look or
  patrol sweep in progress for vision) unless `force`. It then starts the layout's unit (`Conflicts=` stops the
  evicted ones), waits for `/health` + `/props`, and returns `{lease_id, url, expires}`.
- `POST /api/engines/lease/<id>/renew` (human only, see below), `POST /api/engines/lease/<id>/release`.
- If the layout has a `stand_in` whose `eval_passed` is set, the lease starts it before evicting the coordinator
  and switches Courage's LLM URL to it (Courage-lite, section B2); otherwise Courage goes offline politely.
- **Auto-revert**: when a lease expires unrenewed, or StoneSage restarts with an orphaned lease on disk
  (`data/engine_lease.json`), it starts the layout's `evicts` units again (which stops the longctx unit) and
  checks their `/health`. So Courage and vision cannot stay down because a loop or Claude session died.
- While leased, evicted engines answer honestly instead of timing out: Courage says "The big brain's on loan until
  HH:MM"; camera_look says vision is lent out until HH:MM and falls back to Frigate's object list without the VLM;
  patrol skips vision for the lease.
- **Hourly, with a human in the loop.** A lease lasts **60 min**. Only a person can renew it; Claude Code and the
  loop worker cannot. At minute 50 StoneSage sends a check-in to John's phone (the `push_approvals` path: HA mobile
  notification with buttons) and to the watch (watch bridge approvals). The check-in carries the loop's short report
  (`job 3f2a: iter 7, 18/20 tests green, 212K local tokens, no escalations`) and two buttons, **Another hour** /
  **Stop**. No answer by minute 60 means stop. That is the dead man's switch: the lease ends, the loop worker
  checkpoints (commits WIP in its scratch clone + saves the transcript summary) and pauses, the engines revert, and
  the job resumes from the checkpoint at the next lease.
  Nights: an explicit up-front approval "run until 07:00" (asked from the phone/watch or the web UI, capped at 10 h)
  replaces the hourly taps for that window; the check-ins still arrive, but silence means continue until the cap.
- **Hands-off (John's call, 2026-09-26).** A person can hand a job off to run **until it completes or a person
  interrupts it**, with no hourly renewals. Granted only by a human: an "Hands-off until done" button on the check-in,
  on the watch, or in the web UI (Claude Code and the loop worker cannot grant it or ask for it without John tapping).
  While hands-off:
  - the lease has no expiry; it ends when the job ends (green, or stopped by its own breakers/caps: `max_iters`,
    `no_change`, `same_failure`, `scope`) or when a person presses **Stop** (phone, watch, web, or Courage "stop the
    loop");
  - hourly check-ins still arrive, but as information with a **Stop** button only; silence means continue;
  - the dead man's switch stays for failures, not for silence: if the loop worker's heartbeat (every 60 s) is missing
    for 5 min, or the longctx engine fails `/health` for 5 min, the lease reverts as usual. A crash never leaves
    Courage on the spare brain indefinitely;
  - a job's `max_minutes` still applies if the contract set one; a hands-off grant can clear it (the button says so).
  Traced as `lease` events `handsoff_granted` / `handsoff_stopped` with who and from which surface.
- Traced as `kind: lease` (acquire, renew, release, expire, revert_failed) in the existing trace.
- Sampling and `reasoning_effort` are per-request fields, not restarts. That is the cheap "hot swap". A real model
  swap is a lease with another layout (a table in `config.json engine_layouts`, so no model names go in code).

### B2. Courage-lite: a small stand-in brain during a lease
`longctx_6750` and `longctx_max` take the 6750 XT from Courage. Instead of going dark, Courage switches to a small
model on VM 102's **CPU** (`llama-courage-lite.service`, :8006; draft in `systemd/disabled/`). CPU, not GPU: it takes
nothing from Bonsai's context, and it works the same in both layouts. VM 102 has 10 vCPUs (i7-12700K, AVX2 +
AVX-VNNI) and ~9 GB RAM free; a 4B Q4_K_M needs ~3 GB.

Candidate: **Qwen3-4B-Instruct-2507** Q4_K_M. Same Qwen3 chat template and native tool-call format as the
coordinator (Qwen3-14B), so Courage's prompt and tool schemas carry over unchanged. Not the models already on disk:
`qwen2.5-coder-3b` is a coder with weak tool choice, and `home-3b-v3` is an HA fine-tune with its own
service-call format, not OpenAI-style tools. Small models are documented to fail on long tool chains, long tool
descriptions and several tools per request, which is exactly Courage's shape. So this is a candidate to measure,
not a pick.

"Safely" is built in, not assumed:
1. **Reflexes don't need the LLM.** Bare on/off orders go through `courage/reflex.py` and the learned reflexes as
   today, with full reliability, whichever brain is loaded.
2. **Every action asks while Courage-lite is the brain.** `is_direct_command` is ignored in lite mode: HA calls,
   notifications and announcements all go through the Yes/No approval (web buttons, phone, watch). Reads (states,
   presence, trace) run freely. Unlock / open garage already always ask.
3. **Gate by eval.** The lease uses the stand-in only if `eval_passed` is set in config, and it's set only after
   Courage's live tool-choice eval (the 42 cases) runs against :8006 with **zero wrong actions** (a wrong action
   is worse than a refusal) and >= 36/42 right tool. It also needs a latency check: warm turn p50 <= 8 s on CPU.
4. **Honest persona line.** The prompt gains one sentence while lite: "You're running on the spare brain until HH:MM;
   keep it short, and say so if a question needs the full one." Replies are capped at 400 tokens (companion stories
   wait for the full brain).
5. Traced: Courage records get `brain: lite` so the trace summary can compare lite vs full turns.

**Measured 2026-09-26 22:50** (Qwen3-4B-Instruct-2507 Q4_K_M, CPU, 6 threads, `llama-courage-lite.service` on :8006,
`COURAGE_EVAL_URL=http://192.168.1.105:8006/v1 python -m unittest tests.live.test_courage_tool_selection`):
- Single turn **38/42 (90%)**, mid-conversation **36/42 (86%)**, **wrong actions 0** in both. Coordinator
  (Qwen3-14B): 42/42 and 42/42.
- Latency p50 **3.75 s**, p95 18.7 s (cold prefill of Courage's prompt on CPU).
- Every miss answers without a tool instead of looking: "When did you last see Kylo?" and "Did you see anyone around
  before I got here?" (presence_now); "What oil does the BMW take?", "How does Savannah take her coffee?", "Remind me
  what coolant the BMW needs." (memory_search); "Text Savannah that I'm running late." (notify); plus one extra
  ha_get_states on "Good morning". So it is **safe (never acts wrongly) but can answer from nothing**, which is a
  hallucination risk on presence and memory questions.
- Gate (>= 36/42, zero wrong actions, p50 <= 8 s): **passes** (mid-conversation exactly at the line).
- Follow-up before relying on it: in lite mode, a deterministic pre-route for "where is / did you see / last see"
  (-> presence_now) and "what/which ... take/need / remind me" (-> memory_search), the same way `reflex.py` skips
  the LLM for on/off, then re-run the eval.

Code change: `courage/agent.py` takes `llm_url` at construction (and the ":8001 isn't answering" message is
hardcoded), so the lease needs a small hook: an `llm_url` provider read on each turn, plus a `lite` flag for rules 2
and 4.

### B3. Autopilot: does a green job merge itself, or wait for review? (2026-09-27, John's call)
A second toggle, independent of hands-off (B decides whether a job needs renewing to keep running; this decides
what happens to its output). Two axes, not one switch - a job can run all night hands-off and still stop at a
reviewable PR rather than land on its own:

- Job contract field `merge_mode`: `"review"` (default) or `"auto"`. `review` means a green job opens a PR against
  `ref` and stops - nothing lands without John looking at the diff. `auto` means the loop worker merges straight to
  `ref` once tests pass and no breaker has fired; tests are the only gate.
- If the contract doesn't set `merge_mode`, it inherits the **session default** - a StoneSage setting any client can
  flip (Architecture, above). `review` ships as the default, matching the existing habit of testing before pushing
  rather than pushing on faith.
- Toggle surface: **`/autopilot on` / `/autopilot off`**. Considered `/headlessloop` / `/humaninloop` first and
  rejected them: neither reads as an obvious opposite of the other at a glance, and neither self-documents months
  later without checking help text. Mirrored as a checkbox wherever a job gets submitted - same word, same meaning,
  every surface.
- **`approver_id` on every lease, hands-off grant, and merge decision** - who granted it, from which surface.
  Single approver for now (John's call, 2026-09-27): the field always holds `"john"` today, but a second approver
  later is a matter of adding rows to whatever table holds this, not restructuring the toggle, the trace schema, or
  the approval UI. Nothing else in the design assumes there is exactly one approver.
- Traced as `loop` events `merge_auto` / `merge_review_opened`, each carrying `approver_id` and `merge_mode`.

### C. Loop worker (VM 102, `server setup/cluster-bridge/local_loop_worker.py`, :8771)
Modelled on `frontier_worker.py` (scratch clone per job, diff out, one job at a time, bearer token, LAN-only).
Reached only through StoneSage's job routes (Architecture, above) - never called directly by Claude Code or anything
else, so its state is never visible from just one surface.

Job contract (`POST /api/loop/jobs`, proxied by StoneSage to the worker's own `POST /jobs`):
```json
{
  "repo": "/srv/loop/repos/stonesage.git", "ref": "main",
  "task": "…spec…",
  "allowed_paths": ["StoneSage/backend/foo.py"],
  "read_paths": ["StoneSage/backend/bar.py"],
  "protected_paths": ["tests/test_foo.py"],
  "test_cmd": "python tests/run_tests.py -k foo",
  "max_iters": 12, "max_minutes": 90, "reset_after_fails": 4,
  "engine_url": "http://127.0.0.1:8005", "reasoning_effort": "medium",
  "merge_mode": null, "approver_id": "john"
}
```
`merge_mode: null` inherits the session default (section B3); an explicit `"review"` or `"auto"` overrides it for
just this job.

Loop per iteration:
1. The prompt is contract + read/allowed file contents (a stable prefix, so it's cached), then the latest attempt's
   test failure (trimmed to the first failing test, max 2K chars).
2. The model answers with whole-file replacements or unified diffs for `allowed_paths` only (checked
   deterministically, and edits elsewhere are rejected). A small tool set: `read_file`, `write_file`, `run_tests`,
   `done`.
3. Run `test_cmd` in the clone (timeout, no network; same sandboxing idea as `run_tests.py`).
4. Green: stop. Red: append the failure and retry. After `reset_after_fails` failures in a row, start a new context
   from the contract plus a one-paragraph "what didn't work" summary written by Bonsai.

Deterministic loop breakers (the known Bonsai failure modes: reasoning loops, "fixed it" claims with no change):
- **no_change**: the attempt's diff is identical to the previous one, or empty.
- **same_failure**: the same failure signature (test id + first assertion line, hashed) 3 times.
- **repetition**: n-gram repetition in the output above a threshold. Stop the stream (the agent-nudge idea).
- **scope**: an edit outside `allowed_paths`, or any edit to `protected_paths` (tests are the oracle, so the model
  must never touch them).
- **caps**: max_iters, max_minutes, output tokens.

Report (`GET /api/loop/jobs/<id>`, the only thing frontier reads by default):
```
job 3f2a: GREEN after 7 iters (41 min, 212K local tokens, 0 escalations)
diff: +142/-30 in 2 files (both allowed); tests 18/18; protected files untouched
merge: auto -> merged to main | review -> PR #47 opened, waiting on john
```
or
```
job 3f2a: STOPPED same_failure at iter 5: tests/test_foo.py::test_tz "expected 14:00, got 13:00"
```
`GET /api/loop/jobs/<id>/diff` and `/attempts/<n>` exist, but frontier fetches them only on escalation.

### D. MCP tools for Claude Code (add to `cluster-work-mcp`) - thin wrappers over StoneSage routes
Each tool is one HTTP call to StoneSage (Architecture, above); none of this state lives in the MCP process.
- `local_loop_submit(contract)` -> job id (`POST /api/loop/jobs`)
- `local_loop_status(job)` -> the short report above (`GET /api/loop/jobs/<id>`)
- `local_loop_detail(job, what=diff|failure|attempt, n?)`: the escalation path
- `engine_lease(layout, ttl_s, reason)` / `engine_release(lease_id)` / `engine_lease_status()` (`/api/engines/lease*`)
- `autopilot_set(mode)` / `autopilot_status()`: the session default from B3 (`/api/loop/autopilot`)

Claude Code then runs: write the tests -> lease -> submit -> check status occasionally -> if `merge_mode` was
`review`, read the diff and merge by hand once satisfied; if `auto`, just confirm it landed; read the failure only
when escalated -> release.

### E. Model Tryout pipeline: find the best local model, click and go (2026-09-27, John's call)
New Hugging Face distillations that fit 12 GB VRAM show up every couple of days, and small coder/agentic models
(3-8B) matter just as much as the big ones - they're candidates for the loop's executor role and for Courage-lite
(B2). This reuses existing infrastructure rather than building a parallel one:

1. **A picker, not a search box.** Paste a Hugging Face repo URL, or watch a short list of quant-publisher channels
   (the ones already used for Bonsai: `bartowski`, `unsloth`, `mradermacher`, PrismML). No manual HF browsing.
2. **Dynamically hardware-aware: no hardcoded ceiling, no lower bound.** Before every search, read live free VRAM
   per GPU - the same `gpu_metrics.sh` counters Prometheus scrapes, or fdinfo directly for a to-the-second figure -
   and whether a lease is currently held. That live number is the filter, not a config constant.
   - A fully occupied GPU narrows the search to nothing, or to CPU-only candidates; freeing a GPU (via a lease)
     grows the search immediately, with no config edit.
   - No size floor: a 3B agentic coder and a 27B distillation are scouted the same way. A small model matters for
     Courage-lite and the loop executor exactly as much as a large one matters for long-context tasks.
   - Hardware-portable by construction: the picker never needs a number edited anywhere, whatever GPU(s) run it -
     the same principle as "no model names in code" for `engine_layouts`.
3. **Fit before downloading the weights.** Read just the GGUF header first (HF supports range requests) for
   architecture, layer/head counts and native context. Pick the largest quant that plausibly fits the current free
   VRAM, using the same KV-cost math validated on Bonsai (section A). Download into a scratch directory
   (`/opt/models/tryout/` on VM 102 - never `/opt/models/`, so a bad or malicious download can't collide with
   anything live).
4. **Load on a scratch port, lease-gated.** A `tryout` engine slot (:8009) that the picker starts and stops, guarded
   by the same `Conflicts=` + engine-lease mechanism as the longctx layouts (section B): it can only run when a GPU
   has been deliberately freed for it, and it reverts the same way on expiry or crash.
5. **Auto-tune context/batch by search, not a guess.** Start conservative, load, check `/health`; on OOM or
   device-lost (section A's `longctx_max` crash is exactly the failure class this guards against), back off; on
   success, grow. Reuses `model_loader.plan()`'s sizing math and `apply()`'s rollback pattern rather than
   duplicating either.
6. **A standard test battery, run automatically:**
   - Repetition/loop-detection prompt (the same failure class B2 and section C's breakers already watch for).
   - A short deterministic reasoning/coherence check - never an LLM judge (CLAUDE.md).
   - The Courage tool-choice eval (`tests/live/test_courage_tool_selection.py`, `COURAGE_EVAL_URL=...`) when scouting
     a Courage-lite candidate; the loop worker's breaker battery when scouting an executor.
   - Speed at a few context depths, using `bench_longctx.sh`'s pattern generalized to take any model/port instead of
     staying Bonsai-specific.
7. **One report card per model, then discard.** Quant that fit, max stable context, decode/prefill speed, pass/fail
   per test, VRAM used. Nothing stays loaded once the card is written; John decides whether to keep the weights or
   delete them.
8. **Same server, same clients** (Architecture, above): the picker is StoneSage routes (`POST /api/tryout/search`,
   `POST /api/tryout/jobs`, `GET /api/tryout/jobs/<id>`), reachable from the web UI, a Claude Code MCP tool, or a
   bare status check from the phone/watch - never a tool only one surface can drive.

## Measuring the token saving (Phase 6 style: prove it, don't assume it)
- Every job records frontier tokens spent on it (contract + status reads + detail reads) vs local tokens.
- Baseline: the same 5-10 tasks done by Claude Code alone (tokens from `/cost` or the transcript).
- Success = frontier tokens per green task <= 30% of baseline, at equal test pass rate. If proofreading still
  dominates, the escalation triggers are too loose.

## Rollout
1. DONE 2026-09-26 22:44: `prism-b10743-adfffbe` built into `/opt/llama-prism/<tag>` + `current` symlink (script 04);
   RADV reports `integerDotProduct4x8BitPackedSignedAccelerated = true` on both cards. PTQ1_0 in `/opt/models/prism/`. Found on VM 102
   2026-09-26: an older prebuilt `prism-b10709` in `/opt/llama-prism` (before the int-dot kernel, left untouched) and
   `/opt/models/Ternary-Bonsai-2-27B-PQ2_0.gguf` (7.21 GB, 2026-09-19), which can stand in for a first bench if the
   PTQ1_0 download is a problem.
2. DONE 2026-09-27: all three layouts benchmarked (see section A). `longctx_max` at 245K crashed the driver
   (device lost) and needs a follow-up before it's trusted at its full 262144 window; `longctx_6750` and
   `longctx_6600` are solid at their measured depths.
3. DONE 2026-09-26 (eval passes, see B2; pre-route follow-up open). Courage-lite: download Qwen3-4B-Instruct-2507 Q4_K_M, install `llama-courage-lite.service` (disabled), run the
   tool-choice eval + latency check against :8006 **while the coordinator is still up** (CPU only, nothing evicted).
   Set `eval_passed` only on a clean result.
4. Engine lease in StoneSage as HTTP routes (Architecture, above): layouts, stand-in, hourly check-in via phone +
   watch, checkpoint on expiry, auto-revert, `approver_id` on every grant. Unit tests: an unrenewed lease reverts at
   60 min; a renew call without a human tap is refused.
5. Loop worker (VM 102) + StoneSage job routes + thin MCP wrappers (sections C, D), `merge_mode` / `approver_id`
   (B3), `/autopilot` toggle mirrored in the web UI. First job: a small real task that already has tests.
6. Token measurement over 5-10 tasks and a go/no-go decision.
7. Model Tryout pipeline (section E): picker + dynamic-VRAM search + fit/download/test loop, reusing the lease
   mechanism and `model_loader.plan()`. Useful immediately as a way to find a better Courage-lite or loop-executor
   candidate than what's been measured so far.
8. Later: MTP speculative head (`--spec-type draft-mtp`, seen working on Vulkan on a BC-250); q4_0 KV at 262K;
   the "Bonsai explores, frontier patches" mode.

## Open questions for John
1. ~~Courage during a lease~~: decided 2026-09-26: Courage-lite on CPU (B2), eval-gated; offline with a polite
   message if it fails the eval.
2. When can leases run: any time, or only when `stonesage:stack_idle` holds / overnight?
3. ~~Lease TTL~~: decided 2026-09-26: 60 min, renewed only by a human tap (phone/watch), silence = stop. Still
   open: the night pre-approval cap (proposed 10 h) and whether a lease may be taken while someone is home.
   Hands-off (run until done or a person stops it): decided 2026-09-26, section B.
4. ~~Merge autonomy~~: decided 2026-09-27: decoupled from hands-off (section B3). Per-job `merge_mode` (`review`
   default / `auto`), session default toggle (`/autopilot on|off`), `approver_id` recorded on every grant, single
   approver ("john") for now with room for more later.
5. ~~Harness access surface~~: decided 2026-09-27: StoneSage's backend is the one server; Claude Code, the web PWA,
   phone and watch are thin clients of it (Architecture, above) - never of each other or of VM 102 directly.

## Risks
- The fork is a moving target (the key kernel landed 2026-09-24). Pin the exact release tag in script 04 and
  rebuild only on purpose.
- The loader's library reads GGUF headers: tensor types 142/143 may confuse `hw_probe.py --models`. Keep Bonsai
  under `/opt/models/prism/` and check the library view doesn't break.
- Independent tests saw Bonsai loop in reasoning and claim fixes it hadn't made. The breakers above target exactly
  this. If the loop stops with `no_change`/`same_failure` on most jobs, Bonsai isn't good enough and the design
  stands with a different executor.
- Long-context decode speed on RDNA2 falls off sharply past 32K (measured, section A) even without VRAM spill;
  budget loop tasks accordingly rather than assuming flat speed to a layout's advertised ceiling.
- `longctx_max`'s 262144 context is unconfirmed - it crashed the driver at 245K (section A) and is currently capped
  at 131072 until root-caused.
- Model Tryout (section E) downloads GGUF files from arbitrary Hugging Face repos on request. A GGUF is data, not
  executable code, and it only ever loads through the PrismML/mainline `llama-server` binaries already vetted for
  this stack - but a repo can still be mislabeled, mis-quantized, or from an untrustworthy publisher. Scratch
  directory, lease-gated scratch port, and a discard-by-default report card (step 7) all exist so a bad download
  never reaches a live engine or persists without John choosing to keep it.

## Sources
- Model: https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf (+ KNOWN_ISSUES.md)
- Fork/demo: https://github.com/PrismML-Eng/Bonsai-demo, https://github.com/PrismML-Eng/llama.cpp (branch `prism`)
- 6750 XT Vulkan numbers: https://github.com/PrismML-Eng/llama.cpp/pull/188 (superseded by #238, release prism-b10735)
- RDNA2 slow path: https://github.com/PrismML-Eng/llama.cpp/issues/259; ROCm on RDNA2: .../issues/264
- MTP: https://huggingface.co/sudoingx/Ternary-Bonsai-2-27B-PTQ1_0-MTP-GGUF, https://github.com/PrismML-Eng/Bonsai-demo/issues/221
- KV math: https://vramcalculator.com/bonsai-2-27b-vram-requirements/
- Real-world test: https://www.mindstudio.ai/blog/bonsai-2-27b-real-world-test
- Explore/patch split: https://www.ai21.com/blog/better-and-cheaper-together-open-models-explore-frontier-models-patch/
- Loop engineering: https://llmconfigurator.com/en/guides/coding-agents/loop-engineering-local-llm
- OpenCode architecture (client/server, SDK, local-model self-host): https://github.com/opencode-ai/opencode,
  https://opencode.ai/docs/sdk/, https://opencode.ai/docs/models/
