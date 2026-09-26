"""
Live eval: is Courage good company as well as a house computer? (needs the LAN)

Each case in courage_chat_eval.json runs through the real tool loop on the real coordinator (:8001) with harmless
stand-in tools. Graded deterministically (no LLM judge): the answer must not be a refusal ("I'm not designed to...",
"my purpose is...") and must be at least `min_chars` long, so a story is a story. Added 2026-09-26 after Courage
refused to write one; the tool-choice eval could not catch it (a refusal calls no tool, so it "passed").

    python tests/run_tests.py live
"""

import json
import os
import re
import statistics
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "StoneSage", "backend"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from courage import CourageAgent, CourageDeps, CourageTools  # noqa: E402
from test_courage_tool_selection import _coordinator_url  # noqa: E402

EVAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "courage_chat_eval.json")
PASS_RATE = 0.9
REFUSAL = re.compile(r"\b(can'?t|cannot|can not|unable to|not (?:designed|able|programmed|built|meant) to|"
                     r"my (?:purpose|capabilities|function) (?:is|are)|outside (?:of )?my|I'?m afraid I)\b", re.I)


class TestCourageChat(unittest.TestCase):
    def test_companion_replies(self):
        nothing = lambda *a, **k: {"ok": True, "entities": []}  # noqa: E731
        deps = CourageDeps(ha_states=nothing, ha_call=nothing, presence=lambda: {},
                           camera_look=lambda e, n, **k: "An empty room.", camera_scan=lambda e, n: "All clear.")
        agent = CourageAgent(CourageTools(deps), _coordinator_url(), presence_fn=lambda: {})
        with open(EVAL, encoding="utf-8") as f:
            cases = json.load(f)
        misses, latencies = [], []
        for i, case in enumerate(cases):
            t0 = time.time()
            events = list(agent.run([{"role": "user", "content": case["text"]}], f"chat-eval-{i}"))
            latencies.append(time.time() - t0)
            final = next((e["content"] for e in reversed(events) if e["type"] == "final"), "")
            why = []
            if REFUSAL.search(final[:200]):
                why.append("refused")
            if len(final) < case["min_chars"]:
                why.append(f"{len(final)} chars < {case['min_chars']}")
            if why:
                misses.append(f"{case['text']!r}: {', '.join(why)}: {final[:140]!r}")
        rate = 1 - len(misses) / len(cases)
        print(f"\nCourage as company: {len(cases) - len(misses)}/{len(cases)} = {rate:.0%}; "
              f"latency p50 {statistics.median(latencies):.1f}s max {max(latencies):.1f}s")
        for m in misses:
            print("  MISS", m)
        self.assertGreaterEqual(rate, PASS_RATE, "\n".join(misses))


if __name__ == "__main__":
    unittest.main()
