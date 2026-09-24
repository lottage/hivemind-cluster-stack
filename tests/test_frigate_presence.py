"""Offline tests for Frigate presence: identity mapping, in-view vs ended events, filtering, and the merge
with the presence hub. Event dicts mirror real Frigate 0.18 payloads (REST /api/events and ws 'after')."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "StoneSage", "backend"))

from frigate_presence import FrigatePresence, merge_locations  # noqa: E402
from courage.prompt import build_presence_card  # noqa: E402

NOW = 1790276200.0


def ev(eid, label, start, end=None, score=0.88, **kw):
    return {"id": eid, "camera": "kitchen_living_room", "label": label, "sub_label": kw.pop("sub_label", None),
            "start_time": start, "end_time": end, "has_snapshot": True, "false_positive": kw.pop("false_positive", None),
            "data": {"score": score, "top_score": score}, **kw}


def fp():
    return FrigatePresence("http://frigate:5000", {"cat": "luna", "dog": "kylo"}, min_score=0.7, clock=lambda: NOW)


class TestIdentity(unittest.TestCase):
    def test_label_mapping_and_unknown_person(self):
        p = fp()
        self.assertEqual(p.identify(ev("1", "dog", 1)), "kylo")
        self.assertEqual(p.identify(ev("2", "cat", 1)), "luna")
        self.assertEqual(p.identify(ev("3", "person", 1)), "someone")
        self.assertIsNone(p.identify(ev("4", "car", 1)))

    def test_face_sub_label_wins_in_both_shapes(self):
        p = fp()
        self.assertEqual(p.identify(ev("5", "person", 1, sub_label="Austin")), "austin")
        self.assertEqual(p.identify(ev("6", "person", 1, sub_label=["Savannah", 0.91])), "savannah")


class TestIngest(unittest.TestCase):
    def test_in_view_then_ended(self):
        p = fp()
        p.ingest(ev("a", "dog", NOW - 30))                       # new: no end_time
        loc = p.locations()["kylo"]
        self.assertEqual(loc["minutes_ago"], 0.0)
        self.assertEqual(loc["doing"], "in view now")
        p.ingest(ev("a", "dog", NOW - 30, end=NOW - 120))         # end
        loc = p.locations()["kylo"]
        self.assertEqual(loc["minutes_ago"], 2.0)
        self.assertEqual(loc["camera"], "kitchen living room")
        self.assertTrue(loc["snapshot_url"].endswith("/api/events/a/snapshot.jpg"))

    def test_low_score_and_false_positive_are_ignored(self):
        p = fp()
        self.assertIsNone(p.ingest(ev("b", "dog", NOW, end=NOW, score=0.5)))
        self.assertIsNone(p.ingest(ev("c", "dog", NOW, end=NOW, false_positive=True)))
        self.assertEqual(p.locations(), {})

    def test_older_event_does_not_overwrite_newer(self):
        p = fp()
        p.ingest(ev("new", "cat", NOW - 60, end=NOW - 60))
        p.ingest(ev("old", "cat", NOW - 900, end=NOW - 900))     # replayed out of order
        self.assertEqual(p.locations()["luna"]["event_id"], "new")

    def test_websocket_frame_with_string_payload(self):
        p = fp()
        frame = json.dumps({"topic": "events", "payload": json.dumps({"type": "new", "after": ev("w", "dog", NOW)})})
        self.assertEqual(p.handle_message(frame), "kylo")
        self.assertIsNone(p.handle_message(json.dumps({"topic": "stats", "payload": "{}"})))


class TestCameraLook(unittest.TestCase):
    def _fake_urlopen(self, events):
        import io
        from unittest import mock
        resp = mock.MagicMock()
        resp.__enter__.return_value = io.BytesIO(json.dumps(events).encode())
        return mock.patch("frigate_presence.urllib.request.urlopen", return_value=resp)

    def test_in_view_now_filters_ended_low_and_false_positive(self):
        events = [ev("live", "dog", NOW - 40), ev("done", "cat", NOW - 90, end=NOW - 60),
                  ev("weak", "person", NOW - 5, score=0.4), ev("fp", "person", NOW - 5, false_positive=True),
                  ev("anon", "person", NOW - 5)]
        with self._fake_urlopen(events):
            objs = fp().in_view_now("kitchen_living_room")
        self.assertEqual([(o["name"], o["for_s"]) for o in objs], [("kylo", 40), ("someone", 5)])

    def test_describe_in_view_names_known_and_hedges_unknown(self):
        from frigate_presence import describe_in_view
        text = describe_in_view([{"label": "dog", "name": "kylo", "for_s": 40},
                                 {"label": "person", "name": "someone", "for_s": 5}])
        self.assertEqual(text, "Kylo (dog, in view 40 s), a person (not identified, in view 5 s)")


class TestMerge(unittest.TestCase):
    def test_newest_source_wins_per_identity(self):
        hub = {"austin": {"minutes_ago": 12.0, "camera": "Kitchen/Living"}, "kylo": {"minutes_ago": 30.0}}
        frig = {"kylo": {"minutes_ago": 0.0, "source": "frigate"}, "luna": {"minutes_ago": 5.0, "source": "frigate"}}
        out = merge_locations(hub, frig)
        self.assertEqual(out["kylo"]["source"], "frigate")
        self.assertEqual(out["austin"]["minutes_ago"], 12.0)   # hub still names people Frigate can't
        self.assertIn("luna", out)

    def test_card_shows_in_view_and_unidentified_person(self):
        card = build_presence_card({"locations": {"kylo": {"minutes_ago": 0.0, "camera": "kitchen living room"},
                                                  "someone": {"minutes_ago": 3.0, "camera": "kitchen living room"}}})
        self.assertIn("- Kylo: in view now on kitchen living room", card)
        self.assertIn("A person, not identified: seen 3 min ago", card)


if __name__ == "__main__":
    unittest.main()
