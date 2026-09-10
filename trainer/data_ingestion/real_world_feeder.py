#!/usr/bin/env python3
"""
Real-World Deep Sleep Feeder
Bridges active user conversations, rolling passdowns, and operator corrections
into the cluster's 24/7 autonomous deep sleep queue.

Replaces aimless agent flânerie and ungrounded dreams with real-world user challenges!
"""

import os
import json
import urllib.request
from typing import List, Dict, Any, Optional
from .rolling_passdown_manager import RollingPassdownManager

class RealWorldSleepFeeder:
    def __init__(self, cluster_mcp_url: str = "http://127.0.0.1:8765", queue_file: str = "/opt/cluster-bridge/hypothesis_queue.json"):
        self.mcp_url = cluster_mcp_url
        self.queue_file = queue_file
        self.passdown_mgr = RollingPassdownManager()

    def generate_challenges_from_passdown(self) -> List[Dict[str, Any]]:
        """Generates grounded research challenges from the rolling passdown."""
        return self.passdown_mgr.export_grounded_sleep_challenges()

    def inject_challenges_to_cluster(self, challenges: List[Dict[str, Any]]) -> int:
        """
        Injects real-world challenges directly into the cluster's hypothesis queue
        for the next deep sleep consolidation cycle.
        """
        injected = 0
        for c in challenges:
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "inject_thinking_hypothesis",
                    "arguments": {
                        "hypothesis": c["challenge_prompt"],
                        "domain": c["domain"],
                        "priority": 10 # High priority: real human feedback
                    }
                },
                "id": f"inject-{c['id']}"
            }

            try:
                req = urllib.request.Request(
                    f"{self.mcp_url}/messages",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    injected += 1
            except Exception as e:
                # Direct file queue fallback if MCP endpoint is not reachable locally
                if os.path.exists(os.path.dirname(self.queue_file)):
                    try:
                        q_data = []
                        if os.path.exists(self.queue_file):
                            with open(self.queue_file, "r") as f:
                                q_data = json.load(f)
                        q_data.append({
                            "hypothesis": c["challenge_prompt"],
                            "domain": c["domain"],
                            "priority": 10,
                            "source": "rolling_passdown"
                        })
                        with open(self.queue_file, "w") as f:
                            json.dump(q_data, f, indent=2)
                        injected += 1
                    except Exception as fe:
                        print(f"[WARN] Failed to write fallback queue file: {fe}")
                else:
                    print(f"[WARN] Failed to inject challenge {c['id']}: {e}")

        print(f"[SUCCESS] Injected {injected}/{len(challenges)} real-world challenges into cluster deep sleep queue!")
        return injected

if __name__ == "__main__":
    feeder = RealWorldSleepFeeder()
    challenges = feeder.generate_challenges_from_passdown()
    print(f"[INFO] Found {len(challenges)} challenges from ROLLING_PASSDOWN.md")
    feeder.inject_challenges_to_cluster(challenges)
