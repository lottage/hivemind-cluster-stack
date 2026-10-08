# Division 5: Wrist (Garmin Instinct 2 and the Android companion)

Part of [the master roadmap](../ROADMAP.md) (Phase 7). Its own rules and protocol live in
[`stonesage-watch/CLAUDE.md`](../../stonesage-watch/CLAUDE.md) and [`PROTOCOL.md`](../../stonesage-watch/PROTOCOL.md); this file
only sequences the remaining work.

**What it is:** approvals and a glanceable status on the watch. StoneSage publishes to a bridge; an Android companion relays to
the watch over the Connect IQ SDK; replies come back through StoneSage's normal approval path.

**Where the code is:** `stonesage-watch/` (`bridge/`, `android/`, `watch-app/`, `watch-face/`, `deploy/`,
`local-collectors/`); StoneSage side in `StoneSage/backend/courage/watch_client.py` and `watch_status.py`.

## Where it is now
- All six build steps are done and deployed. Passed on hardware (2026-09-28): ask round trip, destructive asks only offer
  Deny / At desk, resync after Bluetooth loss, companion restarts itself after a phone reboot (Tailscale is always-on VPN).
- Status shows compute sources (coordinator, worker, boost, frontier), not project names.

## Next, in order
1. **Wi-Fi drop and restore** on the phone: companion reconnects and replays.
2. **Face freshness**: usage on the face is fresh within 5 minutes. Also confirm whether the face receives phone-message pushes
   on the Instinct 2; if not, remove that path and rely on the 5-minute poll, and document it.
3. **One unattended full-reboot run** (phone reboot with nobody touching it) to prove the chain end to end.
4. **`done` / `err` toasts** for genuinely long-running work only (patrol sweeps, Boost fallback chains, later loop jobs), not
   chat turns. Scope separately before building.
5. **Lease and loop control on the wrist** when Division 4 step 3 and Phase 9 land: loop status and a Stop button; Another
   hour / Stop for lease check-ins already exist.
6. **Savannah's watch** using the same bridge (a second phone token and roster row), later.

## Later
- Face slots from Phase 6 metrics beyond engine health and Boost quota.
- A sideloaded face cannot edit settings from the phone; StoneSage drives the layout with `cfg`. If that becomes limiting,
  upload the face as a private Connect IQ beta app.

## Rules for this division (short form; the full list is in `stonesage-watch/CLAUDE.md`)
- Never commit real IPs, hostnames, tailnet names, tokens or keys; secrets are generated on the Linux host, never on Windows.
- Destructive asks are never approvable from the watch; the bridge forces `["Deny", "At desk"]`.
- Ask before `adb install` over the existing app, host-level changes, or anything destructive. Never change settings on
  John's phone yourself.
- Device limits: API 3.2, 176x176 mono, tiny memory, HTTPS-only outbound. Keep frames tiny and the inbox capped at 8.
- Change the protocol and all three components together, in one change.

## Done when
Every hardware check in the Phase 6 list of `stonesage-watch/CLAUDE.md` has a dated PASS, and a week of real approvals has
produced no lost or duplicated asks.
