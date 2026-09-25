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
        camera_look=lambda eid, name, **kw: looks.append(eid) or f"{name}: a black and white cat on the couch.",
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
        events = run(agent, "it's far too bright in the kitchen")  # inferred, so Courage asks
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
        run(agent, "the bedroom is pitch dark")
        events = run(agent, "no, leave it")
        self.assertEqual(events, [{"type": "final", "content": "Right. Leaving it alone."}])
        self.assertEqual(ha.calls, [])

    def test_approval_is_per_session(self):
        pending = PendingActions()
        ha = FakeHA()
        agent, _ = make_agent(ScriptedLLM(tool_call("ha_call", {"domain": "light", "service": "turn_on", "entity_id": "light.bedroom"})),
                              ha=ha, pending=pending)
        run(agent, "the bedroom is pitch dark", session="phone")
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
        events = run(agent, "turn off the kitchen light, it is late")
        self.assertEqual(events[0]["type"], "tool_result")
        self.assertIn("no entity 'light.kitchen_light'", events[0]["result"])
        self.assertIn("light.kitchen", events[0]["result"])
        self.assertEqual(ha.calls, [])

    def test_only_presence_looks_are_people_only(self):
        """camera_look questions can be about anything, so only presence_now's stale-sighting look may skip vision."""
        calls = []
        look = lambda eid, name, **kw: calls.append(kw) or "ok"
        tools = CourageTools(CourageDeps(ha_states=None, ha_call=None, presence=lambda: {}, camera_look=look, camera_scan=None))
        tools._camera_look("kitchen_living_room")
        tools._presence_now("luna")
        self.assertEqual(calls, [{}, {"people_only": True}])

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

    def test_direct_command_runs_without_asking(self):
        ha = FakeHA()
        llm = ScriptedLLM(tool_call("ha_call", {"domain": "light", "service": "turn_off", "entity_id": "light.kitchen"}),
                          {"choices": [{"message": {"content": "Done."}}], "timings": {"predicted_n": 40, "predicted_ms": 1000}})
        agent, _ = make_agent(llm, ha=ha)
        events = run(agent, "turn off the kitchen light, it is late")
        self.assertEqual(ha.calls, [("light", "turn_off", {"entity_id": "light.kitchen"})])
        self.assertEqual([e["type"] for e in events], ["tool_call", "tool_result", "usage", "final"])
        self.assertEqual((events[2]["completion_tokens"], events[2]["tps"]), (40, 40.0))

    def test_direct_word_must_match_the_service(self):
        tools = CourageTools(CourageDeps(ha_states=None, ha_call=None, presence=None, camera_look=None, camera_scan=None))
        on = {"domain": "light", "service": "turn_on", "entity_id": "light.kitchen"}
        self.assertTrue(tools.is_direct_command("ha_call", on, "turn the kitchen light on"))
        self.assertTrue(tools.is_direct_command("ha_call", on, "lamp on"))
        self.assertFalse(tools.is_direct_command("ha_call", on, "it's dark in here"))
        self.assertFalse(tools.is_direct_command("ha_call", on, "is the kitchen light on?"))
        self.assertFalse(tools.is_direct_command("ha_call", {"domain": "climate", "service": "set_temperature",
                                                             "entity_id": "climate.nest_thermostat"}, "it's cold in here"))
        self.assertTrue(tools.is_direct_command("speak", {"message": "dinner"}, "announce dinner is ready"))

    def test_unlock_always_asks(self):
        ha = FakeHA()
        ha.states = lambda d: {"ok": True, "entities": [{"entity_id": "lock.front_door", "friendly_name": "Front Door", "state": "locked"}]}
        agent, _ = make_agent(ScriptedLLM(tool_call("ha_call", {"domain": "lock", "service": "unlock", "entity_id": "lock.front_door"})), ha=ha)
        events = run(agent, "unlock the front door")
        self.assertEqual(events[0]["type"], "approval_required")
        self.assertEqual(ha.calls, [])

    def test_find_stale_subject_looks_through_last_camera(self):
        looks = []
        llm = ScriptedLLM(tool_call("presence_now", {"who": "luna"}), reply("Luna is on the couch."))
        agent, _ = make_agent(llm, looks=looks)
        events = run(agent, "where is luna")
        self.assertEqual(looks, ["camera.kitchen_living_room_hd_stream"])  # 12 min old > STALE_MINUTES
        self.assertIn("looked_now", events[1]["result"])

    def test_find_fresh_subject_does_not_look(self):
        looks = []
        llm = ScriptedLLM(tool_call("presence_now", {"who": "austin"}), reply("Austin was in 3 minutes ago."))
        agent, _ = make_agent(llm, looks=looks)
        run(agent, "where is austin")
        self.assertEqual(looks, [])

    def test_offer_to_check_is_nudged_into_a_call(self):
        llm = ScriptedLLM(reply("Luna was last seen a while ago. Would you like me to check the cameras?"),
                          tool_call("camera_look", {"camera": "kitchen_living_room"}), reply("She's on the couch."))
        agent, _ = make_agent(llm)
        events = run(agent, "where is luna")
        self.assertEqual([e["type"] for e in events], ["tool_call", "tool_result", "final"])

    def test_trailing_offer_is_trimmed(self):
        llm = ScriptedLLM(reply("Luna is in the living room. Would you like me to check anything else?"))
        agent, _ = make_agent(llm)
        self.assertEqual(run(agent, "thanks")[-1]["content"], "Luna is in the living room.")


if __name__ == "__main__":
    unittest.main()


class TestCourageReflex(unittest.TestCase):
    """Bare on/off orders skip the LLM; everything else must fall through to it."""

    def setUp(self):
        from courage import reflex
        self.reflex = reflex
        self.ents = [
            {"entity_id": "light.living_room_tv_lights", "friendly_name": "Living Room TV Lights", "state": "on", "domain": "light"},
            {"entity_id": "light.driveway_floodlight", "friendly_name": "Driveway/Front Door Floodlight (Timed)", "state": "off", "domain": "light"},
            {"entity_id": "switch.string_lights", "friendly_name": "String Lights", "state": "off", "domain": "switch"},
        ]

    def test_parse(self):
        p = self.reflex.parse
        self.assertEqual(p("Turn off the TV lights"), {"state": "off", "name": "the tv lights"})
        self.assertEqual(p("string lights on please"), {"state": "on", "name": "string lights"})
        self.assertEqual(p("could you switch the floodlight off?"), {"state": "off", "name": "the floodlight"})
        for text in ("is the tv light on?", "it's dark in here", "turn off the lights in ten minutes and lock up", ""):
            self.assertIsNone(p(text), text)

    def test_match_needs_exactly_one(self):
        m = lambda name: self.reflex.match({"state": "off", "name": name}, self.ents)  # noqa: E731
        self.assertEqual(m("tv light")["entity_id"], "light.living_room_tv_lights")
        self.assertEqual(m("driveway floodlight")["entity_id"], "light.driveway_floodlight")
        self.assertIsNone(m("lights"))  # ambiguous
        self.assertIsNone(m("bedroom lamp"))  # unknown

    def test_camera_and_server_switches_are_not_candidates(self):
        states = {"switch": {"ok": True, "entities": [
            {"entity_id": "switch.kitchen_living_room_privacy", "friendly_name": "Kitchen/Living Room Privacy", "state": "off"},
            {"entity_id": "switch.plug_led", "friendly_name": "Plug LED", "state": "on"},
            {"entity_id": "switch.string_lights", "friendly_name": "String Lights", "state": "off"}]}}
        names = [e["friendly_name"] for e in self.reflex.candidates(lambda d: states.get(d, {"ok": True, "entities": []}))]
        self.assertEqual(names, ["String Lights"])

    def test_agent_runs_reflex_without_llm(self):
        ha = FakeHA()
        agent, _ = make_agent(ScriptedLLM(), ha=ha)  # any LLM call would raise
        events = run(agent, "turn off the kitchen light")
        self.assertEqual(ha.calls, [("light", "turn_off", {"entity_id": "light.kitchen"})])
        self.assertEqual(events[-1]["content"], "Kitchen Light off.")

    def test_reflex_already_in_state(self):
        ha = FakeHA()
        agent, _ = make_agent(ScriptedLLM(), ha=ha)
        events = run(agent, "bedroom lamp off")
        self.assertEqual(ha.calls, [])
        self.assertEqual(events[-1]["content"], "The Bedroom Lamp is already off.")


class TestPushApprovals(unittest.TestCase):
    """Approve from the phone: Yes/No buttons on an HA notification (fake HA, no network)."""

    def setUp(self):
        from courage.push_approvals import PushApprovals
        self.sent, self.ran = [], []
        self.pending = PendingActions()
        self.push = PushApprovals("http://ha:8123", "t", "mobile_app_phone", self.pending,
                                  execute=lambda n, a: self.ran.append((n, a)) or '{"ok": true}',
                                  post=lambda path, body: self.sent.append((path, body)))

    def park(self, session="ha:192.168.1.82"):
        return self.pending.put(session, {"name": "ha_call", "args": {"domain": "light", "service": "turn_off",
                                                                       "entity_id": "light.kitchen"}, "summary": "turn off the Kitchen Light"})

    def test_policy(self):
        self.assertTrue(self.push.wants_push("ha:192.168.1.82"))
        self.assertFalse(self.push.wants_push("web-session-1"))
        self.push.policy = "always"
        self.assertTrue(self.push.wants_push("web-session-1"))

    def test_offer_sends_buttons(self):
        a = self.park()
        self.assertTrue(self.push.offer("ha:192.168.1.82", a))
        path, body = self.sent[0]
        self.assertEqual(path, "/api/services/notify/mobile_app_phone")
        self.assertEqual([b["action"] for b in body["data"]["actions"]], [f"COURAGE_YES_{a['id']}", f"COURAGE_NO_{a['id']}"])

    def test_yes_runs_the_parked_action_once(self):
        a = self.park()
        self.assertEqual(self.push.handle_action(f"COURAGE_YES_{a['id']}"), "Done: turn off the Kitchen Light.")
        self.assertEqual(self.ran, [("ha_call", {"domain": "light", "service": "turn_off", "entity_id": "light.kitchen"})])
        self.assertIn("expired", self.push.handle_action(f"COURAGE_YES_{a['id']}"))  # second tap does nothing
        self.assertEqual(len(self.ran), 1)
        self.assertNotIn("actions", self.sent[-1][1]["data"])  # outcome replaces the buttons

    def test_no_drops_it(self):
        a = self.park()
        self.assertIn("Left alone", self.push.handle_action(f"COURAGE_NO_{a['id']}"))
        self.assertEqual(self.ran, [])
        self.assertIsNone(self.pending.get("ha:192.168.1.82"))

    def test_foreign_actions_ignored(self):
        self.assertIsNone(self.push.handle_action("SOME_OTHER_APP_ACTION"))

    def test_agent_mentions_the_phone(self):
        ha = FakeHA()
        agent, _ = make_agent(ScriptedLLM(tool_call("ha_call", {"domain": "light", "service": "turn_off", "entity_id": "light.kitchen"})), ha=ha)
        agent.on_approval = lambda sid, action: sid.startswith("ha:")
        events = run(agent, "it's far too bright in the kitchen", session="ha:192.168.1.82")
        self.assertIn("tap Yes on your phone", events[-1]["content"])


class TestLearnedReflexes(unittest.TestCase):
    """A phrasing the loop resolved into one direct on/off order is replayed next time without the LLM."""

    def setUp(self):
        import tempfile
        from courage.reflex import LearnedReflexes
        self.path = os.path.join(tempfile.mkdtemp(), "reflexes.json")
        self.store = LearnedReflexes(self.path)

    def agent(self, llm, ha):
        agent, _ = make_agent(llm, ha=ha)
        agent.learned = self.store
        return agent

    def test_learn_then_replay_without_llm(self):
        ha = FakeHA()
        llm = ScriptedLLM(tool_call("ha_call", {"domain": "light", "service": "turn_off", "entity_id": "light.kitchen"}), reply("Done."))
        run(self.agent(llm, ha), "kill the kitchen light")          # not a bare on/off sentence: the LLM resolves it
        self.assertEqual(ha.calls, [("light", "turn_off", {"entity_id": "light.kitchen"})])
        self.assertIn("kill kitchen light", self.store.items)
        ha2 = FakeHA()
        ha2.states = lambda d: {"ok": True, "entities": [{"entity_id": "light.kitchen", "friendly_name": "Kitchen Light", "state": "on"}]}
        events = run(self.agent(ScriptedLLM(), ha2), "Please kill the kitchen light!")  # any LLM call would fail
        self.assertEqual(ha2.calls, [("light", "turn_off", {"entity_id": "light.kitchen"})])
        self.assertEqual(events[-1]["content"], "Kitchen Light off.")
        self.assertEqual(self.store.items["kill kitchen light"]["hits"], 1)

    def test_not_learned_from_approvals_or_multi_actions(self):
        ha = FakeHA()
        llm = ScriptedLLM(tool_call("ha_call", {"domain": "light", "service": "turn_off", "entity_id": "light.kitchen"}))
        run(self.agent(llm, ha), "it's far too bright in here")        # inferred: asks, never learned
        self.assertEqual(self.store.items, {})
        two = {"choices": [{"message": {"content": "", "tool_calls": [
            {"id": "a", "type": "function", "function": {"name": "ha_call", "arguments": json.dumps({"domain": "light", "service": "turn_off", "entity_id": "light.kitchen"})}},
            {"id": "b", "type": "function", "function": {"name": "ha_call", "arguments": json.dumps({"domain": "light", "service": "turn_off", "entity_id": "light.bedroom"})}}]}}]}
        run(self.agent(ScriptedLLM(two, reply("Both off.")), FakeHA()), "kill everything off")
        self.assertEqual(self.store.items, {})

    def test_refuses_compound_questions_and_data(self):
        args = {"domain": "light", "service": "turn_off", "entity_id": "light.kitchen"}
        self.assertFalse(self.store.learn("kill the lights in ten minutes", args, "x"))
        self.assertFalse(self.store.learn("kill the lights and the fan", args, "x"))
        self.assertFalse(self.store.learn("is the light off", args, "x"))
        self.assertFalse(self.store.learn("warm it up", {"domain": "climate", "service": "set_temperature",
                                                         "entity_id": "climate.x", "data": {"temperature": 72}}, "x"))
        self.assertTrue(self.store.learn("lights out in the kitchen please", args, "Kitchen Light") is False)  # "in" = compound

    def test_forgets_when_device_disappears(self):
        self.store.learn("kill the pantry light", {"domain": "light", "service": "turn_off", "entity_id": "light.pantry"}, "Pantry")
        ha = FakeHA()  # has no light.pantry
        agent = self.agent(ScriptedLLM(reply("There is no pantry light.")), ha)
        run(agent, "kill the pantry light")
        self.assertNotIn("kill pantry light", self.store.items)
        self.assertEqual(ha.calls, [])

    def test_persists(self):
        from courage.reflex import LearnedReflexes
        self.store.learn("lamp off now", {"domain": "light", "service": "turn_off", "entity_id": "light.bedroom"}, "Bedroom Lamp")
        self.assertIn("lamp off", LearnedReflexes(self.path).items)
