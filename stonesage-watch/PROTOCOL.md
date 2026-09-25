# Wire protocol (v1)

All frames are JSON objects with short keys to fit Bluetooth + Instinct 2 memory.
The same objects travel StoneSage → bridge → phone (WebSocket) → watch (Connect IQ message).

## Bridge → watch

| k      | Target     | Fields                                                             |
|--------|------------|--------------------------------------------------------------------|
| `ask`  | watch app  | `id`, `t` text (≤140), `o` options (≤4, ≤14 chars), `x` TTL s, `p` project?, `d`=1 if destructive |
| `done` | watch app  | `id`, `t`, `p`?                                                    |
| `err`  | watch app  | `id`, `t`, `p`?                                                    |
| `clr`  | watch app  | `id` — remove from inbox (answered elsewhere / expired)            |
| `st`   | watch face | `a` agents `[{p, s, t, pr?}]`, `q` pending ask count               |
| `use`  | watch face | `m` metrics `{tok, usd, mtd, bud, ltk, lsh}` (any may be missing)  |
| `cfg`  | watch face | `slots` — 5 metric IDs for the upper-half slots                    |

Agent state `s`: `wait` (needs you), `err`, `run`, `done`, `idle`. The bridge sorts agents in that order.

Destructive asks (`d`) are always rewritten to options `["Deny", "At desk"]` — the watch can stop
or defer a destructive action, never approve it.

## Watch → bridge

| Frame              | Meaning                                    |
|--------------------|--------------------------------------------|
| `{"id":"a1f3","r":0}` | Reply: index into the ask's `o` list    |
| `{"k":"sync"}`     | Resend all pending asks + status + usage   |

## Bridge → StoneSage (reply webhook, optional)

`POST $STONESAGE_REPLY_WEBHOOK` with `{"id","r","choice","p","d","state"}`.
`state` is `answered` or `expired` (`r = -1`). Or poll `GET /events/{id}`.

## Metric IDs (watch face slots)

0 none · 1 time · 2 date · 3 battery · 4 steps · 5 heart rate · 6 Claude tokens today ·
7 Claude $ today · 8 budget % (month) · 9 local tokens today · 10 local share % ·
11 pending asks · 12 phone notifications · 13 data age · 14 Claude $ month-to-date
