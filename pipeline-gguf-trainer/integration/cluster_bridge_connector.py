#!/usr/bin/env python3
"""
Cluster Bridge Connector & API Hooks
Provides programmatic Python bindings and REST API hooks for StoneSage Cockpit (:8080)
and the Cluster MCP Bridge (:8765).
"""

import os
import sys
import json
import yaml
import shutil
import subprocess
from typing import Dict, Any, Optional

class ClusterBridgeConnector:
    def __init__(self, config_path: str = "./config/training_config.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        self.state_file = "./output/training_status.json"

    def update_status(self, status: str, progress: float, details: Dict[str, Any]):
        """Persists current training status for cockpit polling."""
        os.makedirs("./output", exist_ok=True)
        payload = {
            "status": status,
            "progress_percent": round(progress * 100, 1),
            "details": details
        }
        with open(self.state_file, "w") as f:
            json.dump(payload, f, indent=2)

    def get_status(self) -> Dict[str, Any]:
        """Reads current training status."""
        if os.path.exists(self.state_file):
            with open(self.state_file, "r") as f:
                return json.load(f)
        return {"status": "idle", "progress_percent": 0.0, "details": {}}

    def trigger_sleep_ingest(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Pulls latest rumination dossiers from cluster archive."""
        from data_ingestion.sleep_dossier_collector import SleepDossierCollector
        archive_dir = self.config["data_ingestion"].get("thinking_archive_dir", "/opt/cluster-bridge/thinking_archive")
        collector = SleepDossierCollector(archive_dir=archive_dir)
        dossiers = collector.collect_all(limit=limit)
        sft_path, dpo_path = collector.export_datasets(dossiers, output_dir=self.config["data_ingestion"].get("dataset_output_dir", "./data/processed"))
        return {
            "dossiers_count": len(dossiers),
            "sft_dataset": sft_path,
            "dpo_dataset": dpo_path
        }

    def trigger_url_ingest(self, url: str) -> Dict[str, Any]:
        """Ingests external URL, parses markdown chunks, synthesizes QA."""
        from data_ingestion.external_url_extractor import ExternalUrlExtractor
        extractor = ExternalUrlExtractor()
        items = extractor.process_url(url)
        out_file = os.path.join(self.config["data_ingestion"].get("dataset_output_dir", "./data/processed"), "url_qa.jsonl")
        with open(out_file, "w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item) + "\n")
        return {
            "url": url,
            "items_count": len(items),
            "output_file": out_file
        }

    def promote_to_cluster(self, staged_gguf: str, role: str = "worker") -> Dict[str, Any]:
        """
        Safely deploys a tested GGUF model into /opt/models/ with backup
        and restarts systemd service.
        Roles: 'worker' (:8002) or 'coordinator' (:8001).
        """
        prod_dir = self.config["export"].get("production_dir", "/opt/models")
        os.makedirs(prod_dir, exist_ok=True)

        if role == "coordinator":
            target_name = "ornith-1.5-9b-coordinator-q8_0.gguf"
            service_name = "llama-coordinator"
        else:
            target_name = "ornith-1.5-9b-worker-q4_k_m.gguf"
            service_name = "llama-worker"

        target_path = os.path.join(prod_dir, target_name)
        backup_path = os.path.join(prod_dir, f"{target_name}.bak")

        # 1. Backup existing model
        if os.path.exists(target_path):
            print(f"[INFO] Backing up existing {target_path} -> {backup_path}")
            shutil.copy2(target_path, backup_path)

        # 2. Copy new model
        print(f"[INFO] Deploying staged model {staged_gguf} -> {target_path}")
        shutil.copy2(staged_gguf, target_path)

        # 3. Restart service if running locally on Linux
        if sys.platform != "win32":
            print(f"[INFO] Restarting systemd service: {service_name}")
            subprocess.run(["sudo", "systemctl", "restart", service_name], check=False)

        return {
            "status": "promoted",
            "deployed_path": target_path,
            "backup_path": backup_path,
            "service": service_name
        }

if __name__ == "__main__":
    conn = ClusterBridgeConnector()
    print("[INFO] ClusterBridgeConnector active. Status:", conn.get_status())
