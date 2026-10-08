# Division 4: Compute and measurement (engines, lease, metrics, Boost)

Part of [the master roadmap](../ROADMAP.md) (Phases 1, 6 and the engine half of 9). Status wins over plans: see [STATE.md](../../STATE.md).

**What it is:** the models, the GPUs they run on, and the numbers that say what the stack can do and when a GPU is free.

**Where the code is:** VM 102 units (`server setup/vm-setup/systemd/`); `StoneSage/backend/` (`engine_controller.py`,
`engine_lease.py`, `engine_profiles.py`, `model_loader.py`, `engine_options.py`, `idle_gate.py`, `provenance.py`,
`system_profile.py`, `boost/`); `server setup/metrics/` (Prometheus on LXC 129); `tests/live/model_eval.py`.

## Where it is now
- Engines: coordinator Qwen3-14B and worker Qwen2.5-Coder-3B on the RX 6750 XT; embedder BGE and vision Qwen2.5-VL-7B on the
  RX 6600. Courage-lite (Granite 4.0 h-tiny, CPU) is the stand-in. Tryout slot :8009 for candidates.
- Prometheus (90 days), per-GPU idle gate, model provenance (sha256, lineage, which build can load it), engine lease with
  auto-revert and phone check-in, escalation ladder, Boost router (all surfaces off, no keys).
- Ternary Bonsai 2 27B benchmarked on all three lease layouts (numbers in the master roadmap, section 9A).

## Next, in order
1. **First live handover** to Courage-lite: a deliberate window behind the idle gate, `longctx_6750`, ask before starting
   (Computer goes to the spare brain). Verify revert, `revert_failed` alarm and the "on loan" wording.
2. **Night window for the two 6750-only model evals** (Gemma 4 12B, Ornith 9B OBLITERATED), chained after the handover test.
3. **Hands-off and night grants** (person-only "run until done"; failure-only dead-man's switches: worker heartbeat 5 min,
   engine `/health` 5 min; night cap 10 h). Designed, not built.
4. **Root-cause the `longctx_max` crash at 245K** (poll fdinfo on both cards every 10 s during the sweep; try `-ub 256`); until
   then it stays capped at 131072.
5. **Tune prefill** (`-ub 1024/2048`, PQ2_0 on the 6750, `--cache-reuse`): prefill is the real long-context limit.
6. **One tiny LoRA** (3B worker or 0.6B draft) before any 14B adapter; ROCm on gfx1031/1032 is unofficial. Needs a stopped
   engine, so it goes through the idle gate and the Model Loader's backup/rollback.
7. **Boost keys and frontier worker** when John provides accounts: they light up the escalation ladder's upper rungs.

## Later
- The Model Tryout picker (Division 7 / Phase 9E): Hugging Face URL in, live-VRAM-driven fit, auto-tuned context, standard
  battery, discardable report card.
- Correction capture for text (needs frontier verdicts recorded as events).
- MTP speculative head; q4_0 KV at 262K.

## Rules for this division
- llama-server: `--device Vulkan0|Vulkan1` (never integers, and it means "first visible": `GGML_VK_VISIBLE_DEVICES` pins the
  card); `--flash-attn on|off|auto` (always a value); `--jinja` for native tool calls; embedder inputs < 950 chars.
- Verify placement with `/proc/<pid>/fdinfo`, not the unit text. No hardcoded GPU, model or engine labels in code.
- A model that needs the Prism fork never replaces the mainline binary.
- Egress: home text goes only to `local` / `no_training` sources; pictures and secrets never leave.
- Only a human renews a lease. VM 102 ignores ACPI shutdown: power it off from inside.

## Done when
A lease can be taken, used overnight and reverted with no human present except the approval taps; every model change has a
recorded eval; the metrics dashboard answers "was the stack idle?" for any past hour.
