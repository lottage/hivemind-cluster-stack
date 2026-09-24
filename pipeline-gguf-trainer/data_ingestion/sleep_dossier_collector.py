#!/usr/bin/env python3
"""
Sleep Dossier Collector
Extracts supervised fine-tuning (SFT) pairs and preference (DPO) pairs from
autonomous rumination / deep sleep dossiers (EXP-*.md) generated on the cluster.
"""

import os
import re
import json
import glob
from typing import List, Dict, Any, Optional

try:
    from .format_converter import FormatConverter
    from .frontier_trigger_registry import FrontierTriggerRegistry
except ImportError:
    from format_converter import FormatConverter
    from frontier_trigger_registry import FrontierTriggerRegistry

class SleepDossierCollector:
    def __init__(
        self,
        archive_dir: str = "/opt/cluster-bridge/thinking_archive",
        triggers_path: str = "./data/processed/frontier_triggers.json"
    ):
        self.archive_dir = archive_dir
        self.formatter = FormatConverter()
        self.trigger_registry = FrontierTriggerRegistry(storage_path=triggers_path)

    def parse_dossier(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Parses a single markdown exploration dossier."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            print(f"[WARN] Failed to read {file_path}: {e}")
            return None

        # Extract metadata
        dossier_id_m = re.search(r"\*\*ID\*\*:\s*`([^`]+)`", content)
        domain_m = re.search(r"\*\*Domain\*\*:\s*`([^`]+)`", content)
        target_inv_m = re.search(r"\*\*Target Invariant\*\*:\s*([^\n]+)", content)
        novelty_m = re.search(r"\*\*Novelty Score\*\*:\s*`([^`]+)`", content)
        frontier_m = re.search(r"\*\*Frontier Verified\*\*:\s*`([^`]+)`", content)

        dossier_id = dossier_id_m.group(1) if dossier_id_m else os.path.basename(file_path)
        domain = domain_m.group(1) if domain_m else "general_reasoning"
        target_invariant = target_inv_m.group(1).strip() if target_inv_m else ""
        novelty_score = float(novelty_m.group(1)) if novelty_m else 0.5
        frontier_verified = (frontier_m.group(1).lower() == "true") if frontier_m else False

        # Extract Challenge Prompt (Section 1)
        prompt_m = re.search(r"## 1\. Challenge Prompt\s*```(?:text)?\s*([\s\S]*?)```", content)
        if not prompt_m:
            prompt_m = re.search(r"## 1\. Challenge Prompt\s*([\s\S]*?)(?=\n##\s|\Z)", content)
        
        prompt = prompt_m.group(1).strip() if prompt_m else None
        if not prompt:
            return None

        # Extract Scores (Section 3)
        worker_score = 5
        coord_score = 7
        score_m = re.search(r"\*\*Score \(1-10\)\*\*\s*\|\s*\*\*(\d+)/10\*\*\s*\|\s*\*\*(\d+)/10\*\*", content)
        if score_m:
            worker_score = int(score_m.group(1))
            coord_score = int(score_m.group(2))

        worker_response = ""
        coord_response = ""
        frontier_audit = ""

        # Check for Frontier Audit (Section 5)
        audit_m = re.search(r"## 5\. Tier-1 Frontier Audit[^\n]*\s*([\s\S]*?)(?=$)", content)
        if audit_m:
            frontier_audit = audit_m.group(1).strip()

        # Check for MoE Unified Solution (Section 2)
        moe_m = re.search(r"## 2\. 35B MoE Unified Solution\s*([\s\S]*?)(?=\n## 3|\Z)", content)
        if moe_m:
            coord_response = moe_m.group(1).strip()
            worker_response = "Baseline draft superseded by MoE unified solution."
            coord_score = 10
            worker_score = 6

        # Check for Section 4: Full Model Responses (Standard Dual-GPU)
        sec4_m = re.search(r"## 4\. Full Model Responses\s*([\s\S]*?)(?=## 5\.|\Z)", content)
        if sec4_m and not coord_response:
            sec4_text = sec4_m.group(1).strip()
            parts = re.split(r"### (?:14B Coordinator|Tier 2|Coordinator|Refined Invariant|Synthesis)", sec4_text, flags=re.IGNORECASE)
            if len(parts) >= 2:
                worker_response = parts[0].strip()
                coord_response = parts[1].strip()
            else:
                coord_response = sec4_text

        # Fallback: Check Comparative Evaluation invariant section
        if not coord_response and not worker_response:
            eval_m = re.search(r"## 3\. Comparative Evaluation[\s\S]*?### Core Architectural Invariant Discovered:\s*([\s\S]*?)(?=##|\Z)", content)
            if eval_m:
                coord_response = eval_m.group(1).strip()

        if not coord_response and not worker_response:
            return None

        # Determine chosen vs rejected for DPO and trigger avoidance conditioning
        trigger_info = ""
        if frontier_audit:
            # 1. Register failure triggers from Frontier Audit
            extracted_triggers = self.trigger_registry.register_from_dossier(
                frontier_audit, domain, dossier_id, prompt
            )
            if extracted_triggers:
                trigger_info = self.trigger_registry.format_avoidance_reasoning(extracted_triggers[0])

            # Extract refined invariant
            inv_m = re.search(r"(?:\*\*Refined Architectural Invariant\*\*|\*\*Refined Invariant\*\*|\*\*Operational Invariant\*\*):?\s*([\s\S]*?)(?=##|\Z)", frontier_audit)
            refined_inv = inv_m.group(1).strip() if inv_m else ""
            if refined_inv:
                refined_inv = re.sub(r"^[>\s*#\-]+", "", refined_inv).strip()

            # Check verdict
            verdict_m = re.search(r"(?:###?\s*Verdict|Verdict)[:\s*]*([A-Z_]+)", frontier_audit)
            verdict = verdict_m.group(1) if verdict_m else "UNKNOWN"

            if verdict in ["VERIFIED", "CONCUR", "PASS"]:
                chosen = coord_response or worker_response
                rejected = worker_response if worker_response and worker_response != chosen else "Incomplete baseline response."
            else:
                # Failure verdict (e.g. REVISE_LIMIT_IDENTIFIED)
                # The raw unconstrained model output is REJECTED
                rejected = coord_response if coord_response else (worker_response or "Failed baseline response.")

                # CHOSEN must NEVER be the frontier audit commentary.
                # If MoE solution exists, use it.
                if moe_m:
                    chosen = coord_response
                else:
                    # Synthesize verified response that embodies the refined invariant
                    inv_text = refined_inv if refined_inv else target_invariant
                    cleaned_coord = self.formatter.clean_raw_response(coord_response)
                    # If cleaned_coord has valid sections, retain them while ensuring invariant is satisfied
                    if len(cleaned_coord) > 150:
                        chosen = f"{cleaned_coord}\n\n### Core System Invariant\n> {inv_text}"
                    else:
                        chosen = f"### System Invariant & Solution\n> {inv_text}\n\nAdhere strictly to bounded architecture constraints and closed-form derivations."
        else:
            # Match existing triggers
            matched = self.trigger_registry.match_trigger(prompt, domain)
            if matched:
                trigger_info = self.trigger_registry.format_avoidance_reasoning(matched[0])

            if coord_score >= worker_score and coord_response:
                chosen = coord_response
                rejected = worker_response if worker_response else "Incomplete solution failing invariant."
            else:
                chosen = worker_response or coord_response
                rejected = coord_response if coord_response else "Failed response."

        return {
            "id": dossier_id,
            "domain": domain,
            "target_invariant": target_invariant,
            "novelty_score": novelty_score,
            "frontier_verified": frontier_verified,
            "prompt": prompt,
            "chosen": chosen,
            "rejected": rejected,
            "worker_score": worker_score,
            "coord_score": coord_score,
            "score_delta": abs(coord_score - worker_score),
            "source_file": file_path,
            "trigger_info": trigger_info
        }

    def collect_all(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Collects and parses all dossiers from the archive directory."""
        if not os.path.exists(self.archive_dir):
            print(f"[WARN] Archive directory {self.archive_dir} does not exist.")
            return []

        pattern = os.path.join(self.archive_dir, "EXP-*.md")
        files = sorted(glob.glob(pattern), reverse=True)
        if limit:
            files = files[:limit]

        dossiers = []
        for fpath in files:
            d = self.parse_dossier(fpath)
            if d:
                dossiers.append(d)

        print(f"[INFO] Collected {len(dossiers)} valid training dossiers from {len(files)} files.")
        return dossiers

    def export_datasets(self, dossiers: List[Dict[str, Any]], output_dir: str):
        """Exports SFT and DPO jsonl datasets with token optimization and trigger conditioning."""
        os.makedirs(output_dir, exist_ok=True)
        sft_file = os.path.join(output_dir, "sleep_cycles_sft.jsonl")
        dpo_file = os.path.join(output_dir, "sleep_cycles_dpo.jsonl")

        with open(sft_file, "w", encoding="utf-8") as f_sft, open(dpo_file, "w", encoding="utf-8") as f_dpo:
            for d in dossiers:
                clean_p = self.formatter.clean_prompt(d["prompt"])
                t_info = d.get("trigger_info", "")

                # SFT (ChatML format with <think> reasoning)
                formatted = self.formatter.format_to_chatml(
                    clean_p,
                    d["chosen"],
                    trigger_info=t_info
                )
                sft_item = {
                    "id": d["id"],
                    "domain": d["domain"],
                    "messages": formatted["messages"],
                    "thinking": formatted["thinking"],
                    "answer": formatted["answer"],
                    "trigger_info": t_info
                }
                f_sft.write(json.dumps(sft_item) + "\n")

                # DPO format
                dpo_formatted = self.formatter.format_dpo_pair(
                    clean_p,
                    d["chosen"],
                    d["rejected"],
                    trigger_info=t_info
                )
                dpo_item = {
                    "id": d["id"],
                    "domain": d["domain"],
                    "prompt": dpo_formatted["prompt"],
                    "chosen": dpo_formatted["chosen"],
                    "rejected": dpo_formatted["rejected"],
                    "score_delta": d["score_delta"],
                    "frontier_verified": d["frontier_verified"],
                    "trigger_info": t_info
                }
                f_dpo.write(json.dumps(dpo_item) + "\n")

        print(f"[SUCCESS] Exported SFT -> {sft_file} ({len(dossiers)} items)")
        print(f"[SUCCESS] Exported DPO -> {dpo_file} ({len(dossiers)} pairs)")
        return sft_file, dpo_file

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Collect sleep dossiers for training")
    parser.add_argument("--archive-dir", default="/opt/cluster-bridge/thinking_archive")
    parser.add_argument("--output-dir", default="./data/processed")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    collector = SleepDossierCollector(archive_dir=args.archive_dir)
    dossiers = collector.collect_all(limit=args.limit)
    collector.export_datasets(dossiers, output_dir=args.output_dir)
