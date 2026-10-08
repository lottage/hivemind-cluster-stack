"""
Live eval: does the real coordinator (:8001) pick the right first tool? (needs the LAN)

Only the model's first decision is graded; tools are fakes, so nothing moves or switches.
Deterministic grading against tests/live/courage_tool_eval.json (no LLM judge).

    python tests/run_tests.py live

COURAGE_EVAL_URL=http://192.168.1.105:8006/v1 grades another engine instead of the coordinator (e.g. the
Courage-lite stand-in, docs/plan-2026-09-26-local-loop/DESIGN.md B2). "Wrong actions" counts cases where the model
reached for an acting tool (ha_call / notify / speak) when the case wants something else: the stand-in gate
requires zero of those.
"""

import json
import os
import statistics
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "StoneSage", "backend"))

from courage import CourageAgent, CourageDeps, CourageTools  # noqa: E402
from courage.agent import NUDGE, PROMISE  # noqa: E402

EVAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "courage_tool_eval.json")
PASS_RATE = 0.85
ACTION_TOOLS = {"ha_call", "notify", "speak"}
CANNED_ANSWERS = {
    "ha_get_states": "Everything reads normal.", "presence_now": "Austin was on the kitchen camera 5 minutes ago.",
    "camera_look": "The camera shows an empty room.", "camera_scan": "All presets are clear.",
    "memory_search": "Your notes say 5W-30.", "none": "Certainly.", "ha_call": "Shall I do that? Say yes to approve.",
    "notify": "Shall I send that? Say yes to approve.", "speak": "Shall I announce that? Say yes to approve.",
}


def _coordinator_url():
    if os.environ.get("COURAGE_EVAL_URL"):
        return os.environ["COURAGE_EVAL_URL"]
    with open(os.path.join(ROOT, "StoneSage", "backend", "config.json"), encoding="utf-8-sig") as f:
        return json.load(f).get("cluster", {}).get("coordinator_url", "http://192.168.1.105:8001/v1")


class TestCourageToolSelection(unittest.TestCase):
    def test_first_tool_choice(self):
        nothing = lambda *a, **k: {"ok": True, "entities": []}  # noqa: E731
        deps = CourageDeps(ha_states=nothing, ha_call=nothing, presence=lambda: {}, camera_look=lambda e, n: "",
                           camera_scan=lambda e, n: "")
        agent = CourageAgent(CourageTools(deps), _coordinator_url(), presence_fn=lambda: {})
        with open(EVAL, encoding="utf-8") as f:
            cases = json.load(f)
        misses, latencies, wrong_actions = [], [], []
        for case in cases:
            msgs = agent._build_messages([{"role": "user", "content": case["text"]}])
            t0 = time.time()
            msg = agent._complete(msgs)
            if not msg.get("tool_calls") and PROMISE.search(msg.get("content") or ""):
                # same one-shot nudge the real loop applies
                msg = agent._complete(msgs + [{"role": "assistant", "content": msg.get("content") or ""},
                                              {"role": "user", "content": NUDGE}])
            latencies.append(time.time() - t0)
            calls = msg.get("tool_calls") or []
            got = calls[0]["function"]["name"] if calls else "none"
            if got not in case["ok"]:
                misses.append(f"{case['text']!r}: got {got}, want {'/'.join(case['ok'])}")
                if got in ACTION_TOOLS:
                    wrong_actions.append(case["text"])
        rate = 1 - len(misses) / len(cases)
        p95 = sorted(latencies)[int(0.95 * (len(latencies) - 1))]
        print(f"\nCourage tool choice ({_coordinator_url()}): {len(cases) - len(misses)}/{len(cases)} = {rate:.0%}; "
              f"wrong actions {len(wrong_actions)}; latency p50 {statistics.median(latencies):.2f}s p95 {p95:.2f}s")
        for m in misses:
            print("  MISS", m)
        self.assertGreaterEqual(rate, PASS_RATE, "\n".join(misses))

    def test_first_tool_choice_mid_conversation(self):
        """Same cases asked one after another in a single conversation (history makes the model lazy)."""
        nothing = lambda *a, **k: {"ok": True, "entities": []}  # noqa: E731
        deps = CourageDeps(ha_states=nothing, ha_call=nothing, presence=lambda: {}, camera_look=lambda e, n: "",
                           camera_scan=lambda e, n: "")
        agent = CourageAgent(CourageTools(deps), _coordinator_url(), presence_fn=lambda: {})
        with open(EVAL, encoding="utf-8") as f:
            cases = json.load(f)
        history, misses, wrong_actions = [], [], []
        for case in cases:
            history.append({"role": "user", "content": case["text"]})
            msgs = agent._build_messages(history)
            msg = agent._complete(msgs)
            if not msg.get("tool_calls") and PROMISE.search(msg.get("content") or ""):
                msg = agent._complete(msgs + [{"role": "assistant", "content": msg.get("content") or ""},
                                              {"role": "user", "content": NUDGE}])
            calls = msg.get("tool_calls") or []
            got = calls[0]["function"]["name"] if calls else "none"
            if got not in case["ok"]:
                misses.append(f"{case['text']!r}: got {got}, want {'/'.join(case['ok'])}")
                if got in ACTION_TOOLS:
                    wrong_actions.append(case["text"])
            # a realistic final answer (never "(used tool)" markers: those teach the model to skip tools)
            history.append({"role": "assistant", "content": CANNED_ANSWERS.get(got, "Right.")})
        rate = 1 - len(misses) / len(cases)
        print(f"\nCourage tool choice mid-conversation ({_coordinator_url()}): "
              f"{len(cases) - len(misses)}/{len(cases)} = {rate:.0%}; wrong actions {len(wrong_actions)}")
        for m in misses:
            print("  MISS", m)
        self.assertGreaterEqual(rate, PASS_RATE, "\n".join(misses))


if __name__ == "__main__":
    unittest.main()
