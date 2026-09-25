"""Offline tests for the LIVE tab's camera tiles: battery-safe snapshot refresh, PTZ validation against HA's own
preset names, HLS proxy path checks and the WebRTC -> snapshot fallback."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "StoneSage", "backend"))

import camera_ui  # noqa: E402

CFG = {"camera_ui": {
    "camera.kitchen": {"name": "Kitchen", "live": "webrtc", "ptz": "kitchen"},
    "camera.drive": {"name": "Driveway", "live": "hls", "ptz": "drive", "min_refresh_s": 60},
    "camera.yard": {"name": "Yard", "live": "snapshot", "min_refresh_s": 180},
}}


def ha_state(entity):
    if entity == "select.drive_move_to_preset":
        return {"attributes": {"options": ["Doors", "Driveway ", "Garden"]}}
    if entity == "select.kitchen_move_to_preset":
        return {"attributes": {"options": ["Living Room"]}}
    return None


class TestSnapshot(unittest.TestCase):
    def setUp(self):
        camera_ui._snap_cache.clear()
        self.wakes = 0
        self.now = 1000.0

    def fetch(self, entity):
        self.wakes += 1
        return b"jpeg-%d" % self.wakes  # not a real image: _shrink passes it through

    def snap(self, force):
        return camera_ui.snapshot("camera.yard", CFG, self.fetch, force=force, clock=lambda: self.now)

    def test_refresh_cannot_wake_a_battery_camera_twice_within_min_refresh(self):
        self.assertEqual(self.snap(False), (b"jpeg-1", 0.0))
        self.now += 30
        img, age = self.snap(True)                 # refresh pressed 30 s later
        self.assertEqual((img, age, self.wakes), (b"jpeg-1", 30.0, 1))
        self.now += 200
        img, age = self.snap(True)                 # past 180 s: a new frame
        self.assertEqual((img, age, self.wakes), (b"jpeg-2", 0.0, 2))

    def test_plain_load_uses_cache_without_waking(self):
        self.snap(False)
        self.now += 5000
        self.snap(False)
        self.assertEqual(self.wakes, 1)

    def test_unknown_camera_is_rejected(self):
        with self.assertRaises(KeyError):
            camera_ui.snapshot("camera.nope", CFG, self.fetch)


class TestPTZ(unittest.TestCase):
    def test_moves_map_to_buttons(self):
        self.assertEqual(camera_ui.ptz_command("camera.drive", CFG, "left", "", ha_state),
                         ("button", "button.drive_move_left", None))

    def test_preset_must_match_ha_spelling_exactly(self):
        self.assertEqual(camera_ui.ptz_command("camera.drive", CFG, "preset", "Driveway ", ha_state),
                         ("select", "select.drive_move_to_preset", "Driveway "))
        with self.assertRaises(ValueError):
            camera_ui.ptz_command("camera.drive", CFG, "preset", "Driveway; rm", ha_state)

    def test_non_ptz_camera_and_bad_action(self):
        with self.assertRaises(ValueError):
            camera_ui.ptz_command("camera.yard", CFG, "up", "", ha_state)
        with self.assertRaises(ValueError):
            camera_ui.ptz_command("camera.drive", CFG, "zoom", "", ha_state)


class TestTilesAndHLS(unittest.TestCase):
    def test_webrtc_camera_falls_back_to_snapshot_without_go2rtc(self):
        tiles = camera_ui.list_cameras(CFG, ha_state, webrtc_streams={})
        self.assertEqual([(t["entity"], t["live"]) for t in tiles],
                         [("camera.kitchen", "snapshot"), ("camera.drive", "hls"), ("camera.yard", "snapshot")])
        self.assertEqual(tiles[1]["ptz"]["presets"], ["Doors", "Driveway ", "Garden"])
        self.assertNotIn("ptz", tiles[2])

    def test_webrtc_stream_is_attached(self):
        tiles = camera_ui.list_cameras(CFG, ha_state, webrtc_streams={"camera.kitchen": "kitchen_sub"})
        self.assertEqual((tiles[0]["live"], tiles[0]["stream"]), ("webrtc", "kitchen_sub"))

    def test_hls_proxy_path(self):
        self.assertEqual(camera_ui.hls_proxy_path("abcDEF123_-xyz/master_playlist.m3u8"),
                         "/api/hls/abcDEF123_-xyz/master_playlist.m3u8")
        self.assertEqual(camera_ui.hls_proxy_path("abcDEF123_-xyz/segment/12.m4s"), "/api/hls/abcDEF123_-xyz/segment/12.m4s")
        self.assertIsNone(camera_ui.hls_proxy_path("abcDEF123_-xyz/../../states"))
        self.assertIsNone(camera_ui.hls_proxy_path("abcDEF123_-xyz/config.json"))
        self.assertIsNone(camera_ui.hls_proxy_path("short/master_playlist.m3u8"))


if __name__ == "__main__":
    unittest.main()
