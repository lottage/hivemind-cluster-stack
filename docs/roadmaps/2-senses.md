# Division 2: Senses (cameras, presence, wildlife, commentary)

Part of [the master roadmap](../ROADMAP.md) (Phases 3, 5, 8). Status wins over plans: see [STATE.md](../../STATE.md).

**What it is:** how the house knows who and what is where, within seconds, without running the vision model on every frame.

**Where the code is:** `StoneSage/backend/` (`frigate_presence.py`, `ha_presence.py`, `presence_corrections.py`,
`sighting_boxes.py`, `patrol.py`, `camera_ui.py`, `commentary.py`); Frigate and go2rtc on LXC 128 (`server setup/frigate/`);
the wildlife sentry on VM 102 (`server setup/cluster-bridge/wildlife_sentry_daemon.py`, `wildlife_admin.py`).

## Where it is now
- Frigate 0.18 (OpenVINO on the iGPU), person threshold 0.75. Presence merges Frigate, sentry and patrol, led by Life360 GPS,
  and is published to HA as `sensor.computer_seen_*`.
- Live cameras with WebRTC and an MP4 fallback, quality menu, PTZ controls. PTZ patrol every 15 min (kitchen 4 frames,
  driveway 5). The kitchen C260 sweeps now finish (duplicate TP-Link integration disabled; left-end-stop fix).
- Sighting cards with Wrong / Correct as, subject boxes, and face-library teaching. Commentary: arrival speaks; cooking and
  cleaning are logged only.

## Next, in order
1. **Make the first real correction** (John): it exercises the whole chain (card, Frigate face library, HA sensors).
2. **See a real arrival greeting on an Echo.** Nothing has spoken unprompted yet.
3. **Review the cooking/cleaning shadow log** in the trace tab; flip `commentary.mode.cooking` to "speak" only when it shows
   true hits (the camera mostly faces the living room, so expect few).
4. **Wildlife through Frigate (Phase 5).** The sentry subscribes to Frigate's deer/cat/dog/bird events instead of pulling clips
   on every Tapo alert, and runs the vision model only for re-ID traits (antlers, ear notches, coat). Burst capture from
   Frigate's recording. Hand-label 20 sightings and measure re-ID accuracy before trusting names.
5. **Daily Obsidian digest** (who came by, when, which camera, best snapshot) replacing the free-running dossiers.
6. **Savannah's watch** (Garmin) as a second "awake/asleep" signal for the commentary's resting check (she has no phone
   sensors in HA today).

## Later
- Phase 8: the "Who's Who" guessing game and the wildlife catalogue, both built on the correction plumbing above.
- Solar driveway timer polling stays off until John picks thresholds.
- Frigate's own HA integration (skipped by choice, revisit only if needed).

## Rules for this division
- Battery cameras (TC82): backoff of at least 3 minutes. Resize frames to 448-640 px before any vision call.
- Tapo locks the RTSP login after repeated failures: stop Frigate before retrying a bad password.
- Frigate formats go2rtc streams with `str.format`: a literal `{x}` must be written `{{x}}`.
- Never enable `GO2RTC_ALLOW_ARBITRARY_EXEC` (go2rtc's API has no auth).
- A sighting correction is a training signal: never overwrite one silently.

## Done when
A visitor or pet is named correctly on the card, in HA and by Computer within 2 s; the sentry no longer wakes battery cameras
for motion Frigate already classified; a month of corrections has measurably lowered the wrong-name rate.
