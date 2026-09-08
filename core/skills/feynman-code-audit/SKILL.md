---
name: feynman-code-audit
description: Rigorous paper-vs-codebase audit and experiment replication methodology from the companion-inc/feynman project.
---

# Feynman Paper-vs-Codebase Audit

## Audit Checklist
1. **Claims vs Implementation**: Compare reported benchmark claims in papers directly against the public GitHub code.
2. **Evaluation Mismatches**: Detect altered test sets, missing baseline ablations, or data leakage.
3. **Reproducibility Assessment**: Inspect environment dependencies, fixed random seeds, and GPU VRAM requirements.
4. **Adversarial Scrutiny**: Refuse vague praise; tie every finding to file paths and line numbers.
