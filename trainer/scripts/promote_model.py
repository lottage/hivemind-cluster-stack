#!/usr/bin/env python3
"""
Model Promotion & Deployment CLI
Safely deploys tested GGUF models to /opt/models/ with backup and service restart.
Requires explicit user confirmation or --approve flag.
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from integration.cluster_bridge_connector import ClusterBridgeConnector

def main():
    parser = argparse.ArgumentParser(description="Promote tested GGUF model to cluster production")
    parser.add_argument("--model-file", required=True, help="Path to staged .gguf file")
    parser.add_argument("--role", choices=["worker", "coordinator"], required=True, help="Target model role")
    parser.add_argument("--approve", action="store_true", help="Explicit user approval confirmation")
    args = parser.parse_args()

    if not args.approve:
        print("[ERROR] Promotion blocked by safety guardrails! You must pass --approve to confirm deployment.")
        sys.exit(1)

    connector = ClusterBridgeConnector()
    print(f"[INFO] Promoting {args.model_file} to production as {args.role.upper()}...")
    result = connector.promote_to_cluster(args.model_file, role=args.role)
    print(f"[SUCCESS] Deployed to: {result['deployed_path']}")
    print(f"[SUCCESS] Backup saved to: {result['backup_path']}")
    print(f"[SUCCESS] Target service: {result['service']}")

if __name__ == "__main__":
    main()
