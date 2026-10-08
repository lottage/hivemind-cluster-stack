> Roadmap: Phase 7 of [docs/ROADMAP.md](../docs/ROADMAP.md), remaining work in [docs/roadmaps/5-wrist.md](../docs/roadmaps/5-wrist.md). The rules and build history below stay authoritative for this folder.

# CLAUDE.md — StoneSage ⇄ Garmin Instinct 2

You are implementing and hardening a scaffold that is already in this repo. The code was written
without compiling Kotlin or Monkey C, so expect build fixes. Read `README.md` and `PROTOCOL.md`
first; `PROTOCOL.md` is the contract every component must honor.

## What this system does

StoneSage (the owner's 24/7 web IDE / cluster orchestrator, LXC 120, port 8888) publishes events
to a bridge. An Android companion on a Samsung S25 Ultra holds a WebSocket to the bridge and relays
frames to a Garmin Instinct 2 over the Connect IQ Mobile SDK:

- watch-app: approval asks with 2–4 reply options → reply goes back to StoneSage
- watch-face: upper half = 5 configurable metric slots (LLM usage etc.). Lower half = agent/project
  status (compact, top of the lower half) + an always-on device vitals strip (battery/steps/HR, read
  directly from the device, no bridge data needed) pinned to the very bottom (changed 2026-09-25: the
  old "status only, nothing else in the lower half" rule left most of it blank whenever idle/no-link).

Network: tailnet only. **Correction, deployed 2026-09-26**: Tailscale is not on bare bigserv --
it runs inside LXC 106 "ubuntu" (a generic community-scripts Ubuntu template, hosted on bigserv,
tailnet hostname `ubuntu`), which is what the scaffold's own README/CLAUDE.md assumed was bigserv
itself. Serve only proxies localhost, so LXC 106 runs a socat forward 127.0.0.1:8890 → 10.0.0.x:8890
(the bridge, on LXC 120), exposed with `tailscale serve --bg --https=8443`:
**`https://<bigserv>.<tailnet>.ts.net:8443`**. No Funnel, no router port forwards. Verified live
(curl 200 from inside LXC 106, using the hostname -- Tailscale Serve's TLS listener needs a real
SNI ServerName to pick the cert; connecting by raw tailnet IP fails with "no SNI ServerName").
Tailscale Serve itself needed a one-time account-level enable (`login.tailscale.com/f/serve?node=...`)
before this worked the first time -- that's a per-tailnet toggle, not per-node, so it won't recur.

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
6. **Generate secret token files on the target Linux host itself, never on Windows and `scp` over.**
   Windows Python's `print()`/text-mode file writes use CRLF; `systemd`'s `EnvironmentFile=` does not
   strip the trailing `\r`, so every value silently gets a stray carriage return baked in -- every
   Authorization header built from it then fails at the raw HTTP parse layer (a 400 "Invalid HTTP
   request received", not a clean 401), which looks nothing like an auth bug and wastes real time.
   Bit us during the 2026-09-26 deploy; fixed by writing `/etc/watch-bridge.env` via a Python
   heredoc run over SSH on the LXC itself. If a value must ever be pasted in from Windows, strip `\r`
   explicitly (`.strip()` per line) before using it, and rewrite the destination file `newline="\n"`.
7. When testing a `tailscale serve --https` endpoint, **connect by its real hostname, not by tailnet
   IP** -- the TLS listener picks its cert by SNI, and a raw-IP connection sends no usable SNI,
   failing with "no SNI ServerName" that looks like a broken cert, not a test-methodology issue.
6. **The device enforces HTTPS-only outbound requests** (confirmed 2026-09-25 in the simulator's "Use
   Device HTTPS Requirements" setting, which models real firmware behavior). `bridgeUrl` in
   `properties.xml`/phone settings must always be the bigserv Tailscale Serve HTTPS URL
   (`https://<bigserv>.<tailnet>.ts.net:8443`), never a bare `http://` LAN address — a plain-HTTP bridge
   URL will silently fail on real hardware even though it can work in the simulator with that setting off.

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

### Phase 2 — StoneSage integration (done 2026-09-26, not yet deployed -- Phase 3)
- Vendored as `StoneSage/backend/courage/watch_client.py`, reimplemented with `urllib.request`
  (not `httpx`) to match `push_approvals.py`'s existing style rather than add a dependency.
- `/api/watch/reply` added to `server.py`'s `do_POST`, Bearer-token-checked against
  `config.json watch_bridge.token`. Destructive-ness is **re-derived server-side** from the stored
  `PendingActions` entry (`ALWAYS_CONFIRM` in `courage/tools.py`), never trusted from the incoming
  payload -- verified live that an `unlock` action is correctly flagged regardless.
- `ask` fires at the same `on_approval` hook (`agent.py:324`) the phone push already uses, alongside
  it, not instead of it -- same `PendingActions`, same `execute()`. Two id spaces exist
  (`action["id"]` ours, `action["watch_id"]` the bridge's); `PendingActions.pop_by_watch_id()` bridges
  them. Whichever channel (phone or watch) answers first wins; verified an action can't be popped
  twice. `resolve()` fires both ways: a phone tap clears the watch card (`push_approvals.py`), a
  watch tap clears the phone notification (new `PushApprovals.clear()`).
- `st`: a new poller (`courage/watch_status.py`, `POLL_S=15`) maps the roster to **compute sources**,
  not arbitrary project names (John's call, 2026-09-26) -- `coordinator`/`worker` polled live against
  each engine's own `/slots` (busy = a slot mid-generation, not just Courage's own usage of it);
  `boost`/`frontier` read the trace log's most recent record of that kind (`TraceLog.recent(1, kind=)`),
  "active" if within 20s. `frontier` will show idle until `frontier_worker.py` exists and writes
  trace records. Antigravity is deliberately not in this roster: it runs on the workstation, outside
  the cluster, and StoneSage has no way to observe it (same limit hit during the Antigravity/Google
  usage investigation this session).
- `done`/`err` at task end: **not done**. Courage turns are short conversational exchanges; a toast
  after every one would be noise. Worth scoping separately for actual long-running things (patrol
  sweeps, Boost fallback chains) rather than building it against chat turns.
- Check: `WatchBridge.ask()`/`.resolve()` verified live end to end against a real bridge instance
  (`/events/{id}` showed `resolved`). `pop_by_watch_id` + the destructive re-derivation verified
  directly against the real `PendingActions`/`ALWAYS_CONFIRM` classes. `_engine_busy`/`_trace_active`
  verified against a fake `/slots` server and a real `TraceLog`. Full StoneSage suite still green
  (292 tests, the 1 failure is the pre-existing `test_ally_model_manager` one). Not yet run through a
  live LLM turn end to end -- needs the real coordinator (:8001), i.e. Phase 3 deploy.

### Phase 3 — Deploy (done 2026-09-26)
- LXC 120: `watchbridge` system user, `/opt/watch-bridge` (venv + deps), `/etc/watch-bridge.env`
  (600 root:root, fresh tokens -- generated and written entirely on the Linux host this time; the
  first attempt used local Windows Python and got CRLF line endings baked into every value, which
  systemd's `EnvironmentFile=` does not strip, silently corrupting every Authorization header the
  bridge sent or checked -- see Hard rule 6 above), `watch-bridge.service` enabled
  and running. `config.json`'s `watch_bridge.token` kept in sync with the bridge's own
  `BRIDGE_PUBLISH_TOKEN` (same value, both ends).
- LXC 106 "ubuntu" (not bare bigserv -- see the Network correction above): `watch-forward.service`
  (socat) + `tailscale serve --bg --https=8443` installed and running.
- Check, done live: `curl https://<bigserv>.<tailnet>.ts.net:8443/healthz` -> 200 from inside the
  tailnet. A real Courage turn (`POST /api/cluster/chat`, agent `courage-computer`) correctly
  initialized the whole chain and the bridge's `/watch/snapshot` showed a live roster
  (`coordinator`/`worker`/`boost`/`frontier`, all polled for real) and real `ltk` usage numbers from
  VM 102's `/metrics`. **Not yet checked**: a WebSocket client with the phone token connecting and
  receiving the replay -- needs the Android companion (Phase 4/6), not blocked on anything here.
- **A real code-deploy miss cost most of this phase's debugging time**: Phase 2's StoneSage-side
  changes (`server.py`, `courage/*.py`) were written and tested locally but never actually synced to
  LXC 120 before this phase started -- only the bridge itself got deployed at first. The live
  `push_approvals` working (pre-existing code) masked this for a while, since nothing about it hinted
  the *new* code wasn't there too. Fixed by running `server setup/sync_stonesage_to_lxc.ps1`
  (preserves the remote `config.json`, confirmed). Lesson: after any StoneSage code change, deploying
  only a subsystem's own new files (e.g. just `stonesage-watch/bridge/`) is not the same as deploying
  the StoneSage-side integration code that talks to it -- both need to go out together.

### Phase 4 — Android companion
- Add the Gradle wrapper; `./gradlew assembleDebug` must pass. Fix Connect IQ SDK listener
  signatures to match the resolved SDK version (the bodies are correct; nullability may differ).
- Keep: foreground service type `connectedDevice`, exponential reconnect (2 s → 60 s),
  outbox cap 20, routing ask/done/err/clr → app and st/use/cfg → face.
- Check: builds; in simulator mode (`adb forward tcp:7381 tcp:7381`) frames reach the simulator.
- **Status 2026-09-28.** Gradle wrapper + `assembleDebug` pass (JDK 17, compileSdk 36, CIQ companion SDK 2.4.0,
  OkHttp 4.12). An earlier build is already installed on the S25 Ultra and connects: the bridge logged 13 phone
  connects since 2026-09-27, last one still open. Fixed this session (review, then rebuilt):
  - reconnect race: a late onFailure/onClosed from a replaced socket nulled the live `ws` and started a second
    connection; each connection now carries a generation number taken *before* `newWebSocket()` (an instant
    failure can call back before it returns), and stale callbacks are ignored. A `started` flag replaces the
    `ws == null` start check (also true while a retry was pending, so a repeated start doubled relay + socket).
  - `onClosing` now finishes the close and reconnects at once (a clean bridge restart used to leave the socket
    half-closed until the 30 s ping failed).
  - frames sent while the watch was off Bluetooth were dropped by `GarminRelay.send` and never resent (the bridge
    only replays on a *phone* reconnect). The relay now reports the watch reachable (attach, and every
    `IQDeviceStatus.CONNECTED`) and the service sends `{"k":"sync"}` so pending asks reach the watch; a sync is
    never queued while offline (connecting replays anyway).
  Verified against the live bridge with a client that behaves like the companion (phone token from
  `/etc/watch-bridge.env`, never printed): replay on connect = `st` (4 roster rows, q=0) + `use`; `sync` replays
  the same; a reply to an unknown ask gets only `clr`; a wrong token is refused (403). Replays go only to the
  requesting socket, so the real phone saw nothing. **Still needs the phone:** installing this build
  (`adb install -r`, ask first -- Hard rule 2), the simulator check, and Phase 6 on hardware.

### Phase 5 — Watch app and face
- Build both for `instinct2` with the owner's developer key; fix compile and type-check errors
  without raising minApiLevel above 3.2.0.
- Simulator: verify the wake prompt, inbox, reply menus, `clr` removal, 8-item cap, expiry pruning;
  on the face, all 15 metrics in every slot, remote `cfg` override vs. settings, agent rotation,
  stale/no-link states, and that the lower half only ever draws agent status (top) and the vitals
  strip (bottom) -- never upper-half slot content leaking down.
- Check the memory viewer after 8 asks; report peak usage for app, face, and background.
- **Verify early:** does `registerForPhoneAppMessageEvent` deliver to the *watch face* on Instinct 2?
  If not, remove that path and rely on the 5-minute snapshot poll; document the result.

### Phase 6 — End to end on hardware
Publish an ask → watch buzzes/prompts → reply → StoneSage resumes; destructive ask shows only
Deny/At desk; kill Wi-Fi then restore → companion reconnects and replays; reboot phone → service
auto-starts; face shows fresh usage within 5 minutes.
- **Run 2026-09-28 with John** (S25 Ultra on USB for adb/logcat, Instinct 2 unplugged; the Sep 28 companion build
  installed over the Sep 26 one with `adb install -r`, settings kept; watch app + face on the watch are byte-identical
  to `watch-app/bin`, `watch-face/bin`). Test asks were published straight to the bridge (`POST /events`, publish token
  read on LXC 120), so replies reached StoneSage's `/api/watch/reply` with no pending action behind them.
  1. ask "tap Yes" (Yes/No) -> watch prompted -> Yes -> bridge `answered r=0 Yes` -> webhook to StoneSage 200, 10 s after
     publish. PASS.
  2. destructive ask published with o=Yes/No -> stored and sent as `["Deny","At desk"], d:1` -> watch offered only
     Deny / At desk -> Deny -> `answered Deny`. PASS.
  3. phone Bluetooth off (companion: "send st: FAILURE_DURING_TRANSFER") -> ask published -> Bluetooth on -> the ask
     appeared on the watch. The phone's bridge socket never dropped (no connect/disconnect lines in the bridge log),
     so it was the new watch-reachable `sync`, not a reconnect replay: before this build the ask was lost. PASS.
  - Also seen: after `adb install -r` the service restarts by itself (new `MY_PACKAGE_REPLACED` in BootReceiver) and
    reconnects to the bridge within 1 s. While the watch is on USB (mass-storage mode) every send fails with
    FAILURE_DURING_TRANSFER: unplug it for anything that talks to the watch.
  4. phone reboot: the BootReceiver started the service by itself (~40 s after boot, foreground connectedDevice). PASS
     for the companion. **But the chain did not come back**: Tailscale is installed on the phone and was not running
     after the reboot, and it is not the always-on VPN (`settings secure always_on_vpn_app` = null), so the tailnet
     name did not resolve ("Unable to resolve host", backing off to 60 s) until Tailscale is opened by hand. Fix (a
     phone setting, John's): Settings → Connections → More connection settings → VPN → Tailscale ⚙ → Always-on VPN
     (leave "Block connections without VPN" off). **Set by John 2026-09-28**; with Tailscale up the companion's backoff
     retry reconnected on its own (bridge: phone connected 10:15:56 UTC, stayed up). A second reboot to prove the whole
     chain unattended was skipped by choice: the parts are each verified (BootReceiver start; always-on VPN is Android's
     own mechanism; the companion retries until the name resolves), not yet in one run.
  - Not yet run: Wi-Fi drop + restore on the phone, face freshness < 5 min.

## Reporting
At the end of each phase, summarize what changed, what was verified, and any deviation from
`PROTOCOL.md`. If you must change the protocol, update `PROTOCOL.md` and all three components in
the same change.
