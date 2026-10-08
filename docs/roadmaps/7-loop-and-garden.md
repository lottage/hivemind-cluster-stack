# Division 7: Loop and garden (local loop, CLI harness, the long game)

Part of [the master roadmap](../ROADMAP.md) (Phase 9, the garden, the CLI half of Phase 5). Full design detail:
[`docs/plan-2026-09-26-local-loop/DESIGN.md`](../plan-2026-09-26-local-loop/DESIGN.md). Status wins over plans: see
[STATE.md](../../STATE.md).

**What it is:** getting frontier-quality work out of local models cheaply (the frontier writes tests and specs, a local model
grinds, tests judge), and, much later, the walled "garden" where agents explore their own limits.

**Where the code is:** `harness/` (CLI, connectors, data fabric, edge fleet; duplicates some StoneSage logic), `cluster-work-mcp/`,
`agent-nudge/`, `server setup/cluster-bridge/` (frontier worker, future loop worker), `docs/plan-2026-09-26-local-loop/`.
The engine and lease half of the local loop is Division 4.

## Where it is now
- Groundwork done: Prism fork built, Bonsai 2 27B on three layouts (benchmarked), engine lease, Courage-lite, tryout slot and
  `model_eval.py`. Not built: loop worker, job routes, MCP wrappers, autopilot, hands-off, tryout picker.
- **Shelved, do not extend or re-enable:** autonomous thinking loop, Assembly Hall, agent reproduction, Citadel 3D, Blender,
  trainer runs.

## Next, in order (Phase 9)
1. **Hands-off and night grants** (Division 4 step 3): the loop cannot run for hours without them.
2. **Loop worker** on VM 102 (:8771): scratch clone per job, one job at a time, reached only through StoneSage routes. Contract
   with `allowed_paths`, `read_paths`, `protected_paths`, `test_cmd`, caps and `merge_mode`. Deterministic breakers:
   `no_change`, `same_failure`, `repetition`, `scope`, caps. Unit-test the breakers against recorded Bonsai failure patterns first.
3. **StoneSage job routes and thin MCP wrappers** (`local_loop_submit / _status / _detail`, lease and autopilot tools). No state
   in the MCP process; a crashed Claude Code session must never orphan a job or lease.
4. **`/autopilot` toggle** and `merge_mode` (`review` default, `auto` merges when green), `approver_id` on every grant and merge.
5. **First real job:** a small task that already has tests. Then measure tokens on 5-10 tasks against Claude Code alone; go/no-go
   at frontier tokens per green task <= 30 % of baseline at equal pass rate.
6. **Tryout picker** (Phase 9E) once the lease loop is trusted.
7. **CLI calls StoneSage's API** instead of duplicating `harness/core` logic (Division 3 dependency).

## Later: the garden (nothing scheduled; Phase 4 is built, so it is unblocked)
Grounded senses first (real events, not prompts from other agents); limits you can measure (the Phase 1 evals as a mirror);
a walled sandbox with a read-only house view, no HA writes or shell, hourly token budget, runs only when the idle gate is
open; curated memory (dual-gate review before anything reaches long-term memory or training data); desires as a browsable
wish-list queue. Assembly Hall, personas and agent DNA get reused; reproduction comes last.

## Rules for this division
- Frontier models write contracts, not code; a deterministic oracle judges, never an LLM (small models grade too leniently).
- Tests are the oracle: the model may never touch `protected_paths`.
- StoneSage's backend is the one server; every other surface is a thin client (John, 2026-09-27).
- The fork is pinned to an exact release tag and rebuilt only on purpose; Bonsai stays under `/opt/models/prism/`.
- Never re-enable shelved systems, and never start the garden without a written scope from John.

## Done when
A green loop job lands a PR unattended at under 30 % of the frontier tokens, every breaker is unit-tested, and a stopped Claude
Code session leaves no orphaned lease or job.
