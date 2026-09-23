# Hyperparameter Sensitivity & Sampling Heuristics for Local Model Stacks

This reference explains the mathematical and empirical mechanics of sampling hyperparameters when running quantized open-weights models (specifically Qwen 2.5 Coder, Llama 3.x, and DeepSeek variants) on local hardware (ROCm / Vulkan / llama.cpp).

---

## 1. Min-P Sampling vs. Top-P (Nucleus) Sampling

### The Top-P Problem
Traditional **Top-P (Nucleus)** sampling sorts candidate tokens by probability and takes the top candidates whose cumulative sum reaches $P$ (e.g., $0.90$).
- **Flat Probability Distribution (High Uncertainty)**: When many tokens have low probability, Top-P includes thousands of plausible noise tokens, leading to hallucinations and nonsense.
- **Peaked Probability Distribution (High Certainty)**: When the top token has $98\%$ confidence, Top-P still includes the next $2-5$ tokens, even if their individual probabilities are miniscule ($0.1\%$).

### The Min-P Solution
**Min-P** establishes a dynamic probability floor relative to the *single most probable token*:

$$P_{\text{threshold}} = \text{min\_p} \times P_{\text{max}}$$

Any token with $P(\text{token}) < P_{\text{threshold}}$ is immediately pruned before sampling.

#### Empirical Impact:
- **High Certainty ($P_{\text{max}} = 0.90$, $\text{min\_p} = 0.05$)**: Threshold is $0.05 \times 0.90 = 0.045$. Only tokens with at least $4.5\%$ probability survive. Low-probability distractions are aggressively pruned.
- **High Uncertainty ($P_{\text{max}} = 0.20$, $\text{min\_p} = 0.05$)**: Threshold is $0.05 \times 0.20 = 0.010$. A broader range of creative tokens ($> 1\%$) are considered.
- **Result**: You can safely run higher temperatures ($\tau = 0.65 - 0.80$) for rich, textured prose without runaway hallucinations.

---

## 2. Presence Penalty vs. Frequency Penalty

Quantized and abliterated coding models frequently suffer from **lexical looping** or recycling phrases when answering open-ended architectural questions.

| Parameter | Mechanics | Recommended Range | Effect |
| :--- | :--- | :--- | :--- |
| **Presence Penalty** | Constant additive penalty subtracted from the logit if the token has appeared at least once. | `0.15 - 0.30` | Encourages exploring new vocabulary and domain concepts. Highly effective for abliterated models. |
| **Frequency Penalty** | Proportional penalty scaling with the number of times the token has occurred. | `0.00 - 0.10` | Can break programming language syntax (keywords like `def`, `return`, `int` get over-penalized). Keep low or 0 in coding stacks. |
| **Repetition Penalty** | Divisive penalty on repeated tokens. | `1.04 - 1.08` | Mild penalty to discourage token cycles without breaking code structure. |

---

## 3. Temperature Profiles by Task Archetype

| Archetype | Temp ($\tau$) | Min-P | Presence Pen. | Rep. Pen. | Rationale |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Rigorous Logic & Formal CoT** | `0.40 - 0.50` | `0.08` | `0.00 - 0.05` | `1.08` | High deterministic precision for mathematical proofs, state machines, and concurrency bounds. |
| **Deep Architectural Systems** | `0.60 - 0.70` | `0.06` | `0.20` | `1.06` | Balanced exploration with rich systems vocabulary, trade-off comparisons, and concrete memory models. |
| **Divergent Ideation & Synthesis** | `0.75 - 0.85` | `0.05` | `0.30` | `1.08` | Maximum cognitive texture for artistic critique, paradigm shifts, and novel hypothesis generation. |
| **Baseline Greedy (Control)** | `0.10 - 0.20` | `None` | `0.00` | `1.00` | Used strictly as a control benchmark to diagnose degradation. |

---

## 4. Key/Value (KV) Cache Quantization Dynamics

In `systemd/llama-coordinator.service` or CLI args:
- `-ctk q4_0 -ctv q4_0` (4-bit KV Cache): Cuts KV VRAM by $\approx 60\%$. However, 4-bit attention key/value noise disrupts attention weights across long contexts ($> 4k$ tokens), causing subtle hallucinations in spatial/mathematical relationships.
- `-ctk q8_0 -ctv q8_0` (8-bit KV Cache): Near-FP16 attention fidelity with $40\%$ memory savings. Highly recommended on GPUs with $\ge 12\text{GB}$ VRAM (e.g. RX 6750 XT).
- `-ctk f16 -ctv f16` (FP16 KV Cache): Full mathematical precision. Use whenever VRAM permits.

---

## 5. System Prompt Cognitive Anchoring for Abliterated Models

Abliterated models (unaligned / uncensored) require explicit cognitive grounding:
1. **Define the persona's rigor**: *"You are a principal systems architect and theoretical computer scientist. Assertions must be mathematically grounded."*
2. **Forbid boilerplate summaries**: *"Do not provide superficial overviews or hand-waving generalities. Detail specific hardware primitives, memory barriers, or formal invariants."*
3. **Mandate edge-case coverage**: *"Always analyze failure modes, concurrent race hazards, and asymptotic bounds."*
