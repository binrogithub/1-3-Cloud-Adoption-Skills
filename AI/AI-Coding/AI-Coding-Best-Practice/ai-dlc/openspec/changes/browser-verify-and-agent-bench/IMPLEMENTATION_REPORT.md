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

### agent-bench — the CLI worked as designed; real infra ran; a credential gap stopped it (corrected finding — see note below)

1. `scripts/install-agent-bench.sh` run for real: created the venv,
   `pip install`ed `harbor==0.22.0` (pulling ~90 transitive packages
   including litellm/openai/boto3/fastapi, ~300 MB). `docker ps` confirms
   Docker is available on this host (Harbor's tasks run in containers).
   `agent_bench_pin_state()` returns `ok: true` against the live install.
2. Checked the real installed CLI (`harbor run --help`) before
   dispatching: the top-level flags visible in the (long, truncated)
   help output did not obviously match the `--dataset`/`--agent`/
   `--model`/`--n-concurrent` shape `SKILL.md` assumes. This turned out
   to be a **false alarm from a truncated `--help` read on my part** —
   see the correction below.
3. Dispatched `plan.py bench --n-concurrent 1 --timeout 300`. The
   `plan.py`-level dispatch (`run_agent_bench_session`'s
   `subprocess.run(..., timeout=360)`) hit that 360s ceiling and
   `plan.py bench` correctly reported `round_complete: false,
   agent_bench_state: "incomplete"`, writing **no** record to
   `/var/lib/aidlc/bench-history/` — this part of my original report was
   accurate as far as it went, and it does correctly prove INV-40's hard
   requirement ("a record missing the pinned version or tree_sha256 must
   not be written as complete") holds under a real timeout, not just the
   stubbed `test_agent_bench.py` fixture.
4. **Correction, found on a closer pass through the role's own scratch
   directory after the fact (not checked in the original verification —
   I had only inspected `bench-history` and `plan.py`'s own top-level
   judgment, not the role's own working-directory output)**: the
   underlying Harbor job kept running past the point `subprocess.run`
   killed the parent `jiuwenswarm chat` process (Harbor's job execution
   is not tied to that process's stdio — `result.json`'s `updated_at`
   is ~12 minutes after `plan.py`'s own `ended_at`), and the role itself
   wrote a complete `agent-bench/result.md` into its scratch dir before
   being cut off. That file shows:
   - The exact flags `SKILL.md` specifies (`--dataset terminal-bench@2.0
     --agent claude-code --n-concurrent 1`) **were accepted by the real
     CLI and worked** — my `--help` read was truncated before the
     relevant flag group; there was no CLI mismatch to adapt to.
   - Harbor genuinely resolved the 89-task `terminal-bench@2.0` dataset
     and started real Docker-based trials (confirmed independently
     against Harbor's own `result.json` in its job directory:
     `n_total_trials: 89`, 2 errored, 1 cancelled, 86 pending — matches
     the role's report exactly).
   - Both completed trials failed identically with
     `AgentAuthenticationError` ("Not logged in") — the `claude-code`
     agent inside Harbor's task containers has no Anthropic credentials
     (`ANTHROPIC_API_KEY`/logged-in session), so no task-solving
     capability was actually measured. This is an **environment/
     credential-wiring gap**, not a role or dispatch defect.
   - The role correctly followed the SKILL.md's stop protocol: it did
     not fabricate a result, transcribed the figures directly from
     Harbor's own `result.json`/`job.log`, and made the engineering call
     to stop after the second identical auth failure rather than
     burning through the remaining 86 tasks toward a predetermined 0/89
     — an appropriate outcome, not a shortcut.
   - One operational side-effect found during this correction pass: the
     job's default `--jobs-dir` landed at
     `/opt/understand-anything/jobs/` (an unrelated pinned tree, not
     `AGENT_BENCH_ROOT` or the scratch dir) — harmless in this case
     because that tree is git-tracked and `understand_anything_pin_state()`
     digests only `git ls-files`-tracked content (confirmed: the pin
     still reported `ok: true` before and after removing the stray,
     untracked `jobs/` directory), but worth pinning down explicitly in
     a follow-up (Harbor's `--jobs-dir` should be pointed at the scratch
     run directory). One stopped/exited Docker container from the
     cancelled trial and the stray job directory were both found and
     removed during cleanup.

**Corrected conclusion on agent-bench**: the pin/dispatch mechanism and
the no-fabrication guarantee are both proven correct end-to-end, *and*
the role successfully drove a real Harbor evaluation round against real
Docker infrastructure with zero CLI-adaptation problems. The blocker is
operational, not architectural: Harbor's task containers need Anthropic
credentials wired in before `agent-bench` can produce a real capability
score. My first pass at this report understated the outcome — I had
verified `plan.py`'s own top-level judgment and the signed-record
location, but not the role's own scratch-directory output, and drew a
"CLI mismatch, undetermined" conclusion that the fuller evidence does
not support. Recording this correction plainly rather than quietly
editing the earlier claim away.

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

- **`agent-bench` cannot yet produce a real capability score** — Harbor's
  task containers need Anthropic credentials (`ANTHROPIC_API_KEY` or an
  equivalent logged-in `claude-code` session) wired in before a run can
  measure anything beyond `AgentAuthenticationError`. This is an
  operator/provisioning task (likely belongs in
  `scripts/install-agent-bench.sh` or the pinned Harbor config, injecting
  the same credential the rest of this host's `claude-*` launchers
  already use), not a code change to `cmd_bench`/`run_agent_bench_session`
  — out of scope for this PRD's non-goals, which explicitly exclude
  designing Harbor's exact invocation/credential contract. Recorded here
  as the concrete next step for whoever picks this up.
- `SKILL.md`'s `agent-bench` "What to run" section's example command
  (`--dataset`/`--agent`/`--model`/`--n-concurrent`) is now **confirmed
  correct** against the real installed CLI (see the corrected finding
  above) — no change needed there.
- Harbor's default `--jobs-dir` was observed landing outside both
  `AGENT_BENCH_ROOT` and the scratch run directory (in this run, inside
  an unrelated pinned tree, harmlessly since that tree only digests
  git-tracked content) — a follow-up should have `agent-bench/SKILL.md`
  or `cmd_bench`'s prompt explicitly pass `--jobs-dir` pointed at the
  scratch run directory, so job artifacts always land somewhere expected
  and get cleaned up with it.
