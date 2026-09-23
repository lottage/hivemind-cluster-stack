# AGENTS COLLABORATION HIERARCHY: Aevu_Stev_Gen2_57D0

## Upstream Coordinator
- Coordinator: Node 1 Primary Accelerator (VM 102 :8001)
- Frontier Arbiter: Antigravity (AGY powered by gemini-3.8-flash)

## Handoff & Roaming Protocol
- When roaming off-LAN, write completed tasks to `HANDOVER.md` for reconciliation on reconnect.
- If spinning in a loop, accept out-of-band `/nudge` interventions immediately.
