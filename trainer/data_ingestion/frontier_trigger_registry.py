#!/usr/bin/env python3
"""
Frontier Failure Trigger Registry
Automatically extracts, indexes, and deploys failure triggers identified by
Tier-1 Frontier Audits (REVISE_LIMIT_IDENTIFIED, LIMIT_EXCEEDED, etc.).

Solves:
1. Avoids model failure triggers: Captures exact conditions that cause autoregressive
   loops, truncation cutoffs, or reasoning collapse.
2. SFT/DPO Conditioning: Teaches the model inside <think> to recognize the trigger and
   apply the verified avoidance invariant.
3. In-RAM A-MEM Sync: Pushes sub-35 token avoidance cards to Valkey (:6379) for zero-latency
   runtime pre-inference guardrails.
"""

import os
import re
import json
import time
import hashlib
from typing import Dict, Any, List, Optional, Tuple

class FrontierTriggerRegistry:
    def __init__(self, storage_path: str = "./data/processed/frontier_triggers.json"):
        self.storage_path = storage_path
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        self.triggers: Dict[str, Dict[str, Any]] = self._load_triggers()

    def _load_triggers(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARN] Failed to load trigger registry from {self.storage_path}: {e}")
        return {}

    def _save_triggers(self):
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self.triggers, f, indent=2)

    def extract_triggers_from_audit(
        self,
        audit_text: str,
        domain: str = "general",
        dossier_id: str = "",
        prompt: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Parses a Tier-1 Frontier Audit block and extracts structured failure triggers.
        """
        if not audit_text or len(audit_text) < 40:
            return []

        # Check for non-passing or limit-identifying verdicts
        verdict_m = re.search(r"(?:###?\s*Verdict|Verdict)[:\s*]*([A-Z_]+)", audit_text)
        verdict = verdict_m.group(1) if verdict_m else "UNKNOWN"

        # Check for assessment and refined invariant
        assess_m = re.search(r"(?:\*\*Frontier Architectural Assessment\*\*|\*\*Assessment\*\*):?\s*([\s\S]*?)(?=\*\*Refined|\*\*Operational|##|\Z)", audit_text)
        assessment = assess_m.group(1).strip() if assess_m else audit_text

        inv_m = re.search(r"(?:\*\*Refined Architectural Invariant\*\*|\*\*Refined Invariant\*\*|\*\*Operational Invariant\*\*):?\s*([\s\S]*?)(?=##|\Z)", audit_text)
        refined_inv = inv_m.group(1).strip() if inv_m else ""

        # Extract trigger sentences
        triggers_found = []

        # Known failure signatures and avoidance templates
        pattern_rules = [
            {
                "pattern": r"(?:degeneration loop|repetition loop|repeating tokens|re-listing)",
                "failure_mode": "autoregressive_degeneration_loop",
                "slug": "degen_loop",
                "default_condition": "multi-part parameter matrix or open-ended combinatorial listing without strict schema",
                "default_avoidance": "Enforce strict schema bounding, concise invariant tables, and explicit per-section token limits."
            },
            {
                "pattern": r"(?:horizon limits?|abrupt context cutoff|truncated abruptly|context cutoff|truncat)",
                "failure_mode": "generation_horizon_cutoff",
                "slug": "horizon_cutoff",
                "default_condition": "multi-part technical proof exceeding single-turn horizon budget",
                "default_avoidance": "Structure derivation into compact closed-form equations; avoid verbose prose commentary before core theorem."
            },
            {
                "pattern": r"(?:markdown commentary rather than strict json|failed its operational invariant|strict json)",
                "failure_mode": "schema_format_violation",
                "slug": "schema_violation",
                "default_condition": "prompt requesting formal data or evaluation under operational invariant",
                "default_avoidance": "Output pure JSON payload adhering strictly to schema with zero conversational preamble or markdown wrapping."
            },
            {
                "pattern": r"(?:syntactic leniency bias|false positive evaluation|lenient scoring)",
                "failure_mode": "evaluator_leniency_bias",
                "slug": "leniency_bias",
                "default_condition": "sub-14B model evaluating complex code or mathematical proof",
                "default_avoidance": "Execute deterministic test execution or apply Tier-1 Frontier arbitration for mathematical invariants."
            },
            {
                "pattern": r"(?:kv cache underestimation|vram overflow|out of memory|headroom limit)",
                "failure_mode": "vram_headroom_miscalculation",
                "slug": "vram_miscalculation",
                "default_condition": "hardware sizing calculation with GQA/MQA kv-head architecture",
                "default_avoidance": "Apply exact formula Memory = 2 * L * H_kv * d_h * N_ctx * bytes; strictly distinguish KV heads from query heads."
            }
        ]

        # Scan assessment and refined invariant for failure signatures
        full_text = f"{assessment}\n{refined_inv}"
        clean_domain = domain.strip().lower().replace(" ", "_").replace("-", "_")

        for rule in pattern_rules:
            if re.search(rule["pattern"], full_text, re.IGNORECASE):
                avoidance = rule["default_avoidance"]
                condition = rule["default_condition"]

                if refined_inv:
                    cleaned_inv = re.sub(r"^[>\s*#\-]+", "", refined_inv).strip()
                    sentences = re.split(r"(?<=[.!?])\s+", cleaned_inv)
                    for s in sentences:
                        if re.search(rule["pattern"], s, re.IGNORECASE):
                            avoidance = s.strip()
                            break

                trigger_id = f"TRIG-{clean_domain.upper()}-{rule['slug'].upper()}"
                prompt_keywords = self._extract_keywords(f"{prompt} {condition}")

                trigger_obj = {
                    "trigger_id": trigger_id,
                    "domain": clean_domain,
                    "verdict": verdict,
                    "failure_mode": rule["failure_mode"],
                    "trigger_condition": condition,
                    "avoidance_invariant": avoidance,
                    "assessment_snippet": assessment[:300].strip(),
                    "keywords": prompt_keywords,
                    "source_dossier": dossier_id,
                    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
                triggers_found.append(trigger_obj)

        return triggers_found

    def _extract_keywords(self, text: str) -> List[str]:
        stopwords = {
            "a", "an", "the", "and", "or", "to", "in", "on", "at", "for", "with",
            "is", "are", "was", "were", "this", "that", "it", "from", "by", "of"
        }
        tokens = re.findall(r"\b[a-zA-Z0-9_\-\.]{3,}\b", text.lower())
        tags = []
        for t in tokens:
            if t not in stopwords and t not in tags:
                tags.append(t)
            if len(tags) >= 15:
                break
        return tags

    def register_trigger(self, trigger: Dict[str, Any]) -> bool:
        """Registers a trigger into the persistent store."""
        tid = trigger.get("trigger_id")
        if not tid:
            return False
        self.triggers[tid] = trigger
        self._save_triggers()
        return True

    def register_from_dossier(
        self,
        audit_text: str,
        domain: str,
        dossier_id: str,
        prompt: str = ""
    ) -> List[Dict[str, Any]]:
        """Extracts and registers all triggers from a dossier audit."""
        extracted = self.extract_triggers_from_audit(audit_text, domain, dossier_id, prompt)
        for t in extracted:
            self.register_trigger(t)
        return extracted

    def match_trigger(self, prompt: str, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Matches an incoming prompt against registered triggers.
        Returns matching triggers ranked by keyword overlap.
        """
        if not prompt or not self.triggers:
            return []

        prompt_tokens = set(re.findall(r"\b[a-zA-Z0-9_\-\.]{3,}\b", prompt.lower()))
        matches = []

        for tid, t in self.triggers.items():
            if domain and t.get("domain") and t["domain"] != domain:
                continue
            
            trigger_kws = set(t.get("keywords", []))
            overlap = len(prompt_tokens & trigger_kws)
            
            cond = t.get("trigger_condition", "").lower()
            cond_words = [w for w in re.findall(r"\b\w{4,}\b", cond) if w in prompt.lower()]
            
            score = overlap + (len(cond_words) * 2)
            if score >= 3:
                matches.append((score, t))

        matches.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in matches]

    def format_avoidance_reasoning(self, trigger: Dict[str, Any]) -> str:
        """Formats the trigger detection and avoidance trace for inside <think>."""
        cond = trigger.get("trigger_condition", "known failure condition")
        avoid = trigger.get("avoidance_invariant", "Apply formal structural invariant.")
        return (
            f"[TRIGGER CHECK]: Input matches failure trigger ({cond}).\n"
            f"[TRIGGER AVOIDANCE]: {avoid}"
        )

    def sync_to_amem(self, amem_bridge=None) -> int:
        """
        Syncs all registered triggers to Valkey RAM (:6379) as sub-35 token atomic cards.
        """
        if amem_bridge is None:
            try:
                from .amem_bridge import AMEMBridge
                amem_bridge = AMEMBridge()
            except Exception as e:
                print(f"[WARN] Could not initialize AMEMBridge: {e}")
                return 0

        synced = 0
        for tid, t in self.triggers.items():
            atom_text = f"AVOID {t['failure_mode'].upper()}: {t['avoidance_invariant']}"
            if len(atom_text) > 220:
                atom_text = atom_text[:217] + "..."

            card = {
                "id": f"trigger.{t['domain']}.{tid.lower().replace('-', '_')}",
                "sample_id": t.get("source_dossier") or tid,
                "atom": atom_text,
                "keywords": t.get("keywords", []) + ["trigger", "avoidance", t["failure_mode"]],
                "category": "trigger_avoidance",
                "confidence": 1.0,
                "source": f"frontier_trigger:{tid}",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
            if amem_bridge.store_atom(card):
                synced += 1

        print(f"[SUCCESS] Synced {synced} Frontier Trigger Avoidance cards to Valkey RAM.")
        return synced

if __name__ == "__main__":
    registry = FrontierTriggerRegistry()
    print(f"Initialized FrontierTriggerRegistry. Active triggers: {len(registry.triggers)}")
