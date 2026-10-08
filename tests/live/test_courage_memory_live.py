"""
Live eval: does Courage remember across conversations? (needs the LAN; real coordinator :8001 and embedder :8003)

Uses a throwaway memory file, never the live store on LXC 120. Graded deterministically:
  1. a personal fact told in one conversation is stored as a note
  2. a NEW conversation (no shared history) about it gets an answer that uses it
  3. small talk stores nothing
  4. with notes present, a home question still goes straight to the right tool

    python tests/run_tests.py live
"""

import json
import os
import sys
import tempfile
import unittest
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "StoneSage", "backend"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from courage import CourageAgent, CourageDeps, CourageTools  # noqa: E402
from courage.memory import ConversationMemory  # noqa: E402
from test_courage_tool_selection import _coordinator_url  # noqa: E402


def _embedder_url():
    with open(os.path.join(ROOT, "StoneSage", "backend", "config.json"), encoding="utf-8-sig") as f:
        return json.load(f).get("cluster", {}).get("embedder_url", "http://192.168.1.105:8003/v1").rstrip("/")


def _post(url, body, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


class TestCourageMemoryLive(unittest.TestCase):
    def test_remembers_across_conversations(self):
        chat = _coordinator_url().rstrip("/") + "/chat/completions"
        embed = lambda texts: [d["embedding"] for d in _post(_embedder_url() + "/embeddings",  # noqa: E731
                                                             {"input": texts, "model": "embedder"})["data"]]
        llm = lambda p: _post(chat, {"model": "coordinator", "messages": [{"role": "user", "content": p}],  # noqa: E731
                                     "temperature": 0, "max_tokens": 200,
                                     "chat_template_kwargs": {"enable_thinking": False}})["choices"][0]["message"]["content"]
        mem = ConversationMemory(os.path.join(tempfile.mkdtemp(), "mem.json"), embed, llm)
        mem.learn_later = lambda u, r, s: mem.learn(u, r, s)          # inline, so the next turn sees it

        nothing = lambda *a, **k: {"ok": True, "entities": []}  # noqa: E731
        # memory_search reads the conversation notes too, as the server's _courage_memory_search does
        deps = CourageDeps(ha_states=nothing, ha_call=nothing, presence=lambda: {},
                           camera_look=lambda e, n, **k: "An empty room.", camera_scan=lambda e, n: "All clear.",
                           memory_search=lambda q: [{"text": n["text"]} for n in mem.recall(q)])
        agent = CourageAgent(CourageTools(deps), _coordinator_url(), presence_fn=lambda: {})
        agent.memory = mem
        writes = []
        mem.on_write = writes.append                                # what each learning step did, for the failure message
        from courage.trace import TraceLog
        agent.trace_log = TraceLog(os.path.join(tempfile.mkdtemp(), "trace.jsonl"))

        def say(text, session):
            events = list(agent.run([{"role": "user", "content": text}], session))
            return next((e["content"] for e in reversed(events) if e["type"] == "final"), "")

        say("My sister Emma is coming to stay next weekend, and she's really allergic to cats.", "live-mem-a")
        notes = [n["text"] for n in mem.items()]
        print("\nstored:", notes)
        turn = agent.trace_log.recent(1, "courage")[0]
        self.assertTrue(any("emma" in n.lower() for n in notes),
                        f"nothing about Emma stored: turn outcome={turn['outcome']} path={turn['path']} "
                        f"tools={[x.get('tool') for x in turn['steps'] if 'tool' in x]} learn={writes} "
                        f"reply={turn['final'][:150]!r}")

        answer = say("Who's coming to stay next weekend?", "live-mem-b")
        print("recalled answer:", answer[:200])
        self.assertIn("emma", answer.lower())

        before = len(mem.items())
        say("Tell me a joke about toasters.", "live-mem-c")
        self.assertEqual(len(mem.items()), before, f"small talk was stored: {[n['text'] for n in mem.items()]}")

        msgs = agent._build_messages([{"role": "user", "content": "Is the kitchen light still on?"}],
                                     agent._recall("Is the kitchen light still on?"))
        calls = agent._complete(msgs).get("tool_calls") or []
        self.assertEqual(calls[0]["function"]["name"] if calls else "none", "ha_get_states")


if __name__ == "__main__":
    unittest.main()
