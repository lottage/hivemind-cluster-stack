# Division 1: Computer (the brain and its voice)

Part of [the master roadmap](../ROADMAP.md) (Phases 1, 2, 4, 8). Status wins over plans: see [STATE.md](../../STATE.md).

**What it is:** the tool-calling assistant. It decides what to look at and do, answers in a dry British voice, remembers
the people it talks to, and speaks through the web page, Home Assistant and the Echos.

**Where the code is:** `StoneSage/backend/courage/` (`agent.py` loop and streaming, `prompt.py`, `tools.py`, `reflex.py`,
`memory.py`, `trace.py`, `escalation.py`, `push_approvals.py`, `watch_client.py`); routed from `/api/cluster/chat`
(`server.py`, `is_courage_agent()`) and HA's Ollama API. Code names keep "courage"; anything a person sees says "Computer".

## Where it is now
- 9 tools, 5-step loop, reflexes and learned phrasings, approval rules (outright orders run, inferred ones ask,
  unlock/open-garage always ask), memory, trace, HA conversation agent, phone/watch approvals.
- Prompt-cache layout: first model call ~1 s. Replies stream sentence by sentence; web voice mode speaks in clips.
- Tool choice 47-50/50 (50 cases, single and mid-conversation), 0 wrong actions. A greeting no longer triggers a house survey.
- Qwen3-14B stays the brain (Phase 1 evals). Granite 4.0 h-tiny is the CPU stand-in.

## Next, in order
0. **Voice server on VM 102 is live** (2026-09-29; see STATE.md): STT 0.1-0.3 s, TTS 3x faster; hands-free end-of-speech
   detection and cached reflex confirmations are in (a reflex order is ~0.36 s from end of speech to first audio). Still
   to do: the first real phone test of the end-of-speech thresholds (his phrase recordings are in: Parakeet + name
   correction won, 2.6 % word errors, 0 names missed). Barge-in (talk over Computer) is built as an opt-in ✋ toggle (default off; STATE.md): John's first phone test decides
   whether it becomes the default. Then the HA Wyoming switch.
1. **Hear it.** Reload the page, try voice mode on the phone, then one HA voice device. Nothing in Phase 4 has been heard on
   real hardware except the first (failed, now fixed) test.
2. ~~**Realistic-states eval.**~~ Done 2026-09-29: `tests/live/test_courage_real_states.py` runs the whole loop against
   HA's real entities; questions can no longer trigger or offer an action (see STATE.md). Follow-ups: it still calls the
   kitchen camera's floodlight "the kitchen light"; the "already off" from a lagging HA state is fixed (reflex
   distrusts an "already" our own last command contradicts, 10 s).
3. **Invented small-talk details.** Once seen: "a bit chilly in here" without reading the thermostat. Add a graded case
   (must not state a home fact in a no-tool reply) before changing the prompt.
4. **Memory-lookup dip.** "Remind me what coolant the BMW needs." skips `memory_search` in 3 of 4 runs since the greeting fix.
   Try a wording that keeps both; check with the live eval, twice.
5. **Two-model A/B.** The 6750-only candidates (Gemma 4 12B, Ornith 9B OBLITERATED) run through the same 50 cases in a night window.

## Later
- Wake word "Computer" and local satellites for the kitchen if the Amazon round trip feels slow (about $15-60 per room).
- Kokoro is CPU-bound (~40 ms per character); a faster or GPU voice would end the wait on long replies.
- Phase 8 conversation quality: extend `tests/live/test_courage_chat.py` past "not a refusal, long enough" to follow-ups, thread
  tracking and varied phrasing, and tune against that.
- A coding-agent mode (the loop plus file/shell tools behind approval) that replaces Antigravity day to day.

## Rules for this division
- Facts about the house come from tools, never from memory. Keep prompts lean; no big raw RAG dumps, no negative identity lines.
- Verify with deterministic evals, not LLM judges. Re-run the tool-choice eval twice after any prompt change.
- Say "Computer" in anything a person sees or hears.

## Done when
Voice works in the web page, on the phone and through HA within about 2 s for simple things; the realistic-states eval
passes; a week of real use shows no invented home facts.
