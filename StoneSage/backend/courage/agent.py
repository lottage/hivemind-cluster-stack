"""
Courage's tool loop against the coordinator's OpenAI-compatible API (llama.cpp, jinja templates on).

run() yields plain event dicts; sse() turns them into the SSE chunks the StoneSage chat UI already
understands (tool_call / tool_result events and OpenAI-style content deltas).

Approval flow: an action the user ordered outright ("turn off the TV lights") runs at once. When Courage
inferred it ("it's cold in here" -> raise the heat) or it is an unlock/open, the loop stops, the action is
parked in PendingActions for that session, and Courage asks. A later "yes" in the same session runs it,
"no" drops it, anything else lets it expire.
"""

import json
import re
import threading
import time
import urllib.request
import uuid
from typing import Any, Callable, Dict, Iterator, List, Optional

from . import reflex
from .prompt import build_system_prompt
from .tools import CourageTools
from .trace import TraceLog, TurnTrace

AFFIRM = re.compile(r"^\s*(yes|yeah|yep|yup|y|ok|okay|sure|do it|go ahead|go for it|approved?|confirm(ed)?|please do)\b", re.I)
DENY = re.compile(r"^\s*(no|nope|nah|cancel|don'?t|do not|stop|never ?mind|leave it)\b", re.I)
TOOL_MARKUP = re.compile(r":::(TOOL_CALL|TOOL_RESULT|APPROVAL):::.*?:::END_(TOOL_CALL|TOOL_RESULT|APPROVAL):::", re.S)
THINK = re.compile(r"<think>.*?</think>", re.S)
# "I'll check the cameras", "let me look", "one moment": a promise to use a tool without calling it
PROMISE = re.compile(r"\b(i'?ll|i will|let me|going to|one moment|checking|(would you like|do you want|want) me to)\b.{0,40}"
                     r"\b(check|look|see|find|search|scan|increase|adjust|set|turn)"
                     r"|say yes to approve|\bshall i\b", re.I)  # an approval question only counts if a tool call made it
# "Would you like me to check anything else?", "Let me know if...": filler that makes every reply end in a question
TRAILING_OFFER = re.compile(r"\s*(?:(?:would you like|do you want|shall i|should i|want me to|can i|is there)[^.?!]*"
                            r"\banything else\b[^.?!]*[?.!]|(?:let me know|feel free)[^.?!]*[.!])\s*$", re.I)
NUDGE = "You described a tool call instead of making it. Call the right tool now; do not reply in text."

HISTORY_TURNS = 4  # 2 exchanges: enough for follow-ups; longer history made the coordinator model skip tools (live eval, Qwen3-14B)
FRESH_FACTS = ("For the next message: device states, temperatures, who is where, camera views and household notes "
               "(cars, preferences, past events) must come from a tool call you make now, not from earlier replies or guesses.")


def spoken(text: str) -> str:
    """Text for a speaker (HA voice, Echo): no markdown, no 'say yes to approve' UI wording."""
    text = re.sub(r"[*`#>]+", "", text or "").replace("_", " ")
    text = text.replace("Say yes to approve.", "Just say yes.")
    return re.sub(r"\s+", " ", text).strip()


class PendingActions:
    """One pending approval per session, expiring after `ttl` seconds."""

    def __init__(self, ttl: float = 300.0):
        self.ttl = ttl
        self._lock = threading.Lock()
        self._items: Dict[str, Dict[str, Any]] = {}

    def put(self, session_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        action = dict(action, id=uuid.uuid4().hex[:8], created=time.time())
        with self._lock:
            self._items[session_id] = action
        return action

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            a = self._items.get(session_id)
            if a and time.time() - a["created"] > self.ttl:
                self._items.pop(session_id, None)
                return None
            return a

    def pop_by_id(self, action_id: str) -> Optional[Dict[str, Any]]:
        """Take a parked action by its id, whichever session parked it (phone approvals don't know the session)."""
        with self._lock:
            for sid, a in list(self._items.items()):
                if a.get("id") == action_id:
                    self._items.pop(sid, None)
                    return a if time.time() - a["created"] <= self.ttl else None
        return None

    def pop(self, session_id: str) -> Optional[Dict[str, Any]]:
        a = self.get(session_id)
        with self._lock:
            self._items.pop(session_id, None)
        return a


def _http_post_json(url: str, body: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    req = urllib.request.Request(url, json.dumps(body).encode("utf-8"), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


class CourageAgent:
    def __init__(self, tools: CourageTools, llm_url: str, presence_fn: Optional[Callable[[], Dict[str, Any]]] = None,
                 runs_on_fn: Optional[Callable[[], Optional[str]]] = None,
                 pending: Optional[PendingActions] = None, max_steps: int = 5, timeout: float = 90.0,
                 post: Callable[[str, Dict[str, Any], float], Dict[str, Any]] = _http_post_json):
        base = llm_url.rstrip("/")
        if not base.endswith("/chat/completions"):
            base = base + ("/chat/completions" if base.endswith("/v1") else "/v1/chat/completions")
        self.url = base
        self.tools = tools
        self.presence_fn = presence_fn
        self.runs_on_fn = runs_on_fn
        self.on_approval: Optional[Callable[[str, Dict[str, Any]], bool]] = None  # e.g. push to the phone
        self.learned: Optional["reflex.LearnedReflexes"] = None  # phrasings the loop resolved, replayed without the LLM
        self.trace_log: Optional[TraceLog] = None  # one record per turn (courage/trace.py); None = not recorded
        self.pending = pending or PendingActions()
        self.max_steps = max_steps
        self.timeout = timeout
        self.post = post

    # ---- model call ----------------------------------------------------------
    def _complete(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        body = {
            "model": "coordinator",
            "messages": messages,
            "tools": self.tools.openai_tools(),
            "temperature": 0.3,
            "max_tokens": 350,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        data = self.post(self.url, body, self.timeout)
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        t = data.get("timings") or {}  # llama.cpp: predicted_n tokens generated in predicted_ms
        msg["_gen"] = (t.get("predicted_n") or (data.get("usage") or {}).get("completion_tokens") or 0, t.get("predicted_ms") or 0)
        return msg

    # ---- conversation shaping ------------------------------------------------
    def _build_messages(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        presence = None
        if self.presence_fn:
            try:
                presence = self.presence_fn()
            except Exception:
                presence = None
        runs_on = None
        if self.runs_on_fn:
            try:
                runs_on = self.runs_on_fn()
            except Exception:
                runs_on = None
        msgs: List[Dict[str, Any]] = [{"role": "system", "content": build_system_prompt(presence, runs_on=runs_on)}]
        turns = [m for m in history if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)]
        for m in turns[-HISTORY_TURNS:]:
            text = THINK.sub("", TOOL_MARKUP.sub("", m["content"])).strip()
            if text:
                msgs.append({"role": m["role"], "content": text})
        if len(msgs) > 2:
            # With history in context the model stops calling tools and answers from thin air; a late reminder fixes it
            msgs.insert(len(msgs) - 1, {"role": "system", "content": FRESH_FACTS})
        return msgs

    @staticmethod
    def _args(raw: Any) -> Dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        try:
            val = json.loads(raw or "{}")
            return val if isinstance(val, dict) else {}
        except (TypeError, ValueError):
            return {}

    # ---- reflex: bare on/off orders without the LLM ------------------------------------
    def _reflex(self, text: str, tr: TurnTrace):
        """Generator; returns True when it handled the message (events already yielded)."""
        learned = self.learned.lookup(text) if self.learned else None
        if learned:
            ent, _ = self.tools.resolve_entity(learned["domain"], learned["entity_id"])
            if ent is None:
                self.learned.forget(learned["key"])  # the device is gone: fall back to the loop
                return False
            args = {"domain": learned["domain"], "service": learned["service"], "entity_id": learned["entity_id"]}
            state = learned["service"].replace("turn_", "") if learned["service"] != "toggle" else None
            tr.path = "learned"
            handled = yield from self._switch(args, ent.get("friendly_name") or learned["name"], state, ent.get("state"), tr)
            if handled:
                self.learned.hit(learned["key"])
            else:
                tr.path = "loop"
            return handled
        order = reflex.parse(text)
        if not order:
            return False
        ent = reflex.match(order, reflex.candidates(self.tools.deps.ha_states))
        if not ent:
            return False
        args = {"domain": ent["domain"], "service": f"turn_{order['state']}", "entity_id": ent["entity_id"]}
        tr.path = "reflex"
        handled = yield from self._switch(args, ent.get("friendly_name") or ent["entity_id"], order["state"], ent.get("state"), tr)
        if not handled:
            tr.path = "loop"
        return handled

    def _switch(self, args: Dict[str, Any], name: str, state: Optional[str], current: Optional[str], tr: TurnTrace):
        if self.tools.validate("ha_call", args):
            return False  # refused (e.g. server plug): let the loop explain
        if state and current == state:
            yield {"type": "final", "content": f"The {name} {'is' if not name.lower().endswith('s') else 'are'} already {state}."}
            return True
        verb = f"Switching {state}" if state else "Toggling"
        yield {"type": "tool_call", "name": "ha_call", "arguments": args, "status": f"{verb} {name}…"}
        tr.tool_started()
        result = self.tools.execute("ha_call", args)
        tr.tool("ha_call", args, result)
        yield {"type": "tool_result", "name": "ha_call", "result": result}
        ok = json.loads(result).get("ok", False) if result.startswith("{") else False
        done = f"{name} {state}." if state else f"{name} toggled."
        yield {"type": "final", "content": done if ok else f"Home Assistant refused to change the {name}."}
        return True

    # ---- the loop ------------------------------------------------------------
    def run(self, history: List[Dict[str, Any]], session_id: str = "default") -> Iterator[Dict[str, Any]]:
        """Events: tool_call, tool_result, approval_required, then usage (tokens generated, tok/s) and final.
        Each turn is recorded in self.trace_log (courage/trace.py) when it ends, however it ends."""
        gen = [0, 0.0]
        last_user = next((m["content"] for m in reversed(history) if m.get("role") == "user"), "")
        tr = TurnTrace(session_id, last_user if isinstance(last_user, str) else "")
        try:
            for ev in self._run(history, session_id, gen, tr):
                if ev["type"] == "final":
                    tr.end("answered", ev.get("content") or "")
                    if gen[0]:
                        yield {"type": "usage", "completion_tokens": gen[0],
                               "tps": round(gen[0] / (gen[1] / 1000), 1) if gen[1] else 0}
                yield ev
        except Exception:
            tr.end("error")
            raise
        finally:
            if tr.outcome is None:
                tr.end("abandoned")          # the client went away mid-turn (GeneratorExit)
            if self.trace_log:
                self.trace_log.write(tr.record())

    def _run(self, history: List[Dict[str, Any]], session_id: str, gen: List[float],
             tr: TurnTrace) -> Iterator[Dict[str, Any]]:
        messages = self._build_messages(history)
        last_user = next((m["content"] for m in reversed(history) if m.get("role") == "user"), "")

        pending = self.pending.get(session_id)
        if pending:
            if DENY.match(last_user):
                self.pending.pop(session_id)
                tr.path = "approval_no"
                yield {"type": "final", "content": "Right. Leaving it alone."}
                return
            if AFFIRM.match(last_user):
                self.pending.pop(session_id)
                tr.path = "approval_yes"
                call_id = f"call_{pending['id']}"
                yield {"type": "tool_call", "name": pending["name"], "arguments": pending["args"],
                       "status": self.tools.status_text(pending["name"], pending["args"]).replace("Asking to", "Going to")}
                tr.tool_started()
                result = self.tools.execute(pending["name"], pending["args"])
                tr.tool(pending["name"], pending["args"], result)
                yield {"type": "tool_result", "name": pending["name"], "result": result}
                messages.append({"role": "assistant", "content": "", "tool_calls": [
                    {"id": call_id, "type": "function",
                     "function": {"name": pending["name"], "arguments": json.dumps(pending["args"])}}]})
                messages.append({"role": "tool", "tool_call_id": call_id, "content": result})
            # anything else: a new request, the old action quietly expires on its own

        if not (pending and AFFIRM.match(last_user)):
            handled = yield from self._reflex(last_user, tr)
            if handled:
                return

        nudged = False
        switched = []  # successful direct ha_calls this turn; a phrasing is learned only if it caused exactly one
        for _ in range(self.max_steps):
            t_llm = time.time()
            try:
                msg = self._complete(messages)
                gen[0] += msg["_gen"][0]
                gen[1] += msg["_gen"][1]
            except Exception as e:
                text = f"My brain on :8001 isn't answering ({type(e).__name__}). Try again in a moment."
                tr.end("llm_error", text)
                yield {"type": "final", "content": text}
                return
            tr.llm((time.time() - t_llm) * 1000, msg["_gen"][0], len(msg.get("tool_calls") or []))

            calls = msg.get("tool_calls") or []
            if not calls:
                msg["content"] = TRAILING_OFFER.sub("", THINK.sub("", msg.get("content") or "")).strip()
            if not calls and not nudged and PROMISE.search(msg.get("content") or ""):
                nudged = True
                tr.trigger("nudged")
                messages.append({"role": "assistant", "content": msg.get("content") or ""})
                messages.append({"role": "user", "content": NUDGE})
                continue
            if not calls:
                text = msg["content"]
                if self.learned and len(switched) == 1:
                    self.learned.learn(last_user, *switched[0])
                if not text:
                    tr.trigger("empty_answer")
                yield {"type": "final", "content": text or "I have nothing useful to add, which is rare."}
                return

            messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
            for i, call in enumerate(calls):
                fn = call.get("function") or {}
                name, args = fn.get("name", ""), self._args(fn.get("arguments"))
                call_id = call.get("id") or f"call_{uuid.uuid4().hex[:8]}"

                if self.tools.needs_approval(name):
                    err = self.tools.validate(name, args)
                    if err:
                        tr.invalid(name, args, err)
                        result = json.dumps({"ok": False, "error": err})
                        yield {"type": "tool_result", "name": name, "result": result}
                        messages.append({"role": "tool", "tool_call_id": call_id, "content": result})
                        continue
                if self.tools.needs_approval(name) and not self.tools.is_direct_command(name, args, last_user):
                    action = self.pending.put(session_id, {"name": name, "args": args,
                                                           "summary": self.tools.describe_action(name, args)})
                    yield {"type": "approval_required", "id": action["id"], "name": name,
                           "arguments": args, "summary": action["summary"]}
                    pushed = False
                    if self.on_approval:
                        try:
                            pushed = bool(self.on_approval(session_id, action))
                        except Exception:
                            pushed = False
                    skipped = len(calls) - i - 1
                    extra = f" (I've held back {skipped} other request{'s' if skipped > 1 else ''} until then.)" if skipped else ""
                    phone = " Or tap Yes on your phone." if pushed else ""
                    text = f"Shall I {action['summary']}? Say yes to approve.{phone}{extra}"
                    tr.end("asked_approval", text)
                    yield {"type": "final", "content": text}
                    return

                yield {"type": "tool_call", "name": name, "arguments": args, "status": self.tools.status_text(name, args)}
                tr.tool_started()
                result = self.tools.execute(name, args)
                tr.tool(name, args, result)
                yield {"type": "tool_result", "name": name, "result": result}
                if name == "ha_call" and self.learned and result.startswith("{") and json.loads(result).get("ok"):
                    ent, _ = self.tools.resolve_entity(args.get("domain", ""), args.get("entity_id", ""))
                    switched.append((args, (ent or {}).get("friendly_name") or args.get("entity_id", "")))
                messages.append({"role": "tool", "tool_call_id": call_id, "content": result})

        text = "I've gone round in circles on that one. Ask me again, more plainly?"
        tr.end("step_cap", text)
        yield {"type": "final", "content": text}

    # ---- SSE for the StoneSage chat route -----------------------------------
    def sse(self, history: List[Dict[str, Any]], session_id: str = "default") -> Iterator[str]:
        def chunk(obj: Dict[str, Any]) -> str:
            return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

        usage = None
        for ev in self.run(history, session_id):
            if ev["type"] == "usage":
                usage = {"completion_tokens": ev["completion_tokens"], "tps": ev["tps"]}
            elif ev["type"] == "final":
                yield chunk({"object": "chat.completion.chunk", "model": "courage",
                             "choices": [{"index": 0, "delta": {"content": ev["content"]}, "finish_reason": None}]})
            else:
                yield chunk(ev)
        yield chunk({"object": "chat.completion.chunk", "model": "courage", "usage": usage,
                     "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
        yield "data: [DONE]\n\n"
