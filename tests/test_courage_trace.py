"""Offline tests for the trace: what gets recorded for each way a Courage turn can go, the escalation triggers
(recorded only), a client leaving mid-turn, Boost call records (metadata only: never message text or home names),
patrol sweep records, rotation, and the summary counts per kind."""

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


class TestBoostRecords(unittest.TestCase):
    def test_metadata_only_and_fallthrough(self):
        from unittest import mock
        from test_boost import ENV, Clock, FakeHttp, cfg, reference_policy
        from boost.router import BoostRouter
        recs = []
        http = FakeHttp({"groq.com": (429, {"retry-after": "30"}, {"error": {"message": "rate limit"}})})
        r = BoostRouter(lambda: cfg(), None, http=http, env=ENV, clock=Clock(), home_terms=("luna",))
        r.on_call = recs.append
        with mock.patch("boost.egress.egress_allowed", reference_policy):
            res = r.complete([{"role": "user", "content": "Did Luna eat her dinner at 192.168.1.50?"}], "courage")
        self.assertTrue(res["ok"])
        rec = recs[0]
        self.assertEqual((rec["kind"], rec["surface"], rec["outcome"], rec["class"]), ("boost", "courage", "answered", "home"))
        self.assertEqual(rec["found"], ["home:lan_ip", "home:term"])          # kinds of home content, not the words
        self.assertIn("fell_through", rec["triggers"])
        self.assertTrue(rec["tried"][0].startswith("groq"))
        text = json.dumps(rec)
        self.assertNotIn("Luna", text)
        self.assertNotIn("luna", text)
        self.assertNotIn("dinner", text)
        self.assertNotIn("192.168", text)

    def test_all_failed(self):
        from test_boost import ENV, Clock, FakeHttp, cfg
        from boost.router import BoostRouter
        recs = []
        down = (503, {}, {"error": "down"})
        r = BoostRouter(lambda: cfg(), None, http=FakeHttp({"": down}), env=ENV, clock=Clock())
        r.on_call = recs.append
        self.assertFalse(r.complete([{"role": "user", "content": "what is 2+2"}], "chat", allow_local=False)["ok"])
        self.assertEqual((recs[0]["outcome"], recs[0]["triggers"]), ("failed", ["all_failed"]))


class TestPatrolRecords(unittest.TestCase):
    def make(self):
        from test_patrol import TestSweep, KITCHEN
        t = TestSweep()
        p, cam = t.make()
        recs = []
        p.on_sweep = recs.append
        return p, cam, recs, KITCHEN

    def test_sweep_record(self):
        p, cam, recs, kitchen = self.make()
        p._sweep("camera.kitchen", kitchen, None, "manual") if p._claim("camera.kitchen") else None
        rec = recs[0]
        self.assertEqual((rec["kind"], rec["reason"], rec["outcome"], rec["returned"]), ("patrol", "manual", "done", "start"))
        self.assertEqual(rec["frames"], 8)
        self.assertEqual(rec["pans"][:2], [30, 60])
        self.assertEqual(rec["stopped"], "end_stop")
        self.assertEqual(rec["vision"]["calls"], 8)
        self.assertEqual(rec["triggers"], [])

    def test_return_failed_and_vision_error(self):
        p, cam, recs, kitchen = self.make()
        cam.save_ok = False
        cam.select_option = lambda eid, option, timeout=4: {"ok": False, "error": "camera offline"}
        p.vision_fn = lambda f, w, prof: {"seen": [], "error": "vision down"}
        p.sweep("camera.kitchen", kitchen)
        rec = recs[0]
        self.assertEqual((rec["reason"], rec["returned"]), ("scheduled", "failed"))
        self.assertIn("return_failed", rec["triggers"])
        self.assertIn("save_failed", rec["triggers"])
        self.assertFalse(rec["saved_start"])
        self.assertEqual(rec["home_error"], "camera offline")          # HA's words, for the next debugging session
        self.assertIn("vision_error", rec["triggers"])


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
        self.assertEqual(s["kinds"], {"courage": len(recent)})               # records without a kind are Courage turns
        self.assertEqual(s["tools"]["presence_now"], len(recent))
        self.assertIn("step_cap", s["outcomes"])

    def test_prometheus_counters(self):
        log = TraceLog(os.path.join(tempfile.mkdtemp(), "trace.jsonl"))
        log.write({"kind": "courage", "outcome": "answered", "ms": 1500, "triggers": ["nudged"],
                   "steps": [{"tool": "presence_now", "ok": True}, {"tool": "ha_call", "ok": False}]})
        log.write({"kind": "patrol", "outcome": "done", "camera": 'Drive "front"', "frames": 5, "ms": 50000, "triggers": []})
        text = log.metrics.text()
        self.assertIn('stonesage_trace_records_total{kind="courage",outcome="answered"} 1', text)
        self.assertIn('stonesage_trace_triggers_total{kind="courage",trigger="nudged"} 1', text)
        self.assertIn('stonesage_courage_tool_calls_total{tool="ha_call",ok="false"} 1', text)
        self.assertIn('stonesage_patrol_frames_total{camera="Drive \\"front\\""} 5', text)   # quotes escaped
        self.assertIn('stonesage_trace_duration_seconds_sum{kind="patrol"} 50.0', text)

    def test_kind_filter(self):
        log = TraceLog(os.path.join(tempfile.mkdtemp(), "trace.jsonl"))
        log.write({"kind": "courage", "at": 1.0, "outcome": "answered"})
        log.write({"kind": "boost", "at": 2.0, "outcome": "failed", "provider": "groq"})
        log.write({"kind": "patrol", "at": 3.0, "outcome": "done", "camera": "Driveway"})
        self.assertEqual([r["kind"] for r in log.recent(10, "boost")], ["boost"])
        s = log.summary(hours=1, now=10.0)
        self.assertEqual((s["kinds"], s["cameras"]), ({"courage": 1, "boost": 1, "patrol": 1}, {"Driveway": 1}))


if __name__ == "__main__":
    unittest.main()
