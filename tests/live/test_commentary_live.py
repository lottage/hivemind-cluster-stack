"""
Live eval: what Computer says unprompted (commentary.py) on the real coordinator (:8001), via StoneSage's dry-run route
POST /api/commentary/test (never spoken). Graded deterministically, no LLM judge (needs the LAN):
  - one short line (<= 30 words), not empty
  - addresses the right people: a named resident's name appears; nobody else's name does; an unknown person gets no name
  - invents no senses or moods (smell, sound, taste, "you look tired"): he only sees a still picture
Added 2026-09-27 after dry runs named the wrong person ("Someone cleaning" -> "Savannah, ...") and invented a smell.

    python tests/run_tests.py live
"""

import json
import unittest
import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "StoneSage", "backend"))
from commentary import INVENTED  # noqa: E402

URL = "http://192.168.1.167:8888/api/commentary/test"
RUNS = 3
PASS_RATE = 0.9
NAMES = ("austin", "savannah", "luna", "kylo")
SENSES = INVENTED          # the same pattern commentary.py regenerates on

CASES = [
    {"who": ["savannah"], "facts": "Event: they just came home, after about 9.2 hours away. It is Sunday 17:40."},
    {"who": ["austin"], "facts": "Event: they just came home, after about 45 minutes away. It is Tuesday 12:10."},
    {"who": ["austin", "savannah"], "facts": "Event: they just came home, after about 3.5 hours away. It is Saturday 21:15."},
    {"who": ["austin"], "facts": "Event: started cooking in the kitchen; the camera shows: chopping onions on a cutting "
                                 "board. It is Sunday 18:05."},
    {"who": [], "facts": "Event: started cleaning in the kitchen; the camera shows: wiping the counter with a cloth. "
                         "It is Sunday 20:10."},
    {"who": ["savannah"], "facts": "Event: started cooking in the kitchen; the camera shows: stirring a pot on the "
                                   "stove. It is Wednesday 07:30."},
    {"who": [], "facts": "Event: started cooking in the kitchen; the camera shows: a frying pan on the stove. "
                         "It is Friday 19:45."},
]


def _ask(case):
    req = urllib.request.Request(URL, json.dumps({"trigger": "eval", **case}).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


class TestCommentaryLive(unittest.TestCase):
    def test_remarks(self):
        misses, total = [], 0
        for case in CASES:
            for _ in range(RUNS):
                total += 1
                text = (_ask(case).get("remark") or "").strip()
                low = text.lower()
                why = []
                if not text or len(text.split()) > 30:
                    why.append(f"{len(text.split())} words")
                for n in case["who"]:
                    if n not in low:
                        why.append(f"missing {n}")
                others = [n for n in NAMES if n in low and n not in case["who"]]
                if others:
                    why.append(f"names {others}")
                if SENSES.search(text):
                    why.append(f"invents {SENSES.search(text).group(0)!r}")
                print(f"  {'MISS' if why else 'ok  '} {case['who'] or ['?']}: {text}" + (f"  <- {', '.join(why)}" if why else ""))
                if why:
                    misses.append(f"{case['who']} {case['facts'][:40]}: {', '.join(why)}: {text!r}")
        rate = 1 - len(misses) / total
        print(f"\nCommentary remarks: {total - len(misses)}/{total} = {rate:.0%}")
        self.assertGreaterEqual(rate, PASS_RATE, "\n".join(misses))


if __name__ == "__main__":
    unittest.main()
