#!/usr/bin/env python3
"""
Dataset Builder
Consolidates and validates training datasets from sleep dossiers,
user file uploads (JSONL, TXT, MD, CSV), and external URL extractions.
Produces standardized ChatML SFT and DPO preference datasets.
"""

import os
import glob
import json
import csv
from typing import List, Dict, Any

class DatasetBuilder:
    def __init__(self, output_dir: str = "./data/processed"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def parse_user_upload(self, file_path: str) -> List[Dict[str, Any]]:
        """Parses a user uploaded file into standard prompt/completion dicts."""
        items = []
        ext = os.path.splitext(file_path)[1].lower()
        base = os.path.basename(file_path)

        try:
            if ext == ".jsonl":
                with open(file_path, "r", encoding="utf-8") as f:
                    for idx, line in enumerate(f):
                        line = line.strip()
                        if not line:
                            continue
                        data = json.loads(line)
                        if "prompt" in data and "chosen" in data:
                            items.append(data)
                        elif "messages" in data:
                            # Extract user & assistant messages
                            user_msg = next((m["content"] for m in data["messages"] if m["role"] == "user"), None)
                            asst_msg = next((m["content"] for m in data["messages"] if m["role"] == "assistant"), None)
                            if user_msg and asst_msg:
                                items.append({
                                    "id": f"UPLOAD-{base}-{idx}",
                                    "prompt": user_msg,
                                    "chosen": asst_msg
                                })
            elif ext == ".csv":
                with open(file_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for idx, row in enumerate(reader):
                        prompt = row.get("question") or row.get("prompt") or row.get("instruction")
                        chosen = row.get("answer") or row.get("chosen") or row.get("response")
                        if prompt and chosen:
                            items.append({
                                "id": f"CSV-{base}-{idx}",
                                "prompt": prompt.strip(),
                                "chosen": chosen.strip()
                            })
            elif ext in [".txt", ".md"]:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                # Split on section headings or double newlines
                sections = content.split("## ")
                for idx, sec in enumerate(sections):
                    sec = sec.strip()
                    if len(sec) > 80:
                        lines = sec.split("\n", 1)
                        title = lines[0].strip()
                        body = lines[1].strip() if len(lines) > 1 else sec
                        items.append({
                            "id": f"DOC-{base}-{idx}",
                            "prompt": f"Detail the implementation and architectural principles of {title}.",
                            "chosen": body
                        })
        except Exception as e:
            print(f"[WARN] Error reading user upload {file_path}: {e}")

        return items

    def build_unified_datasets(
        self,
        uploads_dir: str = "./data/uploads",
        archive_items: List[Dict[str, Any]] = None,
        enforce_dual_gate: bool = True,
        auto_quarantine: bool = True
    ):
        """
        Builds unified SFT and DPO training files strictly filtered through
        the Dual-Gate Curation Gatekeeper (Frontier Verified + Human-in-Loop Approved).
        """
        from .curation_gatekeeper import CurationGatekeeper
        gatekeeper = CurationGatekeeper(
            db_path=os.path.join(self.output_dir, "curation_registry.json")
        )

        candidates = []
        if archive_items:
            candidates.extend(archive_items)

        if os.path.exists(uploads_dir):
            for fname in os.listdir(uploads_dir):
                fpath = os.path.join(uploads_dir, fname)
                if os.path.isfile(fpath):
                    candidates.extend(self.parse_user_upload(fpath))

        print(f"[CURATION] Ingesting {len(candidates)} candidate items through Dual-Gate Gatekeeper...")
        for item in candidates:
            gatekeeper.evaluate_and_register(item, auto_quarantine=auto_quarantine)

        stats = gatekeeper.registry["stats"]
        print(f"[CURATION STATS] Total Evaluated: {stats['total_evaluated']} | Frontier Verified (Gate 1): {stats['frontier_verified']} | Human Approved (Gate 2): {stats['human_approved']} | Quarantined: {stats['quarantined']}")

        if enforce_dual_gate:
            admitted = gatekeeper.get_admitted_training_dataset()
            # If no items have human approval yet, check if there are frontier-verified items waiting
            if len(admitted) == 0 and stats["gate1_passed"] > 0:
                print("[WARNING] Zero samples have human operator approval! Strict Dual-Gate requires human sign-off.")
                print(f"[ACTION REQUIRED] Run 'python scripts/run_pipeline.py --review-pending' to approve {stats['pending_human_review']} pending samples.")
        else:
            # Fallback for development dry-run
            admitted = [c for c in candidates if c.get("frontier_verified", True)]

        from .format_converter import FormatConverter
        from .frontier_trigger_registry import FrontierTriggerRegistry
        formatter = FormatConverter()
        trigger_registry = FrontierTriggerRegistry(storage_path=os.path.join(self.output_dir, "frontier_triggers.json"))

        sft_path = os.path.join(self.output_dir, "train_sft.jsonl")
        dpo_path = os.path.join(self.output_dir, "train_dpo.jsonl")

        with open(sft_path, "w", encoding="utf-8") as f_sft:
            for item in admitted:
                t_info = item.get("trigger_info")
                if not t_info:
                    matches = trigger_registry.match_trigger(item["prompt"], item.get("domain"))
                    if matches:
                        t_info = trigger_registry.format_avoidance_reasoning(matches[0])

                formatted = formatter.format_to_chatml(item["prompt"], item["chosen"], trigger_info=t_info)
                entry = {
                    "id": item.get("id", "GEN"),
                    "messages": formatted["messages"],
                    "thinking": formatted["thinking"],
                    "answer": formatted["answer"],
                    "trigger_info": t_info or ""
                }
                f_sft.write(json.dumps(entry) + "\n")

        with open(dpo_path, "w", encoding="utf-8") as f_dpo:
            for item in admitted:
                if item.get("rejected"):
                    t_info = item.get("trigger_info")
                    if not t_info:
                        matches = trigger_registry.match_trigger(item["prompt"], item.get("domain"))
                        if matches:
                            t_info = trigger_registry.format_avoidance_reasoning(matches[0])

                    dpo_formatted = formatter.format_dpo_pair(
                        item["prompt"],
                        item["chosen"],
                        item["rejected"],
                        trigger_info=t_info
                    )
                    entry = {
                        "id": item.get("id", "DPO"),
                        "prompt": dpo_formatted["prompt"],
                        "chosen": dpo_formatted["chosen"],
                        "rejected": dpo_formatted["rejected"],
                        "trigger_info": t_info or ""
                    }
                    f_dpo.write(json.dumps(entry) + "\n")

        print(f"[SUCCESS] Curated SFT dataset created: {sft_path} ({len(admitted)} samples)")
        print(f"[SUCCESS] Curated DPO dataset created: {dpo_path} ({len(admitted)} pairs)")

        # Sync triggers and admitted knowledge directly into in-RAM A-MEM (:6379)
        trigger_count = trigger_registry.sync_to_amem()
        if len(admitted) > 0:
            synced_atoms = gatekeeper.sync_all_to_amem()
            print(f"[A-MEM BRIDGE] Synced {synced_atoms} atomic cards + {trigger_count} trigger guardrails to Valkey RAM for zero-latency runtime recall.")
        elif trigger_count > 0:
            print(f"[A-MEM BRIDGE] Synced {trigger_count} trigger guardrails to Valkey RAM.")

        return sft_path, dpo_path

if __name__ == "__main__":
    builder = DatasetBuilder()
    builder.build_unified_datasets()
