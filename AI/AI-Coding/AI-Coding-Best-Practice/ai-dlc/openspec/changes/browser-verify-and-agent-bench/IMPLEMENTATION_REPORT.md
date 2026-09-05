# Implementation Report — browser-verify and agent-bench roles

Branch: `ai-dlc/browser-verify-and-agent-bench-v0.25.0`
Date: 2026-09-06

## What changed

- **`bin/plan.py`** — additions only (526 insertions, 0 deletions across
  the two concurrently-delegated sub-tasks; no collision, verified by
  `ast.parse` + full pytest run before and after):
  - `PLAYWRIGHT_MCP_ROOT`, `PLAYWRIGHT_MCP_PATHS`, `AGENT_BENCH_ROOT`,
    `BENCH_RUNS_DIR`, `BENCH_HISTORY_DIR` constants.
  - `browser_verify_tree_digest()` / `browser_verify_pin_state()` and
    `agent_bench_tree_digest()` / `agent_bench_pin_state()` — structurally
    identical to `understand_anything_pin_state()`.
  - `run_browser_verify_session()` / `run_agent_bench_session()` —
    structurally identical to `run_codegraph_session()`; the latter takes
    no `change` parameter, matching the spec's "standalone diagnostic"
    requirement.
  - `cmd_browser_verify()` / `cmd_bench()` — mirror `cmd_codegraph_brief`'s
    applicability → pin → dispatch → record shape.
  - `browser-verify` and `bench` subparsers wired into
    `_build_subparsers()`/`main()`; `bench` deliberately has no
    `--change`/`--repo`.
- **`scripts/install-browser-verify.sh`** (new) — local npm install of
  `@playwright/mcp` + `playwright install chromium` into
  `/opt/playwright-mcp`, writes `.aidlc-pin.json`.
- **`scripts/install-agent-bench.sh`** (new) — isolated venv + `pip
  install harbor` into `/opt/agent-bench`, writes `.aidlc-pin.json`.
- **`supervisor/skills/workspace/browser-verify/SKILL.md`** and
  **`.../agent-bench/SKILL.md`** (new) — thin conduits, no restated
  discipline.
- **`tests/test_browser_verify.py`** (8 tests) and
  **`tests/test_agent_bench.py`** (8 tests) — pin-state branches,
  applicability/unavailable/dispatched cases, INV-40's hard requirement,
  and (agent-bench) an argparse introspection asserting no `--change`.
- **`tests/collapse/no_direct_tool_exec.sh`** (new, written directly, not
  delegated) — an AST-based static gate for INV-38, not the grep-with-
  context sketch in design.md (that approach has real false-positive/
  false-negative exposure: a comment mentioning a permitted function's
  name would wrongly exempt an unrelated line, and a real violation that
  doesn't repeat that name on its own line would wrongly pass). Walks
  `bin/plan.py`/`bin/report.py`, finds every `subprocess.*`/`os.exec*`
  call whose string arguments mention "playwright"/"harbor", and checks
  the call's actual enclosing function against the two permitted
  dispatchers.
- **`tests/collapse/dt1_gates.sh`** — its hard-coded `plan.py` subcommand
  allowlist updated to include `browser-verify` and `bench` (the same
  gate that needed a matching update when `suggest` was added in an
  earlier change).
- **Two version placeholders corrected** — both delegated sub-tasks had
  no network access and guessed pinned versions (`@playwright/mcp@1.0.0`,
  `harbor==0.1.0`). Checked the real current releases (`npm view
  @playwright/mcp version`, `pip index versions harbor`) and corrected
  both scripts to `0.0.80` and `0.22.0`.

## A real bug found and fixed by the live end-to-end test (not by review)

Both `cmd_browser_verify` and `cmd_bench`'s prompts originally said "Read
`supervisor/skills/workspace/<name>/SKILL.md` in this repo and follow
it." This is wrong: the dispatch's `--cwd` is the *target* repo (or, for
`bench`, a scratch dir) — the workspace skill lives beside `bin/plan.py`,
not there. The relative path resolves to nothing.

Diff review did not catch this (it looks like reasonable prose, and it
follows the letter of `openspec-author`'s "point at your instructions,
don't restate them" convention). **Running a real dispatch caught it**:
the browser-verify role's evidence frames show it attempting exactly that
non-existent path. The established fix already exists in this codebase —
`cmd_codegraph_brief` reads `understand-diff/SKILL.md`'s content directly
in Python and embeds it verbatim in the prompt, rather than telling the
role to fetch it by path. Applied the identical fix to both new commands
(`Path(__file__).resolve().parent.parent / "supervisor/skills/workspace/
<name>/SKILL.md"`, read and inlined between `----- BEGIN/END SKILL.md
-----` markers). Re-ran the full suite (147 passed) and re-dispatched —
see below.

## Live end-to-end verification (real installs, real dispatches, real
   evidence-frame inspection — not self-reports)

### browser-verify — full pass

1. `scripts/install-browser-verify.sh` run for real: downloaded
   `@playwright/mcp@0.0.80` (local npm install) and Chromium (114.3 MiB).
   `browser_verify_pin_state()` returns `ok: true` against the live
   install.
2. Dispatched `plan.py browser-verify --change bvtest --repo
   <scratch-repo> --pages index.html` against an isolated one-page
   scratch repo. First attempt was killed by my own overly-tight outer
   `timeout` wrapper mid-dispatch (my error, not a product bug) — retried
   without an external timeout, using the command's own `--timeout 300`
   (360s internal cap). Completed in 347.6s: `round_complete: true`,
   `browser_verify_state: "passed"`.
3. **Verified from the raw evidence frames, not the role's own report**:
   the role wrote its own MCP JSON-RPC client (`/tmp/mcp-driver.js`) that
   spawns the real `@playwright/mcp/cli.js` via `child_process.spawn`,
   performs a proper `initialize` → `notifications/initialized` →
   `tools/list` → `tools/call` handshake, and calls the genuine tool
   names `browser_navigate`, `browser_snapshot`,
   `browser_network_requests`, `browser_evaluate` against a real headless
   Chromium instance navigating a local HTTP server. The accessibility
   snapshot returned is in Playwright's real YAML-ish format
   (`- heading "hello from browser-verify e2e" [level=1] [ref=e2]`).
   `browser-verify/report.md`, `state.json.browser_verify`, and
   `events.jsonl`'s `BROWSER_VERIFY_PASSED` entry all match. This is
   exactly the acceptance bar the PRD set (genuine tool invocation, not
   an improvised curl/requests/html.parser substitute) and it is met.

### agent-bench — mechanism proven correct; run itself timed out

1. `scripts/install-agent-bench.sh` run for real: created the venv,
   `pip install`ed `harbor==0.22.0` (pulling ~90 transitive packages
   including litellm/openai/boto3/fastapi, ~300 MB). `docker ps` confirms
   Docker is available on this host (Harbor's tasks run in containers).
   `agent_bench_pin_state()` returns `ok: true` against the live install.
2. Checked the real installed CLI (`harbor run --help`) before
   dispatching: the top-level flags visible in the (long, truncated)
   help output did not obviously match the `--dataset`/`--agent`/
   `--model`/`--n-concurrent` shape `SKILL.md` assumes (Harbor's config
   surface is large; a `--config <JobConfig>` path is also documented).
   Deliberately did **not** pre-fix the SKILL.md for this — dispatched
   the real role as-is to see whether it discovers and adapts to the
   real CLI on its own, which is the actual point of routing this
   through an intelligent role rather than a fixed script.
3. Dispatched `plan.py bench --n-concurrent 1 --timeout 300`. Over
   360.1s the role made exactly three tool calls: checked the `harbor`
   entry point exists, read the entry-point script, then ran `cd
   <scratch-dir> && harbor run --dataset terminal-bench@2.0 --agent
   claude-code --n-concurrent 1` — this command **never returned** before
   the internal timeout killed the dispatch. It did not error quickly
   (which a rejected/unknown-flag CLI usage error would), consistent
   with the flags being accepted and Harbor genuinely starting a real
   evaluation (dataset resolution, container build, task execution) —
   plausible given Docker was confirmed present and a real
   terminal-bench round is expected to take substantially longer than a
   few minutes even at `n-concurrent 1`. No Harbor-spawned containers
   were left running afterward (`docker ps -a` showed only pre-existing,
   unrelated infrastructure).
4. **The mechanism behaved exactly as specified under this genuine
   timeout**: `plan.py bench` returned `round_complete: false,
   agent_bench_state: "incomplete"`, and — critically — wrote **no**
   record under `/var/lib/aidlc/bench-history/` (confirmed: the
   directory did not even exist afterward). INV-40's hard requirement
   ("a record missing the pinned version or tree_sha256 must not be
   written as complete") held under a real timeout, not just the stubbed
   `test_agent_bench.py` fixture that exercises the same code path
   synthetically.

**Conclusion on agent-bench**: the pin/dispatch/no-fabrication mechanism
is proven correct end-to-end. Whether the role would have gone on to
successfully adapt to Harbor's real CLI (or correctly stopped and
reported a mismatch) is **not settled** by this run — the timeout was hit
first. This is a test-harness limitation (my own conservative `--timeout
300` for bounding how long I'd wait), not a finding about the product
code: a real invocation should use the subcommand's actual default
(`--timeout 1800`) or larger, since a genuine Harbor evaluation round is
a many-minutes-to-hours operation. Recorded here rather than chased
further, per instruction not to wait indefinitely on a real external
tool's own timescale.

## Test suite results

- `pytest -q tests/test_browser_verify.py tests/test_agent_bench.py`: 16
  passed.
- `pytest -q` (full suite): 147 passed, both before and after the
  SKILL.md-path bug fix.
- `bash tests/collapse/dt1_gates.sh`: pass (SKILL, exit 0) after the
  subcommand-allowlist update.
- `bash tests/collapse/no_direct_tool_exec.sh`: pass against the real
  `bin/plan.py`; independently verified to actually fail (correct
  file/line/function named) against a scratch copy with a deliberately
  injected violation.
- `bash -n` on both new install scripts: clean.

## Not completed / left for a human

- Whether the agent-bench role can successfully discover and adapt to
  Harbor's real CLI surface — undetermined (timed out before reaching a
  verdict either way). A follow-up run with `--timeout 1800`+ (or
  Harbor's own smallest single-task dataset, if one exists) would settle
  it; not attempted here to avoid an open-ended wait.
- `SKILL.md`'s `agent-bench` "What to run" section still shows the
  `--dataset`/`--agent`/`--model`/`--n-concurrent` example command,
  unverified against Harbor's real flag surface. Left as-is per this
  change's scope (the PRD's non-goals explicitly exclude designing
  Harbor's exact invocation contract in this pass) — worth revisiting
  once a real run actually completes and confirms or corrects it.
