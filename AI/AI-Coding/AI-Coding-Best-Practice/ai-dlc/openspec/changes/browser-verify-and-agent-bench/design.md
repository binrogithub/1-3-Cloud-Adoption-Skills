# Design — browser-verify and agent-bench roles

Both roles are built from the same six-part shape `codegraph` already
establishes; nothing new is invented, only instantiated twice.

## Shared shape (per role)

| Part | codegraph precedent | browser-verify | agent-bench |
|---|---|---|---|
| Root constant | `UNDERSTAND_ANYTHING_ROOT` (env `AI_DLC_UNDERSTAND_ANYTHING_ROOT`, default `/opt/understand-anything`) | `PLAYWRIGHT_MCP_ROOT` (env `AI_DLC_PLAYWRIGHT_MCP_ROOT`, default `/opt/playwright-mcp`) | `AGENT_BENCH_ROOT` (env `AI_DLC_AGENT_BENCH_ROOT`, default `/opt/agent-bench`) |
| Install script | `scripts/install-understand-anything.sh` | `scripts/install-browser-verify.sh` | `scripts/install-agent-bench.sh` |
| Pin file | `.aidlc-pin.json` beside the tree | same | same |
| Pin-state fn | `understand_anything_pin_state()` | `browser_verify_pin_state()` | `agent_bench_pin_state()` |
| Workspace skill | `supervisor/skills/workspace/codegraph/SKILL.md` | `supervisor/skills/workspace/browser-verify/SKILL.md` | `supervisor/skills/workspace/agent-bench/SKILL.md` |
| Session dispatcher | `run_codegraph_session()` | `run_browser_verify_session()` | `run_agent_bench_session()` |
| plan.py subcommand | `codegraph build`/`brief` | `browser-verify` | `bench` |

## Install scripts (pure glue, no upstream modification)

`scripts/install-browser-verify.sh`:
```bash
mkdir -p "$ROOT"
npm install --prefix "$ROOT" @playwright/mcp@"$PINNED_VERSION"
"$ROOT/node_modules/.bin/playwright" install chromium
write_pin "$ROOT" tag="$PINNED_VERSION"   # computes tree_sha256, writes .aidlc-pin.json
```

`scripts/install-agent-bench.sh`:
```bash
python3 -m venv "$ROOT/venv"
"$ROOT/venv/bin/pip" install "harbor==$PINNED_VERSION"
write_pin "$ROOT" tag="$PINNED_VERSION"
```

`write_pin` is a small shared shell function (new, factored out of the
existing per-script pin-writing logic in `install-understand-anything.sh`
/ `install-opendesign.sh` if they duplicate it, or written once and
reused by all three going forward) — computes a tree-wide sha256 digest
and writes `{tag, sha, tree_sha256, sparse_paths, installed_at,
size_bytes}`, the exact shape `understand_anything_pin_state()` already
expects.

## Pin-state functions

Both are structurally identical to `understand_anything_pin_state()`:
directory exists → pin file exists → pin carries `tag` + `tree_sha256` →
pinned paths present → measured digest equals pinned digest. Each
failure returns `{"ok": false, "why": ..., "remedy": ..., "exit_code":
...}`; nothing raises.

```python
def browser_verify_pin_state(root: Path | None = None) -> dict:
    root = Path(root) if root else PLAYWRIGHT_MCP_ROOT
    ...  # identical shape to understand_anything_pin_state

def agent_bench_pin_state(root: Path | None = None) -> dict:
    root = Path(root) if root else AGENT_BENCH_ROOT
    ...  # additionally checks root/"venv/bin/harbor" is executable
```

## Workspace skills

`browser-verify/SKILL.md` — three sections, no restated discipline
(mirrors `openspec-author`'s shape exactly):
1. What you are — verifying a list of pages the dispatch prompt names.
2. What to run — drive the pinned Playwright MCP server (path from the
   prompt) against each page: navigate, take an accessibility snapshot,
   check the assertions the prompt lists (status, title, selector
   presence). Write `browser-verify/report.md`: one row per page,
   pass/fail, failure reason.
3. If it fails — the existing `CLI_UNAVAILABLE_MARKER` stop protocol,
   pointed at not restated.

`agent-bench/SKILL.md` — three sections:
1. What you are — running one benchmark round of this pipeline itself,
   not modifying any user project.
2. What to run — `<pin_root>/venv/bin/harbor run --dataset <dataset>
   --agent claude-code --model <model> --n-concurrent <n>` (values from
   the dispatch prompt), then read Harbor's own result output and
   summarize into `agent-bench/result.md`: total tasks, pass count,
   per-category failure breakdown, plus a pointer to Harbor's raw output
   path.
3. If it fails — same stop protocol.

## Dispatch functions

Both mirror `run_codegraph_session()` verbatim in structure — only the
session-name prefix and cwd/argument differ:

```python
def run_browser_verify_session(change: str, prompt: str, repo: Path,
                               task_dir: Path, mode: str,
                               timeout: int) -> tuple[dict, list]:
    session_name = f"browser-verify-{change}-{seq}"
    cmd = [CLIENT, "chat", prompt, "--jsonl", "--cwd", str(repo),
           "--mode", mode, "--timeout", str(timeout),
           "--session", session_name]
    ...  # identical evidence-capture + judge_frames() shape

def run_agent_bench_session(prompt: str, repo: Path, task_dir: Path,
                            mode: str, timeout: int) -> tuple[dict, list]:
    session_name = f"agent-bench-{seq}"
    cmd = [CLIENT, "chat", prompt, "--jsonl", "--cwd", str(repo),
           "--mode", mode, "--timeout", str(timeout),
           "--session", session_name]
    ...  # same
```

`agent_bench`'s dispatch does not take a `change` — its `cwd`/`task_dir`
point at a fixed diagnostic location (e.g. a scratch dir under
`/var/lib/aidlc/bench-runs/<timestamp>/`), never a `.ai-dlc/tasks/<id>/`
directory, so it structurally cannot be mistaken for part of any change's
lifecycle.

## plan.py subcommands

```
plan.py browser-verify --change <id> --repo <repo> --pages <p1,p2,...>
```
1. Applicability: none of `--pages` exist in the current working tree →
   `browser_verify_state: "not_applicable"`, exit 0.
2. `browser_verify_pin_state()` not ok → `browser_verify_state:
   "unavailable"`, exit 0 (never blocks the caller).
3. Build the prompt (pages list + assertions), call
   `run_browser_verify_session()`, judge frames, write
   `state.json.browser_verify` + append `BROWSER_VERIFY_PASSED` /
   `BROWSER_VERIFY_FAILED` / `BROWSER_VERIFY_UNAVAILABLE` to
   `events.jsonl`.

```
plan.py bench [--dataset terminal-bench@2.0] [--model <name>]
              [--n-concurrent N]
```
1. `agent_bench_pin_state()` not ok → emit `{"agent_bench_state":
   "unavailable", ...}`, exit 0.
2. Build the prompt, call `run_agent_bench_session()`, judge frames.
3. Write the signed result — including the pinned Harbor version and
   pin sha256 (INV-40) — to `/var/lib/aidlc/bench-history/<started_at
   ISO timestamp>.json`. Print a summary to stdout. No `--change`
   argument exists on this subcommand at all — it is not wired to any
   task-dir or delivery path.

## Static enforcement of "no direct call" (INV-38)

New collapse gate script, e.g. `tests/collapse/no_direct_tool_exec.sh`:
```bash
# Every source line naming a playwright/harbor executable must be inside
# one of the two permitted dispatcher functions.
grep -n 'playwright\|harbor' bin/plan.py bin/report.py \
  | grep -v 'def run_browser_verify_session\|def run_agent_bench_session\|def browser_verify_pin_state\|def agent_bench_pin_state\|PLAYWRIGHT_MCP_ROOT\|AGENT_BENCH_ROOT' \
  | grep -E 'subprocess|os\.exec|Popen' && exit 1
exit 0
```
(Exact grep shape refined at implementation time — the point being
enforced is: outside the two dispatcher functions and the two pin-state
functions, no code path may spawn these executables directly.)
