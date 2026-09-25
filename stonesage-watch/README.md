# StoneSage ⇄ Instinct 2

```
StoneSage ──POST /events──▶ watch-bridge (StoneSage LXC :8890)
                                 ▲  │ WebSocket /ws/watch
             bigserv: socat ─────┘  │ (tailscale serve https :8443)
                                    ▼
                     Android companion (S25 Ultra, foreground service)
                                    │ Connect IQ Mobile SDK
                     ┌──────────────┴───────────────┐
                     ▼                              ▼
             watch-app (asks, replies)     watch-face (usage + status)
```

| Folder | What it is |
|---|---|
| `bridge/` | FastAPI service: event queue, pending asks (SQLite), usage collector, `stonesage_client.py` |
| `deploy/` | systemd units + one-shot Tailscale Serve setup for bigserv |
| `android/` | Kotlin companion: WebSocket ⇄ Garmin relay, boot start, Samsung battery helpers |
| `watch-app/` | Monkey C device app: wake prompt, inbox, reply menus |
| `watch-face/` | Monkey C watch face: 5 configurable metric slots up top, agent status below |
| `PROTOCOL.md` | Every frame on the wire + metric IDs |

## 1. Bridge (StoneSage LXC)

```bash
sudo useradd -r -s /usr/sbin/nologin watchbridge
sudo mkdir -p /opt/watch-bridge && sudo cp bridge/*.py bridge/requirements.txt /opt/watch-bridge/
cd /opt/watch-bridge && sudo python3 -m venv .venv && sudo .venv/bin/pip install -r requirements.txt
sudo cp bridge/.env.example /etc/watch-bridge.env && sudo chmod 600 /etc/watch-bridge.env  # fill tokens
sudo cp deploy/watch-bridge.service /etc/systemd/system/ && sudo systemctl enable --now watch-bridge
curl -s localhost:8890/healthz
```

Smoke test from the LXC:
```bash
export BRIDGE_PUBLISH_TOKEN=...   # from /etc/watch-bridge.env
python3 -c "from stonesage_client import WatchBridge as W; w=W(); \
  print(w.ask('Test ask from StoneSage', ['Yes','No'], project='test')); \
  w.status([{'p':'stonesage','s':'run','t':'bridge smoke test','pr':30}])"
```

## 2. bigserv (Tailscale already running)

Tailscale Serve only proxies to localhost, so a socat unit forwards bigserv's
`127.0.0.1:8890` to the LXC. Edit the LAN IP in `deploy/bigserv-watch-forward.service`, then:
```bash
cd deploy && sudo ./bigserv-tailscale.sh
```
It prints the bridge URL (`https://bigserv.<tailnet>.ts.net:8443`). Tailnet-only; no Funnel, no port forwards.

## 3. Android companion

1. Open `android/` in Android Studio (let it add the Gradle wrapper and bump versions if it asks).
2. Run on the S25 Ultra. Enter the bridge URL + `BRIDGE_PHONE_TOKEN`, tap **Save & start**.
3. Tap **Allow unrestricted battery**, then add this app, Garmin Connect, and Tailscale to
   *Settings → Battery → Background usage limits → Never sleeping apps*. Turn on Tailscale's always-on VPN.

If a Connect IQ listener signature doesn't compile against your SDK version, use
Android Studio's *Implement members* on that `object :` — the bodies stay the same.

## 4. Watch app + face

VS Code + Monkey C extension, Instinct 2 device profile installed.

- Build each folder for `instinct2`; copy the `.prg` files to `GARMIN/APPS/` over USB.
- **Face settings on a sideloaded face can't be edited from the phone.** Options:
  - Let StoneSage drive the layout: `WatchBridge().layout([1, 8, 2, 6, 9])` (default on).
  - Or upload the face as a private *beta app* in the Connect IQ store to get phone settings.
  - For the polling fallback, set `bridgeUrl` / `readToken` in `properties.xml` for your local
    build only — don't commit the real token.

### Simulator testing (no watch needed)

```bash
adb forward tcp:7381 tcp:7381     # phone ⇄ Connect IQ simulator
```
Tick *Simulator mode* in the companion, run the app/face in the simulator, publish test events.

## Face layout (176×176)

```
┌───────────────┬──────┐
│  SLOT 1 (big) │ SLOT │   upper half: any metric in any slot
│  SLOT 3       │  2   │   (settings or StoneSage `cfg`)
│ SLOT 4 │ SLOT 5      │
├──────────────────────┤
│ > stonesage   1/3    │   lower half: reserved for agents
│ refactor usage.py    │   (rotates each minute if enabled)
│ [██████░░░░]         │
│ 2 ASK  3m ago        │
└──────────────────────┘
```
Metric IDs are in `PROTOCOL.md`.

## Things to verify early

- **Push to the face.** The face registers for phone-message events (the Instinct 2 supports
  them at API 3.2), but test it in the simulator first. If pushes don't arrive, the 5-minute
  snapshot poll still works.
- **Cost units.** Run one manual `curl` against the Anthropic cost report and set
  `COST_AMOUNT_DIVISOR` so the dollar figures match the Console.
- **WebSocket through Tailscale Serve.** Check `/healthz` shows `"phones": 1` once the companion is running.
- **Memory.** Check the simulator's memory view after a burst of asks; the inbox is capped at 8 items.
- **Destructive actions.** Asks sent with `destructive=True` only ever offer *Deny* / *At desk*.
