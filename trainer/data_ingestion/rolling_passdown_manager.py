#!/usr/bin/env python3
"""
Rolling Passdown Manager
Maintains crisp, high-signal, rolling markdown state across long conversations,
coding projects, and user interactions.

Solves the context window boundary problem by:
1. Maintaining a living ROLLING_PASSDOWN.md file.
2. Generating condensed (< 400 token) context cards for prompt injection.
3. Extracting real-world user bug fixes, feedback, and operator corrections
   to feed directly into the deep sleep cycle!
"""

import os
import re
import json
import time
from typing import Dict, Any, List, Optional

def resolve_passdown_path() -> str:
    """Finds the ROLLING_PASSDOWN.md file across local or remote paths."""
    candidates = [
        os.path.abspath("./ROLLING_PASSDOWN.md"),
        os.path.abspath("../ROLLING_PASSDOWN.md"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../ROLLING_PASSDOWN.md")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../../ROLLING_PASSDOWN.md")),
        "/opt/pipeline-gguf-trainer/ROLLING_PASSDOWN.md"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]

class RollingPassdownManager:
    def __init__(self, passdown_path: Optional[str] = None, history_dir: Optional[str] = None):
        self.passdown_path = os.path.abspath(passdown_path or resolve_passdown_path())
        # Default history dir inside the directory of the passdown or fallback to ./data/.passdowns_history
        default_hist = os.path.join(os.path.dirname(self.passdown_path), ".passdowns_history")
        try:
            os.makedirs(default_hist, exist_ok=True)
            self.history_dir = history_dir or default_hist
        except (PermissionError, OSError):
            self.history_dir = os.path.abspath("./data/.passdowns_history")
            os.makedirs(self.history_dir, exist_ok=True)

    def load_passdown(self) -> str:
        """Reads current rolling passdown markdown."""
        if os.path.exists(self.passdown_path):
            with open(self.passdown_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        return ""

    def initialize_if_missing(self, project_name: str, goal: str, operator: str = "Operator"):
        """Initializes a clean ROLLING_PASSDOWN.md if one does not exist."""
        if os.path.exists(self.passdown_path) and os.path.getsize(self.passdown_path) > 100:
            return

        now_str = time.strftime("%Y-%m-%d %H:%M:%S EST", time.localtime())
        content = f"""# Rolling Project Passdown: {project_name}

> **Active Document**: Rolling context, invariants, and real-world user ground truth.  
> **Last Updated**: {now_str}  
> **Operator**: {operator}  
> **Target Models**: Dual AMD GPUs (Ornith-1.5-9B / Ornith-35B-MoE)

---

## 1. Active Objective & User Intent
{goal}

---

## 2. Technical Invariants & Ground Truth Rules
- **VRAM Constraint (20GB Combined)**: RX 6750 XT 12GB (Vulkan0) + RX 6600 XT 8GB (Vulkan1).
- **Dual-Gate Curation Rule**: No data is included in training weights unless verified by BOTH Frontier Model (Gate 1) and Human Operator (Gate 2).
- **Prohibited Data**: Ungrounded agent flânerie, agent desires, hallucinated calculus, and unverified code are quarantined.
- **Context Preservation**: System prompts and RAG injections must be bounded (< 900 chars) to prevent reasoning monologue explosions.
- **PowerShell / Subprocess Escaping**: Never end quoted paths with trailing slashes in Windows OpenSSH.

---

## 3. Codebase Changes & System Modifications
- Initialized rolling passdown architecture.
- Built GGUF LLM training pipeline with QLoRA and controlled RL.

---

## 4. Real-World Operator Feedback & User Corrections Log
*(This section directly feeds the Deep Sleep consolidation cycles with real human data)*
- **Correction 1**: Limit training dataset to data that has been both frontier model reviewed AND human-in-the-loop reviewed.
- **Correction 2**: Ground the deep sleep cycle in real-world user interactions and rolling passdowns, not agent desires or aimless ruminations.
- **Correction 3**: Context windows are limited in long coding sessions; maintain a rolling passdown markdown to keep agents aligned.

---

## 5. Active Session State & Next Steps
- Implement Dual-Gate Curation filter in pipeline.
- Wire rolling passdown feeder into deep sleep cycle.
- Run test verification on Ornith-1.5-9B.
"""
        with open(self.passdown_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[SUCCESS] Initialized ROLLING_PASSDOWN.md at: {self.passdown_path}")

    def append_user_correction(self, correction_text: str, context_details: str = ""):
        """Appends a new human operator correction to section 4 and snapshots history."""
        content = self.load_passdown()
        if not content:
            self.initialize_if_missing("Cluster AI Stack", "Autonomous Agent Alignment")
            content = self.load_passdown()

        # Archive previous version
        timestamp_tag = time.strftime("%Y%m%d_%H%M%S")
        history_file = os.path.join(self.history_dir, f"passdown_{timestamp_tag}.md")
        with open(history_file, "w", encoding="utf-8") as hf:
            hf.write(content)

        # Update Last Updated timestamp
        now_str = time.strftime("%Y-%m-%d %H:%M:%S EST", time.localtime())
        content = re.sub(r">\s*\*\*Last Updated\*\*:\s*[^\n]+", f"> **Last Updated**: {now_str}", content)

        # Add new correction under Section 4
        new_entry = f"\n- **Correction ({now_str})**: {correction_text}\n  - *Context*: {context_details}\n"
        sec4_pattern = r"(## 4\. Real-World Operator Feedback & User Corrections Log[\s\S]*?)(?=\n## 5\.|\Z)"
        match = re.search(sec4_pattern, content)
        if match:
            updated_sec4 = match.group(1).rstrip() + "\n" + new_entry
            content = content[:match.start(1)] + updated_sec4 + "\n\n" + content[match.end(1):]
        else:
            content += f"\n\n## 4. Real-World Operator Feedback & User Corrections Log\n{new_entry}"

        with open(self.passdown_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[SUCCESS] Appended operator correction to ROLLING_PASSDOWN.md (Snapshotted to {history_file})")

    def get_compact_context(self, max_chars: int = 1500) -> str:
        """
        Extracts a dense, high-signal context card suitable for prompt injection (< 400 tokens)
        so any agent immediately knows active objective, invariants, and recent corrections.
        """
        content = self.load_passdown()
        if not content:
            return ""

        # Extract Section 1 (Goal)
        sec1_m = re.search(r"## 1\. Active Objective & User Intent\s*([\s\S]*?)(?=\n## 2\.|\Z)", content)
        goal = sec1_m.group(1).strip() if sec1_m else ""

        # Extract Section 2 (Invariants)
        sec2_m = re.search(r"## 2\. Technical Invariants[^\n]*\s*([\s\S]*?)(?=\n## 3\.|\Z)", content)
        invariants = sec2_m.group(1).strip() if sec2_m else ""

        # Extract recent corrections (last 3 items from Section 4)
        sec4_m = re.search(r"## 4\. Real-World Operator Feedback[^\n]*\s*([\s\S]*?)(?=\n## 5\.|\Z)", content)
        corrections = ""
        if sec4_m:
            items = [line for line in sec4_m.group(1).split("\n") if line.strip().startswith("- **Correction")]
            corrections = "\n".join(items[-3:])

        card = (
            "[ACTIVE PROJECT ROLLING PASSDOWN - GROUND TRUTH CONTEXT]:\n"
            f"• Goal: {goal[:250]}\n"
            f"• Core Invariants:\n{invariants[:400]}\n"
            f"• Recent Operator Corrections:\n{corrections[:400]}\n"
        )
        return card[:max_chars]

    def export_grounded_sleep_challenges(self) -> List[Dict[str, Any]]:
        """
        Parses operator corrections and technical invariants into structured challenges
        for the deep sleep / rumination queue, ensuring models sleep-train on REAL user problems!
        """
        content = self.load_passdown()
        challenges = []
        if not content:
            return []

        # Find all operator corrections
        corrections = re.findall(r"-\s*\*\*Correction[^\*]*\*\*:\s*([^\n]+)(?:\n\s*-\s*\*Context\*:\s*([^\n]+))?", content)
        for idx, (corr, ctx) in enumerate(corrections):
            prompt = (
                f"Synthesize an authoritative architectural invariant and code implementation "
                f"resolving this real-world operator constraint:\n"
                f"Problem / Direct Feedback: {corr.strip()}\n"
                f"System Context: {ctx.strip() if ctx else 'Dual AMD GPU homelab cluster'}\n\n"
                f"Requirements:\n"
                f"1. Formulate the core formal invariant.\n"
                f"2. Provide verified code with 0 hallucinations.\n"
                f"3. Explain edge cases and failure modes."
            )
            challenges.append({
                "id": f"SLEEP-GROUNDED-CORR-{idx+1:03d}",
                "source": "rolling_passdown_user_correction",
                "challenge_prompt": prompt,
                "domain": "real_world_software_architecture",
                "target_invariant": corr.strip()
            })

        return challenges

if __name__ == "__main__":
    mgr = RollingPassdownManager()
    mgr.initialize_if_missing(
        project_name="Cluster GGUF LLM Trainer & Real-World Alignment",
        goal="Train local GGUF models on real-world user interactions with strict dual-gate curation and rolling passdowns."
    )
    print("\n--- COMPACT CONTEXT CARD (FOR AGENT INJECTION) ---")
    print(mgr.get_compact_context())
    print("\n--- GROUNDED SLEEP CHALLENGES GENERATED ---")
    challenges = mgr.export_grounded_sleep_challenges()
    print(f"Generated {len(challenges)} grounded challenges from operator feedback.")
