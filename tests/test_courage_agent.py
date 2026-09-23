"""Offline tests for the Courage tool loop: fake llama server + fake Home Assistant, no network."""

import copy
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "StoneSage", "backend"))

from courage import CourageAgent, CourageDeps, CourageTools, PendingActions  # noqa: E402

PRESENCE = {"locations": {"luna": {"last_seen": "01:23 PM", "minutes_ago": 12.0, "camera": "Kitchen/Living Room"},
                          "austin": {"last_seen": "01:43 PM", "minutes_ago": 3.0}},
            "recent_sightings": [{"entity": "Luna", "timestamp": "01:23 PM"}]}


class FakeHA:
    def __init__(self):
        self.calls = []

    def states(self, domain):
        ents = [{"entity_id": "light.kitchen", "friendly_name": "Kitchen Light", "state": "on", "attributes": {"brightness": 200}},
                {"entity_id": "light.bedroom", "friendly_name": "Bedroom Lamp", "state": "off", "attributes": {}}]
        return {"ok": True, "entities": [e for e in ents if e["entity_id"].startswith(f"{domain}.")]}

    def call(self, domain, service, data):
        self.calls.append((domain, service, data))
        return {"ok": True}


def tool_call(name, args, cid="c1"):
    return {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}}]}


def reply(text):
    return {"choices": [{"message": {"content": text}}]}


class ScriptedLLM:
    """Returns queued responses and records every request body."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, url, body, timeout):
        self.requests.append(copy.deepcopy(body))  # the agent keeps appending to its message list
        if not self.responses:
            raise AssertionError("LLM called more times than scripted")
        return self.responses.pop(0)


def make_agent(llm, ha=None, pending=None, looks=None):
    ha = ha or FakeHA()
    looks = looks if looks is not None else []
    deps = CourageDeps(
        ha_states=ha.states, ha_call=ha.call, presence=lambda: PRESENCE,
        camera_look=lambda eid, name: looks.append(eid) or f"{name}: a black and white cat on the couch.",
        camera_scan=lambda eid, name: f"{name}: scanned 3 presets, nobody there.")
    return CourageAgent(CourageTools(deps), "http://fake:8001/v1", presence_fn=lambda: PRESENCE,
                        pending=pending or PendingActions(), post=llm), ha


def run(agent, text, session="s1", history=None):
    return list(agent.run((history or []) + [{"role": "user", "content": text}], session))


class TestCourageAgent(unittest.TestCase):
    def test_is_luna_inside_uses_presence(self):
        llm = ScriptedLLM(tool_call("presence_now", {}), reply("Luna was on the kitchen camera 12 minutes ago."))
        agent, _ = make_agent(llm)
        events = run(agent, "Is Luna inside?")
        self.assertEqual([e["type"] for e in events], ["tool_call", "tool_result", "final"])
        self.assertIn('"luna"', events[1]["result"])
        self.assertIn("12 minutes", events[-1]["content"])
        # tool result was fed back with the matching id
        tool_msg = llm.requests[1]["messages"][-1]
        self.assertEqual((tool_msg["role"], tool_msg["tool_call_id"]), ("tool", "c1"))
        # thinking off, native tools on
        self.assertEqual(llm.requests[0]["chat_template_kwargs"], {"enable_thinking": False})
        self.assertEqual(len(llm.requests[0]["tools"]), 8)

    def test_presence_card_in_system_prompt(self):
        llm = ScriptedLLM(reply("Hello."))
        agent, _ = make_agent(llm)
        run(agent, "hi")
        system = llm.requests[0]["messages"][0]["content"]
        self.assertIn("Camera sightings", system)
        self.assertIn("Luna: seen 12 min ago on Kitchen/Living Room", system)
        self.assertIn("Savannah: no recent sighting", system)

    def test_camera_look_runs_freely(self):
        looks = []
        llm = ScriptedLLM(tool_call("camera_look", {"camera": "kitchen_living_room"}), reply("Luna's on the couch."))
        agent, _ = make_agent(llm, looks=looks)
        events = run(agent, "what's Luna doing?")
        self.assertEqual(looks, ["camera.kitchen_living_room_hd_stream"])
        self.assertEqual(events[0]["status"], "Looking at the kitchen living room camera…")

    def test_action_waits_for_approval_then_runs_on_yes(self):
        pending = PendingActions()
        ha = FakeHA()
        llm = ScriptedLLM(tool_call("ha_call", {"domain": "light", "service": "turn_off", "entity_id": "light.kitchen"}))
        agent, _ = make_agent(llm, ha=ha, pending=pending)
        events = run(agent, "turn off the kitchen light")
        self.assertEqual([e["type"] for e in events], ["approval_required", "final"])
        self.assertEqual(ha.calls, [], "nothing may run before approval")
        self.assertEqual(events[-1]["content"], "Shall I turn off the Kitchen Light? Say yes to approve.")

        agent.post = ScriptedLLM(reply("Done. The kitchen is dark."))
        events = run(agent, "yes")
        self.assertEqual(ha.calls, [("light", "turn_off", {"entity_id": "light.kitchen"})])
        self.assertEqual([e["type"] for e in events], ["tool_call", "tool_result", "final"])
        self.assertIsNone(pending.get("s1"))

    def test_no_cancels_pending_action(self):
        pending = PendingActions()
        ha = FakeHA()
        agent, _ = make_agent(ScriptedLLM(tool_call("ha_call", {"domain": "light", "service": "turn_on", "entity_id": "light.bedroom"})),
                              ha=ha, pending=pending)
        run(agent, "lamp on")
        events = run(agent, "no, leave it")
        self.assertEqual(events, [{"type": "final", "content": "Right. Leaving it alone."}])
        self.assertEqual(ha.calls, [])

    def test_approval_is_per_session(self):
        pending = PendingActions()
        ha = FakeHA()
        agent, _ = make_agent(ScriptedLLM(tool_call("ha_call", {"domain": "light", "service": "turn_on", "entity_id": "light.bedroom"})),
                              ha=ha, pending=pending)
        run(agent, "lamp on", session="phone")
        agent.post = ScriptedLLM(reply("Yes to what, exactly?"))
        run(agent, "yes", session="other-tab")
        self.assertEqual(ha.calls, [])

    def test_disallowed_service_is_refused_without_asking(self):
        ha = FakeHA()
        llm = ScriptedLLM(tool_call("ha_call", {"domain": "light", "service": "delete", "entity_id": "light.kitchen"}),
                          reply("I'm not permitted to do that."))
        agent, _ = make_agent(llm, ha=ha)
        events = run(agent, "delete the kitchen light")
        self.assertEqual(events[0]["type"], "tool_result")
        self.assertIn("not on Courage's allowlist", events[0]["result"])
        self.assertEqual(ha.calls, [])

    def test_made_up_entity_is_refused_with_candidates(self):
        ha = FakeHA()
        llm = ScriptedLLM(tool_call("ha_call", {"domain": "light", "service": "turn_off", "entity_id": "light.kitchen_light"}),
                          reply("There's no such light."))
        agent, _ = make_agent(llm, ha=ha)
        events = run(agent, "turn off the kitchen light")
        self.assertEqual(events[0]["type"], "tool_result")
        self.assertIn("no entity 'light.kitchen_light'", events[0]["result"])
        self.assertIn("light.kitchen", events[0]["result"])
        self.assertEqual(ha.calls, [])

    def test_entity_domain_mismatch_refused(self):
        tools = CourageTools(CourageDeps(ha_states=None, ha_call=None, presence=None, camera_look=None, camera_scan=None))
        self.assertIsNotNone(tools.validate("ha_call", {"domain": "light", "service": "turn_on", "entity_id": "lock.front_door"}))

    def test_ha_get_states_filters_by_name(self):
        llm = ScriptedLLM(tool_call("ha_get_states", {"domain": "light", "name_contains": "kitchen"}), reply("Kitchen light is on."))
        agent, _ = make_agent(llm)
        events = run(agent, "is the kitchen light on?")
        result = json.loads(events[1]["result"])
        self.assertEqual([e["entity_id"] for e in result["entities"]], ["light.kitchen"])

    def test_filler_filter_does_not_hide_entities(self):
        agent, _ = make_agent(ScriptedLLM())
        for junk in ("any", "all lights", "lights"):
            res = json.loads(agent.tools.execute("ha_get_states", {"domain": "light", "name_contains": junk}))
            self.assertEqual(res["count"], 2, junk)
        res = json.loads(agent.tools.execute("ha_get_states", {"domain": "light", "name_contains": "garage"}))
        self.assertEqual(res["count"], 2)
        self.assertIn("no light names matched", res["note"])

    def test_llm_down_gives_plain_error(self):
        def boom(url, body, timeout):
            raise ConnectionRefusedError("refused")
        agent, _ = make_agent(boom)
        events = run(agent, "hello")
        self.assertIn("isn't answering", events[-1]["content"])

    def test_history_strips_tool_markup_and_think(self):
        llm = ScriptedLLM(reply("ok"))
        agent, _ = make_agent(llm)
        hist = [{"role": "user", "content": "earlier"},
                {"role": "assistant", "content": "<think>hmm</think>:::TOOL_CALL:::x:::{}:::END_TOOL_CALL:::Luna is in."}]
        run(agent, "and now?", history=hist)
        sent = llm.requests[0]["messages"]
        self.assertEqual(sent[2], {"role": "assistant", "content": "Luna is in."})

    def test_sse_format(self):
        agent, _ = make_agent(ScriptedLLM(reply("Morning.")))
        chunks = list(agent.sse([{"role": "user", "content": "hi"}], "s"))
        self.assertTrue(all(c.startswith("data: ") and c.endswith("\n\n") for c in chunks))
        self.assertEqual(chunks[-1], "data: [DONE]\n\n")
        first = json.loads(chunks[0][6:])
        self.assertEqual(first["choices"][0]["delta"]["content"], "Morning.")

    def test_promise_without_tool_call_gets_one_nudge(self):
        llm = ScriptedLLM(reply("I'll check the thermostat for you. One moment."),
                          tool_call("ha_get_states", {"domain": "climate"}), reply("It's 68 in here."))
        agent, _ = make_agent(llm)
        events = run(agent, "is it cold in here?")
        self.assertEqual([e["type"] for e in events], ["tool_call", "tool_result", "final"])
        self.assertIn("described a tool call", llm.requests[1]["messages"][-1]["content"])

    def test_only_one_nudge(self):
        llm = ScriptedLLM(reply("Let me check that."), reply("Let me check that again."))
        agent, _ = make_agent(llm)
        events = run(agent, "hmm?")
        self.assertEqual(events, [{"type": "final", "content": "Let me check that again."}])

    def test_step_limit(self):
        llm = ScriptedLLM(*[tool_call("presence_now", {}, cid=f"c{i}") for i in range(5)])
        agent, _ = make_agent(llm)
        events = run(agent, "loop forever")
        self.assertIn("round in circles", events[-1]["content"])


if __name__ == "__main__":
    unittest.main()
