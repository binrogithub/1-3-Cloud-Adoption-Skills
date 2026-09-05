# Tasks — browser-verify and agent-bench roles

## 1. Shared: `write_pin` helper

- Factor a shared pin-writing helper (shell function or small Python
  script reused by all three `install-*.sh` scripts, existing ones
  included if they don't already share one) computing a tree-wide sha256
  digest and writing `.aidlc-pin.json` in the shape
  `understand_anything_pin_state()` expects.

## 2. G1 — `browser-verify`

- `scripts/install-browser-verify.sh`: local (not global) npm install of
  `@playwright/mcp` into `AI_DLC_PLAYWRIGHT_MCP_ROOT` (default
  `/opt/playwright-mcp`), `playwright install chromium`, write pin.
- `browser_verify_pin_state()` in `bin/plan.py`, structurally identical
  to `understand_anything_pin_state()`.
- `supervisor/skills/workspace/browser-verify/SKILL.md` per design.md —
  three sections, no restated discipline, no schema/tool assumptions
  beyond what the dispatch prompt gives it.
- `run_browser_verify_session()` in `bin/plan.py`, mirroring
  `run_codegraph_session()`.
- `plan.py browser-verify --change <id> --repo <repo> --pages <p1,p2,...>`
  subcommand: applicability check → pin check → dispatch → record in
  `state.json`/`events.jsonl`.

## 3. G2 — `agent-bench`

- `scripts/install-agent-bench.sh`: isolated venv under
  `AI_DLC_AGENT_BENCH_ROOT` (default `/opt/agent-bench`), `pip install
  harbor`, write pin.
- `agent_bench_pin_state()`, additionally checking the venv's `harbor`
  entry point is executable.
- `supervisor/skills/workspace/agent-bench/SKILL.md` per design.md.
- `run_agent_bench_session()`, mirroring `run_codegraph_session()` but
  with no `change` argument.
- `plan.py bench [--dataset terminal-bench@2.0] [--model <name>]
  [--n-concurrent N]` subcommand: pin check → dispatch → write signed
  result (with pinned Harbor version + pin sha256, INV-40) to
  `/var/lib/aidlc/bench-history/<timestamp>.json`. No `--change` flag
  exists on this subcommand.

## 4. Static enforcement (INV-38)

- New `tests/collapse/no_direct_tool_exec.sh` per design.md: fails if any
  source line outside the two dispatcher functions and two pin-state
  functions names a playwright/harbor executable in a `subprocess`/
  `os.exec`/`Popen` call.

## 5. Tests

- `browser_verify_pin_state`/`agent_bench_pin_state`: four branches each
  (healthy, missing directory, missing pin file, digest mismatch) —
  assert the same `{ok, why, remedy, exit_code}` shape
  `understand_anything_pin_state` uses.
- `plan.py browser-verify`: fixture where none of `--pages` exist →
  `not_applicable`; fixture where pin is unavailable → `unavailable`,
  exit 0; (stubbed dispatch) fixture asserting `state.json`/`events.jsonl`
  get the right entries on a judged-complete dispatch.
- `plan.py bench`: fixture where pin is unavailable → `unavailable`, exit
  0; (stubbed dispatch) fixture asserting the written result file under
  `/var/lib/aidlc/bench-history/` includes the pinned tool version and
  sha256; assert the subcommand has no `--change`/`--repo` requirement
  tying it to a task lifecycle.
- `no_direct_tool_exec.sh`: assert it currently passes against the
  as-implemented `bin/plan.py`; assert it would fail against a
  deliberately-introduced direct `subprocess.run(["npx", "playwright-mcp"
  , ...])` outside the dispatcher (a fixture copy of the file with the
  violation injected, not a change to the real file).

## 6. End-to-end (real environment, record actual results in
   IMPLEMENTATION_REPORT.md)

- Run `scripts/install-browser-verify.sh`; confirm
  `browser_verify_pin_state().ok == true`. Dispatch `plan.py
  browser-verify` against a real multi-page project's pages; inspect the
  evidence frames' `commands_seen` for genuine Playwright MCP tool
  invocations (navigate/snapshot), not an improvised curl/requests
  substitute — same acceptance bar used for `openspec-author`.
- Run `scripts/install-agent-bench.sh`; confirm
  `agent_bench_pin_state().ok == true`. Run `plan.py bench
  --n-concurrent 1` against a minimal task subset; confirm a signed
  result lands under `/var/lib/aidlc/bench-history/` with the pinned
  Harbor version.

## 7. CHECK → REPORT → MERGE_GATE

- `plan.py validate` for the signed spec verdict.
- `report.py deliver` for the delivery report.
- Present the diff and validator conclusion at MERGE_GATE for a human;
  no merge without an approved, rationale-carrying answer.
