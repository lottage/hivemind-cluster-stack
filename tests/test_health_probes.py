"""Offline test for the health probe list: the voice server on VM 102 is probed next to the old voice LXC (its fallback)."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "StoneSage", "backend"))

import health  # noqa: E402


def probes(cfg=None):
    return {p[1]: p for p in health.build_probes(cfg or {})}


class TestVoiceProbes(unittest.TestCase):
    def test_the_voice_server_and_its_wyoming_ports_are_probed(self):
        p = probes()
        self.assertEqual(p["Voice server (VM 102)"][3], "http://192.168.1.105:8210/health")
        self.assertEqual(p["Wyoming STT (VM 102)"][3:], ("192.168.1.105", 10301))
        self.assertEqual(p["Wyoming TTS (VM 102)"][3:], ("192.168.1.105", 10201))

    def test_the_wake_word_service_is_probed(self):
        self.assertEqual(probes()["Wake word (VM 102)"][3:], ("192.168.1.105", 10400))

    def test_the_old_voice_lxc_is_still_probed_as_the_fallback(self):
        p = probes()
        for name in ("Whisper STT", "Kokoro TTS", "Wyoming Whisper", "Wyoming Piper"):
            self.assertIn(name, p)

    def test_the_configured_voice_server_url_is_followed(self):
        p = probes({"voice": {"stt_url": "http://10.9.8.7:9000/"}})
        self.assertEqual(p["Voice server (VM 102)"][3], "http://10.9.8.7:9000/health")
        self.assertEqual(p["Wyoming STT (VM 102)"][3], "10.9.8.7")
        self.assertEqual(p["Wake word (VM 102)"][3], "10.9.8.7")


if __name__ == "__main__":
    unittest.main()
