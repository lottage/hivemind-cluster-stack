# Wake-word server (VM 102, `wakeword-server.service`, Wyoming TCP :10400)

Hears "Computer" for Wyoming satellites (the Raspberry Pi 3B+ voice remote, later others). A satellite streams 16 kHz mono audio
here; this service tells it when the wake word was said; the satellite then talks to Home Assistant's "Courage" Assist pipeline
(which uses the voice server's Parakeet STT and Kokoro TTS, see `../voice-server/`).

Installed 2026-10-01 at `/opt/wakeword-server` (root-owned, world-readable, runs as the `voiceserver` user, RSS ~46 MB, MemoryMax 512M):
- `venv/` with `wyoming-openwakeword` 2.1.0 (rhasspy, Apache-2.0, installed from the `v2.1.0` git tag: PyPI only has 1.8.2, which needs
  `tflite-runtime-nightly`, not available for Python 3.14) on `pyopen-wakeword` 1.1.0 (generic wheel with the TFLite runtime built in).
- `models/computer_v2.tflite` = the community "Computer" model (MIT, github.com/fwartner/home-assistant-wakewords-collection, `en/computer`;
  reacts to "Computer" and "Hey Computer"). SHA-256 in `models/SHA256SUMS`. The service strips `_vN` from file names, so the model is
  offered as `computer`; with v1 and v2 in the same folder the first file found wins, so only v2 is in `models/` and v1 sits in `alt/`.
- Unit `wakeword-server.service` (this folder). Built-in models (okay_nabu, hey_jarvis, hey_mycroft, alexa, hey_rhasspy) come with
  the package. Status badge: "Wake word (VM 102)".

Quality, honestly: the model's own README reports ~57 % recall and ~5 false activations per hour on its test set. Smoke test here
(`Wyoming` client, Kokoro voices, clean synthetic speech): 16/16 "computer" phrases fired, 0/20 other phrases. That says the plumbing
works, NOT how it behaves with a real voice, a real mic and a TV on: tune `--threshold` / `--trigger-level` in the unit on the real
device, and if it is not good enough train a model on our own voices (openWakeWord's training notebook; Kokoro can generate the
synthetic positives) and optionally a custom verifier from John's recordings.
The community model with a "hey computer" name on openwakeword.com was rejected: sign-in to download, ONNX only, 11.7 % recall.
