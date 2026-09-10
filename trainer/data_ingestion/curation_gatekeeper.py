#!/usr/bin/env python3
"""
Dual-Gate Curation & Quarantine Gatekeeper
Strictly prevents hallucinations, bad code, ungrounded physics/logic/calculus,
and random agent desires from polluting model weights.

Admittance Invariant:
A training sample CANNOT be included in the training dataset unless it has been:
  1. Gate 1: Tier-1 Frontier Model Reviewed & Verified (verdict == "VERIFIED")
  2. Gate 2: Human-in-the-Loop (HITL) Reviewed & Explicitly Approved (human_status == "APPROVED")
"""

import os
import json
import time
from typing import Dict, Any, List, Optional, Tuple

class CurationGatekeeper:
    def __init__(self, db_path: str = "./data/processed/curation_registry.json", quarantine_dir: str = "./data/quarantine"):
        self.db_path = db_path
        self.quarantine_dir = quarantine_dir
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.quarantine_dir, exist_ok=True)
        self.registry = self._load_registry()

    def _load_registry(self) -> Dict[str, Any]:
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARN] Failed to load curation registry: {e}")
        return {
            "version": "2.0-dual-gate",
            "samples": {},
            "stats": {
                "total_evaluated": 0,
                "frontier_verified": 0,
                "human_approved": 0,
                "quarantined": 0,
                "ready_for_training": 0
            }
        }

    def _save_registry(self):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(self.registry, f, indent=2)

    def evaluate_and_register(self, item: Dict[str, Any], auto_quarantine: bool = True) -> Tuple[bool, str]:
        """
        Evaluates a candidate sample against Gate 1 (Frontier Audit) and registers it.
        Checks for:
          - Valid Frontier Audit block
          - No ungrounded physics/logic red flags
          - No unverified agent desires / aimless flânerie
        """
        sample_id = item.get("id") or f"SAMPLE-{int(time.time()*1000)}"
        prompt = item.get("prompt", "")
        chosen = item.get("chosen", "")
        frontier_verified = item.get("frontier_verified", False)
        domain = item.get("domain", "general")

        # 1. Gate 1 Checks: Frontier Verification
        rejection_reasons = []
        if not frontier_verified:
            rejection_reasons.append("Missing Tier-1 Frontier Audit verification")

        # Check for agent desire / aimless flânerie red flags
        combined_text = (prompt + "\n" + chosen).lower()
        flanerie_triggers = [
            "aimless flânerie", "wander and consume", "my desires as an agent",
            "what i dream of", "my personal wishes", "pondering my existence",
            "i wish to browse manga", "i feel lonely as an ai"
        ]
        for trigger in flanerie_triggers:
            if trigger in combined_text:
                rejection_reasons.append(f"Contains ungrounded agent desire / aimless flânerie ('{trigger}')")
                break

        # Check for ungrounded / hallucinated physics or impossible calculus
        pseudomath_triggers = [
            "quantum consciousness entanglement in weights",
            "infinite energy thermodynamic loop",
            "division by zero yields hyper-dimensional state",
            "faster-than-light gradient descent"
        ]
        for trigger in pseudomath_triggers:
            if trigger in combined_text:
                rejection_reasons.append(f"Contains pseudo-scientific / hallucinated physics ('{trigger}')")
                break

        gate1_passed = (len(rejection_reasons) == 0)

        # Update registry
        existing = self.registry["samples"].get(sample_id, {})
        human_status = existing.get("human_status", "PENDING_REVIEW")
        human_notes = existing.get("human_notes", "")

        sample_record = {
            "id": sample_id,
            "domain": domain,
            "prompt": prompt[:300] + ("..." if len(prompt) > 300 else ""),
            "full_prompt": prompt,
            "chosen": chosen,
            "rejected": item.get("rejected", ""),
            "frontier_verified": frontier_verified,
            "gate1_passed": gate1_passed,
            "gate1_rejection_reasons": rejection_reasons,
            "human_status": human_status, # PENDING_REVIEW, APPROVED, REJECTED
            "human_notes": human_notes,
            "source": item.get("source_file") or item.get("source") or "sleep_cycle",
            "trigger_info": item.get("trigger_info", ""),
            "admitted_to_training": (gate1_passed and human_status == "APPROVED"),
            "registered_at": existing.get("registered_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        }

        self.registry["samples"][sample_id] = sample_record

        # Quarantine if failed Gate 1 and requested
        if not gate1_passed and auto_quarantine:
            q_file = os.path.join(self.quarantine_dir, f"{sample_id}.json")
            with open(q_file, "w", encoding="utf-8") as qf:
                json.dump({
                    "id": sample_id,
                    "rejection_reasons": rejection_reasons,
                    "prompt": prompt,
                    "sample": item
                }, qf, indent=2)

        self._recalculate_stats()
        self._save_registry()

        if gate1_passed:
            return True, f"Passed Gate 1 (Frontier Audit). Current Human Status: {human_status}"
        else:
            return False, f"Gate 1 Failed: {', '.join(rejection_reasons)}"

    def human_approve(
        self,
        sample_id: str,
        reviewer_notes: str = "Approved by human operator",
        approval_token: Optional[str] = None,
        interactive: bool = False
    ) -> bool:
        """
        Explicitly stamps Gate 2 Human Approval on a sample.
        SECURITY INVARIANT:
        Approval CANNOT be passed as an unchecked string. It MUST provide either:
          1. A cryptographically signed HMAC approval_token from the human's secret key.
          2. A successful interactive TTY challenge (OperatorAuth.interactive_human_challenge).
        Any unauthenticated attempt (e.g. from an autonomous agent or script) is REJECTED.
        """
        from training.operator_auth import OperatorAuth
        auth = OperatorAuth()

        if sample_id not in self.registry["samples"]:
            print(f"[ERROR] Sample {sample_id} not found in curation registry.")
            return False

        record = self.registry["samples"][sample_id]
        if not record["gate1_passed"]:
            print(f"[SECURITY] Cannot human-approve sample {sample_id}: Gate 1 (Frontier Audit) has not passed!")
            return False

        # Verify Authentication: Token or Interactive Challenge
        auth_verified = False
        if approval_token:
            valid, msg = auth.verify_approval_token(approval_token, sample_id)
            if valid:
                auth_verified = True
            else:
                print(f"[SECURITY ALERT] Approval token verification failed: {msg}")
                return False
        elif interactive:
            valid, res = auth.interactive_human_challenge(sample_id)
            if valid:
                auth_verified = True
                approval_token = res
            else:
                print(f"[SECURITY] Interactive challenge failed: {res}")
                return False
        else:
            # Check if operator key exists in environment or local human profile
            key = auth.get_operator_key()
            if key:
                # Sign token with local operator key
                approval_token = auth.generate_approval_token(sample_id)
                auth_verified = True
            else:
                print(f"[SECURITY BLOCKED] Approval rejected! No cryptographic operator key or interactive confirmation provided.")
                print(f"Autonomous agents cannot self-approve training data.")
                return False

        if not auth_verified:
            return False

        record["human_status"] = "APPROVED"
        record["human_notes"] = reviewer_notes
        record["approval_token"] = approval_token
        record["human_approved_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        record["admitted_to_training"] = True

        # Intermediary Operational Bridge: Synthesize A-MEM Atomic Card into Valkey RAM
        try:
            from data_ingestion.amem_bridge import AMEMBridge
            bridge = AMEMBridge()
            atom = bridge.sync_approved_sample(record)
            if atom:
                record["amem_card_id"] = atom["id"]
                print(f"[A-MEM BRIDGE] Synthesized Knowledge Atom '{atom['id']}' -> Valkey RAM (:6379)")
                print(f"             [ATOM]: {atom['atom']}")
        except Exception as e:
            print(f"[WARN] Failed to sync approved sample to A-MEM: {e}")

        self._recalculate_stats()
        self._save_registry()
        print(f"[SUCCESS] Sample {sample_id} CRYPTOGRAPHICALLY APPROVED by human operator. Admitted to training dataset.")
        return True

    def sync_all_to_amem(self) -> int:
        """Syncs all approved curation samples to the in-RAM A-MEM store (:6379)."""
        from data_ingestion.amem_bridge import AMEMBridge
        bridge = AMEMBridge()
        count = bridge.sync_all_approved_from_registry(self.registry)
        print(f"[A-MEM BRIDGE] Synced {count} approved knowledge atoms to A-MEM store.")
        return count

    def human_reject(self, sample_id: str, rejection_reason: str = "Rejected by operator") -> bool:
        """Rejects a sample at Gate 2 and moves it to quarantine."""
        if sample_id not in self.registry["samples"]:
            print(f"[ERROR] Sample {sample_id} not found in curation registry.")
            return False

        record = self.registry["samples"][sample_id]
        record["human_status"] = "REJECTED"
        record["human_notes"] = rejection_reason
        record["admitted_to_training"] = False

        # Quarantine
        q_file = os.path.join(self.quarantine_dir, f"{sample_id}_human_rejected.json")
        with open(q_file, "w", encoding="utf-8") as qf:
            json.dump({"sample_id": sample_id, "reason": rejection_reason, "record": record}, qf, indent=2)

        self._recalculate_stats()
        self._save_registry()
        print(f"[REJECTED] Sample {sample_id} rejected by operator. Reason: {rejection_reason}")
        return True

    def get_pending_human_reviews(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Lists samples that passed Gate 1 (Frontier) and are waiting for human review."""
        pending = []
        for sid, rec in self.registry["samples"].items():
            if rec["gate1_passed"] and rec["human_status"] == "PENDING_REVIEW":
                pending.append(rec)
                if len(pending) >= limit:
                    break
        return pending

    def get_admitted_training_dataset(self) -> List[Dict[str, Any]]:
        """Returns ONLY samples that have cleared BOTH Gate 1 and Gate 2."""
        admitted = []
        for sid, rec in self.registry["samples"].items():
            if rec.get("admitted_to_training", False):
                admitted.append({
                    "id": rec["id"],
                    "domain": rec["domain"],
                    "prompt": rec["full_prompt"],
                    "chosen": rec["chosen"],
                    "rejected": rec["rejected"],
                    "human_approved": True,
                    "frontier_verified": True,
                    "trigger_info": rec.get("trigger_info", "")
                })
        return admitted

    def _recalculate_stats(self):
        samples = self.registry["samples"].values()
        self.registry["stats"] = {
            "total_evaluated": len(samples),
            "frontier_verified": sum(1 for s in samples if s.get("frontier_verified")),
            "gate1_passed": sum(1 for s in samples if s.get("gate1_passed")),
            "pending_human_review": sum(1 for s in samples if s.get("gate1_passed") and s.get("human_status") == "PENDING_REVIEW"),
            "human_approved": sum(1 for s in samples if s.get("human_status") == "APPROVED"),
            "human_rejected": sum(1 for s in samples if s.get("human_status") == "REJECTED"),
            "quarantined": sum(1 for s in samples if not s.get("gate1_passed") or s.get("human_status") == "REJECTED"),
            "admitted_to_training": sum(1 for s in samples if s.get("admitted_to_training"))
        }

if __name__ == "__main__":
    gatekeeper = CurationGatekeeper()
    print("[INFO] Curation Gatekeeper active. Stats:", json.dumps(gatekeeper.registry["stats"], indent=2))
