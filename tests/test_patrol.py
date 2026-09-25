"""Offline tests for the PTZ patrol: schedule rules, who counts as home, a full simulated sweep that finds the end
stop, and the vision JSON parsing. The camera is a fake whose picture depends on its pan position."""

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "StoneSage", "backend"))

from PIL import Image  # noqa: E402

import patrol as pt  # noqa: E402

KITCHEN = {"name": "Kitchen", "ptz": "kitchen", "frames": "frigate:kitchen", "home_preset": "Living Room",
           "quiet_when_home": True}
DRIVE = {"name": "Driveway", "ptz": "drive", "frames": "go2rtc:drive", "home_preset": "Doors",
         "battery_sensor": "sensor.drive_battery"}


class TestRules(unittest.TestCase):
    def test_indoor_camera_pauses_while_a_resident_is_home(self):
        self.assertIsNone(pt.interval_for(KITCHEN, 15, None, True, ["Austin"]))
        self.assertEqual(pt.interval_for(KITCHEN, 15, None, False, []), 15)

    def test_solar_camera_battery_gate(self):
        self.assertEqual(pt.interval_for(DRIVE, 15, 80, True, []), 15)    # daylight, healthy
        self.assertEqual(pt.interval_for(DRIVE, 15, 80, False, []), 60)   # night
        self.assertEqual(pt.interval_for(DRIVE, 15, 45, True, []), 60)    # daylight but below 60 %
        self.assertIsNone(pt.interval_for(DRIVE, 15, 25, True, []))       # below 30 %
        self.assertIsNone(pt.interval_for(DRIVE, 15, None, True, []))     # battery unknown

    def test_residents_home_prefers_ha_and_falls_back_to_cameras(self):
        ha = {"Austin": "not_home", "Savannah": None}.get
        self.assertEqual(pt.residents_home(["Austin", "Savannah"], ha, {"austin": 1.0, "savannah": 30.0}), ["Savannah"])
        self.assertEqual(pt.residents_home(["Austin", "Savannah"], ha, {"savannah": 400.0}), [])
        self.assertEqual(pt.residents_home(["Austin"], {"Austin": "home"}.get, {}), ["Austin"])

    def test_vision_json_parsing(self):
        self.assertEqual(pt.parse_vision_json('```json\n{"seen": ["Kylo"], "note": "dog on rug"}\n```')["seen"], ["Kylo"])
        self.assertEqual(pt.parse_vision_json("I see a dog")["seen"], [])


def jpeg(shade):
    buf = io.BytesIO()
    Image.new("L", (160, 90), shade).save(buf, format="JPEG")
    return buf.getvalue()


class FakeCamera:
    """Pan range 0..240 deg in 30 deg steps; the picture's brightness encodes the position."""
    def __init__(self):
        self.pos, self.angle, self.calls = 120, 15, []

    def press_button(self, eid):
        self.calls.append(eid)
        step = self.angle if eid.endswith("left") is False else -self.angle
        self.pos = max(0, min(240, self.pos + step))
        return {"ok": True}

    def call_service(self, domain, service, data):
        if data.get("entity_id", "").endswith("movement_angle"):
            self.angle = data["value"]
        return {"ok": True}

    def select_option(self, eid, option):
        self.calls.append(f"{eid}={option}")
        self.pos = 120
        return {"ok": True}

    def get_state(self, eid):
        return {"sensor.drive_battery": {"state": "90"}, "sun.sun": {"state": "above_horizon"}}.get(eid)

    def frame(self, _source):
        return jpeg(20 + self.pos)                 # 0..240 deg -> shade 20..260 (clamped by PIL at 255)


class TestSweep(unittest.TestCase):
    def make(self, vision_seen=("Kylo",), in_view=True):
        cam = FakeCamera()
        cfg = {"patrol": {"enabled": True, "step_deg": 30, "max_frames": 9, "settle_s": 0, "residents": ["Austin"],
                          "cameras": {"camera.kitchen": KITCHEN}}}
        presence = {"locations": {}, "known_entities": {"people": [{"name": "Austin"}], "pets": [{"name": "Kylo"}]}}
        p = pt.Patrol(lambda: cfg, cam, cam.frame, lambda f, w, prof: {"seen": list(vision_seen) + ["Nobody"]},
                      lambda c: [{"label": "dog"}] if in_view else [], lambda: presence, clock=lambda: 1000.0,
                      sleep=lambda s: None)
        return p, cam

    def test_sweep_starts_at_left_end_stops_at_right_end_and_returns_home(self):
        p, cam = self.make()
        res = p.sweep("camera.kitchen", KITCHEN)
        self.assertEqual(res["frames"], 9)                          # 0..240 deg = 9 positions, then the end stop
        self.assertEqual(cam.calls[:3], ["button.kitchen_move_left"] * 3)
        self.assertEqual(cam.calls[-1], "select.kitchen_move_to_preset=Living Room")
        self.assertEqual(cam.angle, 15)                             # step size restored
        self.assertEqual(set(p.locations()), {"kylo"})              # unknown names from the VLM are dropped
        self.assertTrue(p.frame("camera.kitchen", 0))

    def test_last_sweep_survives_a_restart_and_next_is_set(self):
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "patrol_state.json")
        p, cam = self.make()
        p.state_path = path
        p.state["camera.kitchen"] = {"interval_s": 900}
        p.sweep("camera.kitchen", KITCHEN)
        self.assertEqual(p.status()["cameras"]["camera.kitchen"]["next"], 1000.0 + 900)
        p2 = pt.Patrol(p.cfg_fn, cam, cam.frame, p.vision_fn, p.frigate_in_view, p.presence_fn,
                       clock=lambda: 1100.0, sleep=lambda s: None, state_path=path)
        self.assertEqual(p2.state["camera.kitchen"]["last"], 1000.0)
        self.assertEqual(p2.due("camera.kitchen", KITCHEN), "waiting")   # 100 s after the sweep, not due again

    def test_frigate_camera_skips_vision_when_nobody_is_in_view(self):
        p, _ = self.make(in_view=False)
        p.sweep("camera.kitchen", KITCHEN)
        self.assertEqual(p.locations(), {})

    def test_hand_moved_camera_is_left_alone_and_home_resident_pauses(self):
        p, _ = self.make()
        p.note_manual("camera.kitchen")
        self.assertEqual(p.due("camera.kitchen", KITCHEN), "moved by hand recently")
        p.manual_at.clear()
        p.presence_fn = lambda: {"locations": {"austin": {"minutes_ago": 5}}}
        self.assertEqual(p.due("camera.kitchen", KITCHEN), "paused: Austin home")


if __name__ == "__main__":
    unittest.main()
