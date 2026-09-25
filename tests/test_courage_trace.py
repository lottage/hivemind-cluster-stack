"""Offline tests for Courage's per-turn trace: what gets recorded for each way a turn can go, the escalation
triggers (recorded only), a client leaving mid-turn, rotation, and the summary counts."""

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "StoneSage", "backend"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from courage.trace import TraceLog  # noqa: E402
from test_courage_agent import FakeHA, ScriptedLLM, make_agent, reply, run, tool_call  # noqa: E402


def traced(llm, **kw):
    agent, ha = make_agent(llm, **kw)
    agent.trace_log = TraceLog(os.path.join(tempfile.mkdtemp(), "trace.jsonl"))
    return agent, ha


def last(agent):
    return agent.trace_log.recent(1)[0]


class TestTurnRecords(unittest.TestCase):
    def test_tool_turn_records_llm_calls_tool_and_answer(self):
        llm = ScriptedLLM(tool_call("presence_now", {}), reply("Luna was in the kitchen 12 minutes ago."))
        agent, _ = traced(llm)
        run(agent, "Is Luna inside?")
        rec = last(agent)
        self.assertEqual((rec["path"], rec["outcome"], rec["user"]), ("loop", "answered", "Is Luna inside?"))
        self.assertEqual(rec["llm"]["calls"], 2)
        self.assertEqual([s.get("tool") for s in rec["steps"] if "tool" in s], ["presence_now"])
        self.assertTrue(rec["steps"][1]["ok"])
        self.assertIn("12 minutes", rec["final"])
        self.assertEqual(rec["triggers"], [])

    def test_approval_then_yes(self):
        llm = ScriptedLLM(tool_call("ha_call", {"domain": "light", "service": "turn_off", "entity_id": "light.kitchen"}))
        agent, _ = traced(llm)
        run(agent, "it's far too bright in the kitchen")
        self.assertEqual(last(agent)["outcome"], "asked_approval")
        agent.post = ScriptedLLM(reply("Done."))
        run(agent, "yes")
        rec = last(agent)
        self.assertEqual((rec["path"], rec["outcome"]), ("approval_yes", "answered"))
        self.assertEqual(rec["steps"][0]["tool"], "ha_call")

    def test_reflex_turn_has_no_llm_call(self):
        agent, ha = traced(ScriptedLLM())
        run(agent, "turn off the kitchen light")
        rec = last(agent)
        self.assertEqual((rec["path"], rec["llm"]["calls"]), ("reflex", 0))
        self.assertEqual(ha.calls, [("light", "turn_off", {"entity_id": "light.kitchen"})])


class TestTriggers(unittest.TestCase):
    def test_step_cap_and_repeated_call(self):
        llm = ScriptedLLM(*[tool_call("presence_now", {}, cid=f"c{i}") for i in range(5)])
        agent, _ = traced(llm)
        run(agent, "where is everyone?")
        rec = last(agent)
        self.assertEqual(rec["outcome"], "step_cap")
        self.assertIn("repeated_call", rec["triggers"])
        self.assertIn("step_cap", rec["triggers"])

    def test_nudge_and_llm_error(self):
        llm = ScriptedLLM(reply("Let me check the cameras for you."), reply("Luna is on the couch."))
        agent, _ = traced(llm)
        run(agent, "where's Luna?")
        self.assertIn("nudged", last(agent)["triggers"])

        def down(url, body, timeout):
            raise ConnectionRefusedError()
        agent.post = down
        run(agent, "where's Kylo?")
        rec = last(agent)
        self.assertEqual(rec["outcome"], "llm_error")
        self.assertIn("llm_error", rec["triggers"])

    def test_tool_error_is_recorded(self):
        class BrokenHA(FakeHA):
            def call(self, domain, service, data):
                return {"ok": False, "error": "entity unavailable"}
        llm = ScriptedLLM(tool_call("ha_call", {"domain": "light", "service": "turn_on", "entity_id": "light.bedroom"}),
                          reply("The lamp didn't respond."))
        agent, _ = traced(llm, ha=BrokenHA())
        run(agent, "turn on the bedroom lamp now please, and make it quick")
        rec = last(agent)
        self.assertIn("tool_error", rec["triggers"])
        self.assertIn("entity unavailable", json.dumps(rec["steps"]))

    def test_client_leaving_mid_turn_is_abandoned(self):
        llm = ScriptedLLM(tool_call("presence_now", {}), reply("unused"))
        agent, _ = traced(llm)
        events = agent.run([{"role": "user", "content": "Is Luna inside?"}], "s1")
        next(events)                      # the tool_call event reaches the browser, then the tab closes
        events.close()
        self.assertEqual(last(agent)["outcome"], "abandoned")


class TestLog(unittest.TestCase):
    def test_rotation_and_summary(self):
        path = os.path.join(tempfile.mkdtemp(), "trace.jsonl")
        log = TraceLog(path, max_bytes=400)
        for i in range(6):
            log.write({"at": 1000.0 + i, "outcome": "answered" if i % 2 else "step_cap", "path": "loop", "ms": 100 * i,
                       "steps": [{"tool": "presence_now", "ok": i != 3}], "triggers": ["step_cap"] if i % 2 == 0 else []})
        self.assertTrue(os.path.exists(path + ".1"))                 # rotated, one old copy kept
        recent = log.recent(10)
        self.assertEqual(recent[0]["at"], 1005.0)                    # newest first, across both files
        s = log.summary(hours=1, now=1010.0)
        self.assertEqual(s["turns"], len(recent))
        self.assertEqual(s["tools"]["presence_now"], len(recent))
        self.assertIn("step_cap", s["outcomes"])


if __name__ == "__main__":
    unittest.main()
