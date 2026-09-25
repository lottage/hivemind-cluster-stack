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
        self.pos, self.angle, self.calls = 120, 45, []     # John set a 45 deg step in HA
        self.on_press = None
        self.presets = {}                                    # temporary presets saved by the patrol
        self.save_ok = True

    def press_button(self, eid):
        if self.on_press:
            self.on_press(eid)
        self.calls.append(eid)
        step = self.angle if eid.endswith("left") is False else -self.angle
        self.pos = max(0, min(240, self.pos + step))
        return {"ok": True}

    def call_service(self, domain, service, data):
        if data.get("entity_id", "").endswith("movement_angle"):
            self.angle = data["value"]
        if service == "save_preset":
            if not self.save_ok:
                return {"ok": False, "error": "camera busy"}
            self.presets[data["name"]] = self.pos
        if service == "delete_preset":
            self.presets.pop(data["preset"], None)
        return {"ok": True}

    def select_option(self, eid, option):
        self.calls.append(f"{eid}={option}")
        if option in self.presets:
            self.pos = self.presets[option]
        else:
            self.pos = 120                                   # the home preset
        return {"ok": True}

    def get_state(self, eid):
        return {"sensor.drive_battery": {"state": "90"}, "sun.sun": {"state": "above_horizon"},
                "number.kitchen_movement_angle": {"state": str(self.angle)}}.get(eid)

    def frame(self, _source):
        return jpeg(20 + self.pos)                 # 0..240 deg -> shade 20..260 (clamped by PIL at 255)


class TestSweep(unittest.TestCase):
    def make(self, vision_seen=("Kylo",), in_view=True):
        cam = FakeCamera()
        cfg = {"patrol": {"enabled": True, "step_deg": 30, "max_frames": 9, "settle_s": 0, "residents": ["Austin"],
                          "cameras": {"camera.kitchen": KITCHEN}}}
        presence = {"locations": {}, "known_entities": {"people": [{"name": "Austin"}], "pets": [{"name": "Kylo"}]}}
        self.presence_reads = 0

        def presence_fn():
            self.presence_reads += 1
            return presence
        p = pt.Patrol(lambda: cfg, cam, cam.frame, lambda f, w, prof: {"seen": list(vision_seen) + ["Nobody"]},
                      lambda c: [{"label": "dog"}] if in_view else [], presence_fn, clock=lambda: 1000.0,
                      sleep=lambda s: None)
        return p, cam

    def test_sweep_starts_at_left_end_stops_at_right_end_and_returns_home(self):
        p, cam = self.make()
        res = p.sweep("camera.kitchen", KITCHEN)
        self.assertEqual(res["frames"], 8)                          # 30..240 deg (0 deg = wall is skipped), then the end stop
        self.assertEqual(cam.calls[:4], ["button.kitchen_move_left"] * 3 + ["button.kitchen_move_right"])
        self.assertEqual(p.status()["cameras"]["camera.kitchen"]["first_pan"], 30)
        self.assertEqual(cam.calls[-1], f"select.kitchen_move_to_preset={pt.RETURN_PRESET}")
        self.assertEqual((cam.pos, cam.presets), (120, {}))     # back where it was; temporary preset deleted
        self.assertEqual(cam.angle, 45)                             # John's step size restored, not a default
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

    def test_corrections_on_patrol_sightings(self):
        p, _ = self.make()
        p.sweep("camera.kitchen", KITCHEN)
        ref = p.locations()["kylo"]["patrol_ref"]
        self.assertFalse(p.correct(ref, "Luna", "reject")["ok"])            # not what that card showed
        res = p.correct(ref, "Kylo", "relabel", "Aunt May")
        self.assertTrue(res["ok"] and res["frame"])                         # frame handed back for face training
        self.assertEqual(set(p.locations()), {"aunt-may"})
        self.assertTrue(p.correct(p.locations()["aunt-may"]["patrol_ref"], "Aunt May", "reject")["ok"])
        self.assertEqual(p.locations(), {})
        self.assertFalse(p.correct("garbage", "Kylo", "reject")["ok"])

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

    def test_sweep_returns_to_where_john_left_it_and_falls_back_home(self):
        p, cam = self.make()
        cam.pos = 200                                         # John pointed it at the sofa
        p.sweep("camera.kitchen", KITCHEN)
        self.assertEqual(cam.pos, 200)
        self.assertEqual(cam.presets, {})
        cam.pos, cam.save_ok = 200, False                     # the save failed: home preset as before
        p.sweep("camera.kitchen", KITCHEN)
        self.assertEqual(cam.calls[-1], "select.kitchen_move_to_preset=Living Room")
        self.assertEqual(cam.pos, 120)

    def test_one_sweep_per_camera_at_a_time(self):
        p, cam = self.make()
        started = []
        import threading
        real_sweep = p._sweep
        p._sweep = lambda e, c, pr=None: started.append(e)          # "Sweep now" claims, thread records the start
        self.assertTrue(p.run_now("camera.kitchen")["ok"])
        self.assertFalse(p.run_now("camera.kitchen")["ok"])          # second press refused
        self.assertEqual(p.due("camera.kitchen", KITCHEN), "sweeping")
        self.assertEqual(p.sweep("camera.kitchen", KITCHEN)["skipped"], "already sweeping")   # scheduler too
        for t in threading.enumerate():
            if t is not threading.current_thread() and t.daemon:
                t.join(1)
        self.assertEqual(started, ["camera.kitchen"])
        p._sweep = real_sweep

    def test_manual_move_mid_sweep_stops_it_where_john_left_it(self):
        p, cam = self.make()
        clock = [1000.0]
        p.clock = lambda: clock[0]
        presses = []

        def on_press(eid):
            presses.append(eid)
            if len(presses) == 6:                  # John grabs the camera during the sweep
                clock[0] += 1
                p.note_manual("camera.kitchen")
        cam.on_press = on_press
        res = p.sweep("camera.kitchen", KITCHEN)
        self.assertTrue(res["interrupted"])
        self.assertEqual(len(presses), 6)                            # no move after John's
        self.assertNotIn("select.kitchen_move_to_preset=Living Room", cam.calls)   # and no trip home
        self.assertEqual(cam.angle, 45)
        self.assertFalse(p.state["camera.kitchen"]["busy"])

    def test_per_camera_start_step_and_frame_cap(self):
        p, cam = self.make()
        pans = []
        p.vision_fn = lambda f, where, prof: pans.append(where) or {"seen": []}
        kitchen = dict(KITCHEN, start_deg=90, step_deg=40, max_frames=4)   # John's 4-frame kitchen sweep
        res = p.sweep("camera.kitchen", kitchen)
        self.assertEqual(res["frames"], 4)
        self.assertEqual([w.split("pan ")[1] for w in pans], ["90 deg)", "130 deg)", "170 deg)", "210 deg)"])
        st = p.status()["cameras"]["camera.kitchen"]
        self.assertEqual((st["first_pan"], st["step"]), (90, 40))

    def test_run_once_reads_presence_once(self):
        p, _ = self.make()
        p.run_once()
        self.assertEqual(self.presence_reads, 1)


if __name__ == "__main__":
    unittest.main()
