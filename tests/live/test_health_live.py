"""
Live checks against the real homelab (needs the LAN). Read-only: nothing here writes anywhere.

    python tests/run_tests.py live
"""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "StoneSage", "backend"))

import health  # noqa: E402


def _load_config():
    path = os.path.join(ROOT, "StoneSage", "backend", "config.json")
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


class TestLiveHealth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = health.check_all(_load_config(), use_cache=False)
        cls.by_name = {s["name"]: s for s in cls.result["services"]}

    def test_all_services_up(self):
        down = [f"{s['name']} ({s['status']})" for s in self.result["services"] if not s["ok"]]
        self.assertEqual(down, [], self.result["summary"])

    def test_coordinator_matches_state_md(self):
        """STATE.md: :8001 runs qwen3-14b with 2 slots of 6144 tokens."""
        d = self.by_name["Coordinator (Courage)"]["detail"]
        self.assertIn("qwen3-14b", d.get("model", ""))
        self.assertEqual(d.get("slots"), 2)
        self.assertEqual(d.get("ctx_per_slot"), 6144)

    def test_vision_loaded(self):
        d = self.by_name["Vision"]["detail"]
        self.assertIn("qwen2.5-vl", d.get("model", ""))

    def test_embedder_context(self):
        """BGE inputs must stay < 950 chars; the engine itself is 512 tokens per slot."""
        self.assertEqual(self.by_name["Embedder"]["detail"].get("ctx_per_slot"), 512)


if __name__ == "__main__":
    unittest.main()
