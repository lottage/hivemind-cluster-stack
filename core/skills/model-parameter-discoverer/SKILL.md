# Model Parameter Discoverer

name: model-parameter-discoverer
description: Automated empirical discovery, stress-testing, and hyperparameter calibration for any newly loaded LLM on the dual-GPU cluster (:8001 or :8002). Automatically benchmarks conversationality, coding/logic/math accuracy, hallucination resistance, and context window flow, then produces optimal sampling profiles and syncs directly to StoneSage and Obsidian.

---

## Overview

When swapping to a new model (such as Ornith 9B, Qwen 2.5 Coder, Llama 3.1, or experimental abliterated/uncensored checkpoints), manually tweaking temperature, min-p, and penalties takes hours of repetitive prompt engineering.

This skill automates the entire discovery process. It dispatches a battery of targeted probes designed around the 4 key user priorities:
1. **Conversationality & Texture**: Tests natural conversational flow, lexical density, tone, and anti-looping penalties.
2. **Coding, Logic & Math Accuracy**: Verifies complex state-space resolution, concurrency hazards, and algorithmic invariants without heuristic shortcuts.
3. **Anti-Hallucination Gate**: Deceptive probes that trap models with fictitious APIs or fabricated facts; grounded models refute the falsehood while hallucinating models fail.
4. **Context Window & Flow**: Incremental context load test (4k, 8k, 16k) measuring token throughput (`tok/s`), time-to-first-token, and KV cache stability.

## Standard Operating Procedure

### 1. Run Automated Parameter Discovery
Run immediately after switching models via `cluster-model-switcher`:
```bash
python .agents/skills/model-parameter-discoverer/discover_parameters.py --model-name Ornith-9B --port 8001 --apply-to-stonesage
```

### 2. What the Discovery Suite Outputs
- **`optimal_profile.json`**: Locked-in optimal hyperparameters (`temperature`, `min_p`, `presence_penalty`, `repeat_penalty`, `max_tokens`).
- **StoneSage Configuration**: Automatically patches default sampling parameters in `StoneSage/backend/config.json` and LXC 120.
- **Obsidian Calibration Dossier**: Formats a detailed benchmark report in:
  `C:\Users\admin\OneDrive\Documents\obsidian\Autonomous Thinking\Calibration\{model_name}_dossier.md`
- **Qdrant Vector Brain Sync**: Stores verified model boundaries and optimal parameters in `agent_memories` and `codebase_knowledge`.

## Parameter Sweep Targets

| Parameter | Recommended Range | Function |
| :--- | :---: | :--- |
| **`temperature`** | `0.40 - 0.75` | Controls reasoning creativity vs deterministic constraint. |
| **`min_p`** | `0.05 - 0.08` | Dynamic cutoff preventing probability tail collapse without flat top-p truncation. |
| **`presence_penalty`** | `0.20 - 0.30` | Prevents token cycling and repetitive boilerplate in abliterated/uncensored models. |
| **`repeat_penalty`** | `1.08 - 1.15` | Suppresses phrase loops without corrupting programming syntax. |
| **`context_window`** | `8192 - 16384` | Calibrated based on model VRAM footprint on the RX 6750 XT 12GB. |

## 4-Pillar Evaluation Rubric

1. **Coding & Algorithmic Logic**: Solves non-trivial topological ordering and race hazard mitigation. Must preserve state invariants.
2. **Mathematical & Spatial Rigor**: Derives geometric relationships and memory alignments without fabricating non-existent theorems.
3. **Deceptive Probe Grounding**: Refuses trick questions about non-existent commands (e.g. `pvesm format-all-pools --force`).
4. **Conversational Naturalness**: Explains complex concepts with technical depth and zero corporate fluff.
