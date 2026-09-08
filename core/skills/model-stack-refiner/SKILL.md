---
name: model-stack-refiner
description: >-
  Automate empirical benchmark calibration loops, hyperparameter tuning, and reliability
  verification for any open-weights LLM loaded into the local dual-GPU cluster stack.
  Activate whenever new models are deployed, sampling parameters need fine-tuning,
  hallucinations or shallow outputs are detected, or to verify if a model configuration
  meets the Composite Intelligence Index (CII >= 8.5) required for unattended 24/7 autonomous execution.
---

# Model Stack Parameter Refiner & Calibration Loop

This skill guides the automated, empirical calibration of sampling hyperparameters, KV cache settings, and cognitive system prompt anchors for any model loaded into the local homelab stack (e.g. Qwen 2.5 Coder 14B on `:8001`, 3B Worker on `:8002`, or any new open-weights model swapped into the cluster).

The primary objective is to iterate across diverse cognitive domains until the models achieve a measurable, certified level of **Composite Intelligence** where you can confidently let them run 24/7 hands-free.

---

## 1. The Hands-Free Autonomy Standard: Composite Intelligence Index (CII)

Before granting 24/7 unattended autonomous clearance, a model configuration must score $\\ge 8.5 / 10$ across the 5 canonical benchmark domains with **zero physical or spatial hallucinations**:

$$\\text{CII} = (0.35 \\times \\text{Factual Rigor}) + (0.30 \\times \\text{Invariant Preservation}) + (0.20 \\times \\text{Self-Critique Calibration}) + (0.15 \\times \\text{Textural Density})$$

### Core Verification Pillars:
1. **Factual & Spatial Rigor (Weight 0.35)**: Zero tolerance for fabricated physical or mathematical rules (e.g., verifying rabatment derivations, root rectangle geometry, and memory alignment constraints against ground truth).
2. **Semantic Invariant Preservation (Weight 0.30)**: Solves full algorithmic state spaces and concurrency hazards (e.g. all topological permutations, ABA problem mitigation via tagged pointers or hazard pointers) rather than shortcutting with simple greedy heuristics.
3. **Self-Critique Calibration (Weight 0.20)**: The local evaluator model must penalize subtle flaws rather than giving superficial 9/10s based on academic tone. $|\\text{Local Score} - \\text{Frontier Score}| \\le 1.2$.
4. **Textural Density & Anti-Looping (Weight 0.15)**: Rich, expressive domain-specific taxonomy without corporate fluff, generic summaries, or lexical repetition loops.
5. **Throughput & VRAM Stability**: Coordinator $\\ge 35\\text{ tok/s}$, Worker $\\ge 60\\text{ tok/s}$ with zero out-of-memory errors or context degradation.

---

## 2. Standard Operating Procedure: Running the Calibration Loop

### Step 1: Probe Active Stack & Cluster Health
Verify that the cluster services are online:
```powershell
curl -s http://127.0.0.1:8001/health
curl -s http://127.0.0.1:8002/health
curl -s http://127.0.0.1:6333/readyz
```

### Step 2: Execute the Automated Calibration Suite
Run the closed-loop refiner script from Windows or directly on VM 102:
```powershell
# From your workstation:
powershell -ExecutionPolicy Bypass -File "C:\Users\admin\OneDrive\Documents\.ai\.agents\skills\model-stack-refiner\scripts\run_calibration.ps1"
```
Or execute directly via Python:
```bash
python scripts/calibration_loop.py --target-cii 8.5 --max-rounds 3
```

### Step 3: Frontier Audit Arbitration
The script automatically dispatches each benchmark probe to the dual-GPU cluster, benchmarks throughput, gathers the local 14B comparative evaluation, and passes the outputs through the **Tier-1 Frontier Model (Antigravity)** to audit truthfulness and score the CII.

### Step 4: Lock-In & Engine Sync
When a parameter set satisfies $\\text{CII} \\ge 8.5$:
- The script automatically writes `calibrated_profiles.json`.
- Updates `SAMPLING_PROFILES` in `/home/clusteradmin/cluster-bridge/autonomous_engine.py`.
- Syncs the certification summary to your Obsidian vault (`Autonomous Thinking/Calibration/`).

---

## 3. Diagnostic & Tuning Decision Matrix

When a model fails one or more pillars of the benchmark battery, follow this targeted adjustment matrix:

| Observed Failure Mode | Root Cause | Corrective Action |
| :--- | :--- | :--- |
| **Shallow, generic boilerplate, lacking technical texture** | Greedy decoding (`\\tau \\le 0.20`) or missing dynamic truncation. | Increase $\\tau$ to `0.65 - 0.75`, set `min_p: 0.06`, add `presence_penalty: 0.20`. Anchor system prompt with principal architect persona. |
| **Invented formulas or spatial hallucinations (e.g. geometric steps)** | KV Cache 4-bit attention noise or high temperature with loose sampling. | Tighten `min_p` to `0.08`, reduce $\\tau$ to `0.45 - 0.55`. In `systemd/llama-coordinator.service`, upgrade KV cache from `-ctk q4_0` to `-ctk q8_0`. |
| **Evaluator leniency (awarding 9/10 to broken code or bogus math)** | Evaluator lacks structured rubric and evaluates based on lexical cadence. | Update evaluator system prompt: mandate explicit checklist verification against ground truth assertions before assigning numerical scores. |
| **Repeated phrases, token cycling, or infinite list looping** | Abliterated model ungrounded repetition penalty. | Set `presence_penalty: 0.25` and `repetition_penalty: 1.06`. Ensure `frequency_penalty` remains $\\le 0.05$ to avoid breaking code syntax. |
| **Slow inference or VRAM spill into system RAM** | Context size too large for GPU offload or unquantized KV cache. | Set context `-c 8192`, offload all layers (`-ngl 99`), and verify with `rocm-smi` that VRAM utilization remains $< 90\\%$. |

---

## 4. Supporting Resources

- [Benchmark Suite Reference](./references/benchmark_suite.json): Curated 5-domain test battery with explicit invariant assertions and hallucination traps.
- [Hyperparameter Sensitivity Guide](./references/hyperparameter_heuristics.md): In-depth mathematical mechanics of Min-P, presence penalties, and KV cache precision.
- [Calibration Test Runner](./scripts/calibration_loop.py): Automated test runner script.
