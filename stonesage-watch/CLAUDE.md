# CLAUDE.md — StoneSage ⇄ Garmin Instinct 2

You are implementing and hardening a scaffold that is already in this repo. The code was written
without compiling Kotlin or Monkey C, so expect build fixes. Read `README.md` and `PROTOCOL.md`
first; `PROTOCOL.md` is the contract every component must honor.

## What this system does

StoneSage (the owner's 24/7 web IDE / cluster orchestrator, LXC 120, port 8888) publishes events
to a bridge. An Android companion on a Samsung S25 Ultra holds a WebSocket to the bridge and relays
frames to a Garmin Instinct 2 over the Connect IQ Mobile SDK:

- watch-app: approval asks with 2–4 reply options → reply goes back to StoneSage
- watch-face: upper half = 5 configurable metric slots (LLM usage etc.), lower half = agent/project
  status (reserved; never put slot content there)

Network: tailnet only. bigserv runs Tailscale; Serve only proxies localhost, so bigserv runs a
socat forward 127.0.0.1:8890 → bridge in the StoneSage LXC, exposed with
`tailscale serve --bg --https=8443`. No Funnel, no router port forwards.

## Hard rules

1. **Never commit real IPs, hostnames, tailnet names, tokens or keys.** Use placeholders
   (10.0.0.x, `your-tailnet.ts.net`, `replace-me`). Real values live in `/etc/watch-bridge.env`,
   Android SharedPreferences, or local-only build overrides. Never echo secrets to the terminal.
2. **Ask before anything destructive or host-level**: deleting files/volumes, `tailscale serve reset`,
   editing systemd units on bigserv or Proxmox hosts, restarting StoneSage, `adb install` over an
   existing app. State the exact command and wait for a yes.
3. **Destructive agent actions are never approvable from the watch.** Asks with `d: true` are forced
   to `["Deny", "At desk"]` by the bridge. Keep it that way in every layer.
4. **Watch replies enter StoneSage through its normal request path**, so they trigger the same
   Tier-0 preemption of the background thinking loop as any other StoneSage request.
5. Instinct 2 constraints: API level 3.2 (no CIQ 4.x APIs), 176×176 mono MIP, subscreen top-right
   (use `WatchUi.getSubscreen()`), very tight app memory, background exit data ≤ ~8 KB, wake prompt
   ≤ 255 bytes, temporal events ≥ 5 min. Keep frames tiny; keep the inbox capped.

## Layout

```
bridge/       FastAPI bridge, usage collector, stonesage_client.py (Python 3.11+)
deploy/       systemd units + bigserv Tailscale Serve script
android/      Kotlin companion (minSdk 29, target 35, FGS type connectedDevice)
watch-app/    Monkey C device app (id 5ee31194fb424169944e5ae192a4e7d1)
watch-face/   Monkey C watch face (id 97b5e88982074e1dbb267e2c7141bd45)
```
App IDs must stay in sync between the two manifests and `android/.../Config.kt`.

## Work plan (do in order; each phase ends with its checks passing)

### Phase 0 — Recon (read-only)
- Locate the StoneSage source on LXC 120. Report language/framework, how HTTP routes are defined,
  and where agent tasks start, finish, fail, and currently ask for confirmation.
- Confirm tool availability: Python 3.11+, Android SDK/Gradle, Connect IQ SDK + `monkeyc`,
  a developer key for signing. Report what's missing; don't install system packages without asking.

### Phase 1 — Bridge
- Add `bridge/tests/` with pytest + FastAPI TestClient covering: auth on every endpoint (401s),
  ask publish → WS client receives it, reply → `clr` broadcast + webhook called, invalid reply
  ignored, expiry → `r=-1` webhook, destructive rewrite, `cfg` validation (5 ints, 0..14),
  `st` sorting (wait, err, run, done, idle) and `q` count, snapshot shape, replay on `sync`.
  Mock the Anthropic API and llama-server `/metrics` (including a counter reset).
- Verify Anthropic cost-report amount units with one manual request (the owner supplies the admin
  key via env; do not print it) and set `COST_AMOUNT_DIVISOR` accordingly. If no Console org exists,
  leave `ANTHROPIC_ADMIN_KEY` empty; the face shows `--` for Claude metrics.
- Check: `pytest -q` green; `uvicorn app:app` starts with a test env; `/healthz` responds.

### Phase 2 — StoneSage integration
- Vendor `bridge/stonesage_client.py` (or reimplement in StoneSage's language).
- Add a reply webhook route (default `/api/watch/reply`) that checks
  `Authorization: Bearer $BRIDGE_PUBLISH_TOKEN` and resumes the waiting task via the normal
  request path (rule 4).
- Emit `st` on agent state changes (debounce ≥ 10 s), `ask` at existing confirmation points
  (`destructive=True` for anything irreversible), `done`/`err` at task end. Call `resolve()` when a
  pending ask is answered at the workstation so the watch clears it.
- Check: a scripted fake task produces ask → reply → resume end to end against a local bridge.

### Phase 3 — Deploy (owner confirms each host command)
- LXC: install per README §1. bigserv: fill the LAN IP placeholder locally, run
  `deploy/bigserv-tailscale.sh`.
- Check: from a tailnet device, `curl https://<bigserv>.<tailnet>.ts.net:8443/healthz`, and a
  WebSocket client with the phone token connects and receives the replay.

### Phase 4 — Android companion
- Add the Gradle wrapper; `./gradlew assembleDebug` must pass. Fix Connect IQ SDK listener
  signatures to match the resolved SDK version (the bodies are correct; nullability may differ).
- Keep: foreground service type `connectedDevice`, exponential reconnect (2 s → 60 s),
  outbox cap 20, routing ask/done/err/clr → app and st/use/cfg → face.
- Check: builds; in simulator mode (`adb forward tcp:7381 tcp:7381`) frames reach the simulator.

### Phase 5 — Watch app and face
- Build both for `instinct2` with the owner's developer key; fix compile and type-check errors
  without raising minApiLevel above 3.2.0.
- Simulator: verify the wake prompt, inbox, reply menus, `clr` removal, 8-item cap, expiry pruning;
  on the face, all 15 metrics in every slot, remote `cfg` override vs. settings, agent rotation,
  stale/no-link states, and that nothing draws into the lower half except status.
- Check the memory viewer after 8 asks; report peak usage for app, face, and background.
- **Verify early:** does `registerForPhoneAppMessageEvent` deliver to the *watch face* on Instinct 2?
  If not, remove that path and rely on the 5-minute snapshot poll; document the result.

### Phase 6 — End to end on hardware
Publish an ask → watch buzzes/prompts → reply → StoneSage resumes; destructive ask shows only
Deny/At desk; kill Wi-Fi then restore → companion reconnects and replays; reboot phone → service
auto-starts; face shows fresh usage within 5 minutes.

## Reporting
At the end of each phase, summarize what changed, what was verified, and any deviation from
`PROTOCOL.md`. If you must change the protocol, update `PROTOCOL.md` and all three components in
the same change.
