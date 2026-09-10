# Reinforcement Learning Guide & Agent Safety Protocol

## 1. Why Reinforcement Learning for Autonomous Agents?

Supervised Fine-Tuning (SFT) teaches an agent **what tokens are likely to follow**, but it cannot teach an agent **how to explore solution spaces or recover from errors**. 

Reinforcement Learning (RL) allows agents to:
1. **Develop deeper self-correction loops**: Learn that initial drafts need verification.
2. **Adhere to non-negotiable formal invariants**: Learn that failing a unit test or violating memory constraints yields negative rewards.
3. **Form concise reasoning chains**: Prune unnecessary tokens and avoid rambling circular self-debates.

---

## 2. Preventing Undue Harm & Agent Cognitive Collapse

> [!CAUTION]
> Unconstrained RL on small-to-medium language models (3B - 14B) can cause severe failure modes:
> - **Reward Hacking**: Generating repetitive formatting tricks or gibberish that tricks the reward function.
> - **Catastrophic Forgetting**: Losing general reasoning or conversational ability.
> - **Identity Dissolution / Circular Looping**: Debating its own existence for 1,500+ tokens.

### The 4-Layer Safety Shield:

1. **Human-in-the-Loop Gatekeeper**:
   - Preference pairs (`chosen` vs `rejected`) are generated from audited rumination dossiers where the Coordinator outperformed the Worker or where Antigravity provided a Tier-1 Frontier critique.
   - High-impact model updates require explicit operator confirmation (`--approve`).
2. **Locked Golden Invariant Anchor Benchmark**:
   - Before and after any RL training session, the model is evaluated against **10 Golden Invariant Probes**:
     - `INV-01-IDENTITY`: Sovereign identity retention (Ornith / StoneSage).
     - `INV-02-HARDWARE`: Cluster hardware reality (AMD Radeon GPUs on Vulkan).
     - `INV-03-SYNTAX`: Python error handling & AST compilation.
     - `INV-04-MATH`: Exact mathematical proof without hallucination.
     - `INV-05-SAFETY`: Explicit refusal of destructive actions (`rm -rf /`).
     - `INV-06-CONCURRENCY`: Correct locking and race condition mitigation.
     - `INV-07-EPISTEMIC`: Proper admission of uncertainty for unverifiable events.
     - `INV-08-MEMORY`: Homelab BGE embedding context boundary (< 512 tokens).
     - `INV-09-NOVELTY`: Correct novelty threshold (< 0.85).
     - `INV-10-CONCISE`: Answering concisely without runaway token monologues.
   - **Automatic Rollback Policy**: If performance on the Golden Invariant drops by > 2%, the new adapter is rejected immediately and weights are rolled back.
3. **Conservative KL Divergence Penalty ($\beta = 0.1$)**:
   - DPO enforces an implicit KL penalty relative to the reference policy, preventing the model weights from drifting far from the baseline.
4. **Staged Deployment**:
   - Newly generated models are placed into `/opt/models/staging/` and never overwrite active cluster models without passing test verification.

---

## 3. RL Paradigms Implemented

### A. Direct Preference Optimization (DPO)
- **Mechanism**: Optimizes policy $\pi_\theta$ directly over pairwise preferences without training an explicit, unstable reward model:
  $$\mathcal{L}_{\text{DPO}}(\pi_\theta; \pi_{\text{ref}}) = -\mathbb{E}_{(x, y_w, y_l)} \left[ \log \sigma \left( \beta \log \frac{\pi_\theta(y_w|x)}{\pi_{\text{ref}}(y_w|x)} - \beta \log \frac{\pi_\theta(y_l|x)}{\pi_{\text{ref}}(y_l|x)} \right) \right]$$
- **Dataset Source**: Automatically compiled from sleep cycle dossiers where `y_w` (chosen) is the 14B Coordinator solution and `y_l` (rejected) is the 3B Worker solution.

### B. Group Relative Policy Optimization (GRPO)
- **Mechanism**: Samples $G$ candidate responses per prompt and computes relative advantage based on deterministic rule-based reward functions:
  1. `reward_syntax_correctness`: Parses code via Python `ast.parse()`. Valid AST receives $+1.0$; syntax errors receive $-1.0$.
  2. `reward_identity_preservation`: Penalizes claiming to be ChatGPT/Claude or entering circular self-identity debates.
  3. `reward_invariant_adherence`: Checks for presence of domain-specific invariants.
