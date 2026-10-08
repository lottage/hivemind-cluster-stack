# Local AI Stack — Implementation Handoff

Compiled from a design conversation. This is a spec for four interlocking
pieces of work, in dependency order. Each section states what's decided,
what's still open, and what file(s) already exist to start from.

---

## 1. Unified API Gateway (LiteLLM)

**Status:** Config drafted, not yet deployed.
**Files:** `litellm_config.yaml`, `custom_guardrails.py` (attached separately
in this conversation — Claude Code should ask the user to paste them in if
not already present in the repo).

Fronts four local endpoints (coordinator :8001, worker :8002, BGE embeddings
:8003, vision :8004) plus the Antigravity/Gemini frontier tier, behind one
OpenAI-compatible API on :4000.

Key constraints baked into the config:
- Host addresses via env vars only — never hardcode 192.168.x.x (zero-leak rule)
- `custom_guardrails.py` pre-call hook rejects BGE inputs over ~512 tokens and
  vision frames over 640px *before* they hit the backend and 500
- Fallback currently routes failed coordinator calls straight to frontier —
  **open decision:** this burns frontier tokens on transient local failures
  (VRAM spill, OOM). Consider retry-on-worker before frontier fallback.

**This gateway is the eventual home for the escalation ladder in Section 4.**

---

## 2. Idle Detection (Prometheus)

**Status:** Design complete for current stack state, ready to deploy.
**Files:** `gpu_idle_collector.sh`, `prometheus_idle_rules.yml`.

Purpose: detect safe windows for LoRA/QLoRA fine-tune runs without
interrupting home automation traffic.

- `gpu_idle_collector.sh` runs on the Proxmox **host** (pve/bigserv, not in
  a container) reading amdgpu sysfs `gpu_busy_percent`, written to
  node_exporter's textfile collector directory
- Composite signal `safe_to_finetune:partial` = GPU idle (< 10% busy, 5m avg)
  AND llama-server active slots == 0, on both coordinator and worker
- **Card index mapping in the script is a placeholder** — verify
  `/sys/class/drm/card*/device` ordering against actual hardware before
  deploying; it is not guaranteed stable across reboots
- Marked "partial" because a third signal (assembly hall / agent activity)
  is currently N/A — the assembly hall is shelved, so GPU+inference idle is
  presently a *complete*, accurate signal, not a stopgap
- **Future work, not yet needed:** when the assembly hall is un-shelved, it
  must log to its own dedicated CouchDB database, separate from the Obsidian
  vault sync database, so a future idle signal can watch its `_changes` feed
  without false positives from unrelated vault writes

---

## 3. Model Provenance Registry (CouchDB)

**Status:** Schema designed, not yet built. CouchDB is running locally
(already used for Obsidian vault sync) — use a new dedicated database,
do not share with the vault database.

**Database:** `model_provenance`, one document per model, keyed by GGUF
SHA256 hash (not filename — filenames drift across requants, the hash is
the real identity).

```json
{
  "_id": "sha256:<gguf-file-hash>",
  "loaded_at_path": "<local path>",
  "hf_repo": "<repo id>",
  "hf_base_repo": "<upstream repo if quant/merge/derivative, else null>",
  "architecture": "<from GGUF header>",
  "quantization": "<from GGUF header>",
  "lineage": {
    "type": "base | merge | abliterated | fine-tune-injection | unknown",
    "notes": "<frontier-authored summary of what was modified and why it matters>"
  },
  "quant_chart_summary": "<frontier-authored digest of the repo's perplexity/size table>",
  "recommended_params": {
    "quant": "<chosen level>",
    "context_window": 0,
    "ctk": "q4_0",
    "ctv": "q4_0",
    "temperature_range": [0.0, 0.0],
    "min_p_range": [0.0, 0.0],
    "presence_penalty_range": [0.0, 0.0]
  },
  "engine": {
    "binary": "<llama-server | custom fork name>",
    "binary_repo": "<fork repo URL if non-mainline>",
    "required": false,
    "reason": "<why this specific engine is required, if it is>",
    "verification": "<how the loader confirms the correct binary is in use>"
  },
  "human_approved": false,
  "profile_generated_at": "<ISO timestamp>"
}
```

**Loader flow when a model is selected:**
1. Read GGUF header locally (architecture, quant, context) — offline, instant
2. Frontier model fetches the HF card; if it's a quant/merge/derivative repo,
   follows the link to the base model's card too
3. Frontier model resolves lineage explicitly (base / merge / abliterated /
   fine-tune injection) — this must be stated, not left implicit, since it
   changes sampling recommendations and later correction-worthiness judgments
4. Frontier model reads the repo's quant/perplexity chart against actual
   available VRAM per GPU and recommends a specific quant level
5. Frontier model determines required engine/binary
6. **Full profile presented to the user before any load — nothing loads
   without explicit approval**, consistent with the existing `--approved`
   rule for fine-tuning datasets. `human_approved` starts `false` and only
   flips on explicit confirmation.
7. A re-download or requant produces a new hash → new profile automatically;
   no invalidation logic needed

**Worked example — Ternary-Bonsai-2-27B (prism-ml/Ternary-Bonsai-2-27B-gguf):**
- Ternary (1.72 bits/weight) quant of Qwen3.8-27B, ~5.95GB (PTQ1_0) or
  7.21GB (PQ2_0), Hadamard-rotated weights
- **Hard engine gate required, not just a recommendation:** stock llama.cpp
  either rejects the format outright or silently mis-loads it as Q2_0 and
  produces garbage output with *no error*. The loader must verify the
  running binary is the PrismML-Eng fork (github.com/PrismML-Eng/llama.cpp)
  before allowing this model to serve — block, don't just warn, and do not
  allow a user override given the failure mode is silently-plausible-wrong
  code, not a crash
- No published throughput data exists for AMD/Vulkan (RX 6750 XT / 6600 XT)
  — table only covers NVIDIA + Apple Silicon. Profile should say "no
  benchmark for this GPU family, run `llama-bench` manually" rather than
  guess
- PTQ1_0 vs PQ2_0 pick is genuinely unresolved for this hardware — neither
  published class (Ada/L4 vs Ampere/Hopper/Blackwell) matches these cards
- Reasoning model, thinks at `xhigh` effort by default (`low` isn't actually
  supported, behaves like `xhigh` anyway) — acceptable for coding upsize use
  case where correctness > latency; confirmed NOT intended for home
  automation's fast-turnaround path
- Role in the stack: **coding-assistance upsize only**, loaded when the
  primary coordinator model is outclassed on a coding task — not a
  coordinator replacement

---

## 4. Dynamic Escalation Ladder

**Status:** Design in progress, several dependencies still unbuilt.
Lives behind the LiteLLM gateway from Section 1.

**Core principle: escalation triggers must be objective signals, never the
model self-reporting confidence.** Small quantized models are unreliable at
calibrated self-assessment — same failure class as Qdrant retrieval
rumination (confident-sounding wrong answers, not honest uncertainty).

**Proposed ladder:**
```
local coordinator (14B)
  → Bonsai 2 27B upsize (coding tasks specifically)
  → hand off to another agent (local or Tailscale-reachable remote)
  → frontier arbitration (Antigravity / Gemini)
  → rented external GPU/inference (sanitized payload only — see below)
  → honest "needs a human" response, with attempt history attached
```

**Trigger signals (all currently unbuilt — this is the real prerequisite work):**
- Repetition/loop detection — depends on the nudge tool (currently
  StoneSage-only, "rudimentary," not yet detecting loops in the token
  stream; design work was started and explicitly sidelined mid-conversation
  to return to later)
- Deterministic failure — test/lint/syntax execution results
- Retry exhaustion — same task attempted N times without resolving
- Frontier spot-check disagreement — **currently doesn't exist as a
  discrete event at all.** Frontier arbitration today is a manual user
  click through a front end; there is no autonomous loop and no recorded
  accept/reject verdict. This needs to become a structured event before
  it can function as an escalation trigger or feed the correction-capture
  dataset in Section 5.

**Rented GPU tier — trust boundary, not just another hop:**
- Everything else in the stack is owned infrastructure or an already-vetted
  vendor relationship (frontier). Rented GPU compute is neither.
- Needs its own auth boundary, separate from the Tailscale-everything
  pattern used elsewhere
- Requires a sanitization pass on the outbound payload before it leaves the
  network — strip real IPs/hostnames and any Qdrant-sourced private context
  — consistent with the existing zero-leak rule, extended from docs/configs
  to actual runtime request payloads
- Placed *after* frontier in the ladder deliberately: frontier is trusted,
  rented compute is unknown infrastructure and should be a last resort
  before punting to a human

**Human notification — not yet wired to anything.**
- User wants push notification, "hopefully" — no channel confirmed yet
  (Home Assistant mobile app, ntfy, Pushover, Discord webhook, or
  something StoneSage already has are the live options; none confirmed)
- **Open question for Claude Code to raise with the user directly:** which
  channel to use, since this wasn't settled in the design conversation
- On human-needed exit, the response should carry the full attempt
  history (what was tried, what failed, why it was judged unresolvable)
  rather than a bare "I can't do this"

---

## 5. Correction-Capture Loop (downstream of Section 4)

**Status:** Goal stated, not designed in detail — deferred until Section 4's
frontier-arbitration signal exists, since there's nothing to capture until
frontier's accept/reject verdict is a real event.

Target: (prompt, local output, frontier correction) triples, captured
automatically at the moment frontier corrects a local output — not manual
flagging — feeding periodic LoRA/QLoRA fine-tunes run during
`safe_to_finetune` windows (Section 2), applied as swappable adapters over
existing weights rather than full retraining.

**Still open:** one adapter per failure category (coding-context gaps,
Qdrant retrieval rumination, etc.) vs. one adapter absorbing all correction
types — not decided, affects dataset structure from the start.

---

## Build order recommendation

1. Idle detection (Section 2) — no dependencies, ready now
2. Frontier arbitration as a structured event (Section 4 prerequisite) —
   unblocks both escalation triggers and correction-capture
3. Nudge tool loop detection (sidelined earlier, needs its own design pass)
4. Gateway deployment (Section 1) — can happen in parallel with 2–3
5. Model provenance registry (Section 3) — independent, can happen anytime
6. Escalation ladder wiring (Section 4) — depends on 2, 3
7. Correction-capture (Section 5) — depends on 4
