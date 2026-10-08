# Division 3: Cockpit (StoneSage web app and server)

Part of [the master roadmap](../ROADMAP.md) (Phase 5, parts of 2 and 4). Status wins over plans: see [STATE.md](../../STATE.md).

**What it is:** the one place John uses: a retro Win95-style PWA (no frameworks) on a stdlib `http.server` backend, replacing
the six separate apps he used to juggle.

**Where the code is:** `StoneSage/backend/server.py` (about 8,000 lines, roughly 205 routes in `do_GET` / `do_POST`) and
`StoneSage/frontend/` (`index.html`, `js/`, `sw.js`, `style.css`). Deployed to LXC 120 with `server setup/sync_stonesage_to_lxc.ps1`.

## Where it is now
- Chat with Computer (approvals as Yes/No buttons, tool status, streaming, phone-lock recovery, voice mode).
- F5 Smart Home & CCTV (live cameras, residents and pets, corrections), Engine Console (Model Loader, Boost, trace, memories,
  lease), `/api/health/all` badge, system profile labels read live (no hardcoded hardware).

## Next, in order
1. **Reload behaviour.** An open page keeps old JavaScript after a deploy; that cost a debugging round on 2026-09-28. Add a
   visible "new version available, reload" prompt (compare a version string from the server on an interval), and bump
   the service-worker cache name in the deploy script so it can't be forgotten.
2. **Split `server.py`** into route modules (`routes/ha.py`, `chat.py`, `engines.py`, `proxmox.py`, `cameras.py`), one small
   commit per module with a smoke test after each. Start with the smallest, lowest-traffic group; never move and change
   behaviour in the same commit.
3. **One home screen:** presence card, live cameras, climate, engine health and Computer's chat together; everything else one
   tab away.
4. **Retire the hidden legacy panes** (old "Parameters & Sampling" and "VRAM Sizer" HTML still in `index.html`, kept only
   until `harness.js` / `engine_studio.js` go).
5. **Web-side alerts** for what the phone and watch already get (approval waiting, lease ending, "Computer got stuck").

## Later
- The CLI (`harness/`) calls StoneSage's API instead of duplicating logic (see Division 7).
- The Phase 9 surfaces once they exist: lease/loop status, an `/autopilot` checkbox, the tryout picker. Same routes, same
  meaning on every surface.
- Frontend accent tokens (`ui-accent-tokens` branch) merged when John is ready.

## Rules for this division
- After **any** StoneSage code change, deploy the whole app with the sync script; deploying only a subsystem's own files once
  hid missing integration code for most of a phase.
- Code must run on Python 3.10+ (no backslashes inside f-string expressions). No frameworks in the frontend.
- No secrets in code or docs; `GET /api/config` masks secret fields and POSTs ignore masked values.
- Unit tests: `python tests/run_tests.py` (blocks non-localhost connections; plain `unittest discover` does not and once wrote
  test cards into live Valkey). Known failure: `test_ally_model_manager`.

## Done when
`server.py` is under about 2,000 lines of routing glue, every route group has a smoke test, a deploy tells open pages to
reload, and the home screen answers "what's happening at home" without a second tab.
