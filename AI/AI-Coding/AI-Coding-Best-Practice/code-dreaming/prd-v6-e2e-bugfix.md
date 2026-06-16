# PRD v6: E2E Bug Fixes — Stale Install Sync & PYTHONPATH Import Failure

Date: 2026-06-16
Source: E2E automated pipeline test (12-step full-chain run)

## Findings

| ID | Severity | Summary | Root Cause |
|----|----------|---------|------------|
| F1 | High | Installed skill bundle is stale — `dream_agent_report.py` 254 lines vs source 727 lines, missing all code-index enhanced sections (Project Overview, Key Symbols, Coupling, Recent Activity) | `build_skill.py` + `install-skill.sh` work correctly but nothing triggers a rebuild after source changes. The installed copy at `~/.claude/skills/code-dreaming/` is a one-time snapshot. |
| F2 | High | `ModuleNotFoundError: No module named 'scripts'` when `dream_agent_report.py` is invoked from outside the skill directory on a fresh repo (auto-index path) | `dream_sources.py:339` does a lazy `from scripts.git_adapter import read_git_history` with no `ModuleNotFoundError` fallback. All other scripts have the try/except fallback pattern; this one was missed. |

## Changes

### C1: Add `ModuleNotFoundError` fallback for `dream_sources.py` lazy import (F2)

**File:** `scripts/dream_sources.py` line 339
**What:** Wrap the lazy `from scripts.git_adapter import read_git_history` in a try/except that falls back to `from git_adapter import read_git_history`, matching the pattern used by every other script in the project.
**Why:** When `dream_agent_report.py` is invoked from outside the skill directory (e.g. `python3 /path/to/skill/scripts/dream_agent_report.py --repo-root /some/repo`), `sys.path` does not include the skill root, so `from scripts.git_adapter` fails. This is the exact scenario that triggers auto-index on a fresh repo. The auto-index feature in `dream_agent_report.py` already has the fallback pattern for its own imports; the downstream call into `dream_sources.load_trajectory()` breaks at the git sentinel branch.
**How:**
```python
# Before (line 339):
from scripts.git_adapter import read_git_history  # local import to avoid cycles

# After:
try:
    from scripts.git_adapter import read_git_history
except ModuleNotFoundError:
    from git_adapter import read_git_history
```
**Acceptance:**
- `python3 /path/to/skill/scripts/dream_agent_report.py --repo-root /tmp/fresh-repo` succeeds without PYTHONPATH
- Auto-index on first run works when invoked from any cwd
- Existing tests pass (the fallback is only hit in direct-script-execution mode)
- The try/except matches the identical pattern in `dream_agent_report.py`, `distill.py`, `dream_llm.py`, `scan_to_dream.py`, `reset_memory.py`, `dream.py`

### C2: Add `sys.path` self-injection to `dream_agent_report.py` (F2 defense-in-depth)

**File:** `scripts/dream_agent_report.py` — near top of file, after imports
**What:** Before any `from scripts.*` import attempt, ensure the script's own parent directory is on `sys.path`. This guarantees that both the primary `from scripts.*` import AND any downstream lazy imports (like the one in `dream_sources.py`) resolve correctly regardless of cwd.
**Why:** The try/except fallback in C1 fixes `dream_sources.py` in isolation, but the same class of bug could recur in any future lazy import added to any script. A single `sys.path` injection at the entry point eliminates the entire class. This is the same pattern used by `conftest.py` in the test suite.
**How:**
```python
# At top of dream_agent_report.py, before the try/except import block:
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
```
This ensures that when `dream_agent_report.py` is invoked as `python3 /abs/path/to/scripts/dream_agent_report.py`, the skill root (`/abs/path/to/`) is on `sys.path`, so `from scripts.*` always works for this process and all downstream calls.
**Acceptance:**
- `python3 /path/to/skill/scripts/dream_agent_report.py --repo-root /tmp/fresh-repo` works without PYTHONPATH
- `python3 scripts/dream_agent_report.py --repo-root .` still works from within the skill directory (idempotent insert)
- No change to test behavior (tests already add the root via conftest.py)

### C3: Add staleness check to `install-skill.sh` (F1)

**File:** `bin/install-skill.sh`
**What:** After the existing `python3 "$ROOT/scripts/build_skill.py" --output "$BUILD_DIR"` line, compare the built bundle against the installed destination. If the installed version differs, print a warning. Add `--check` flag that exits non-zero if stale (for CI).
**Why:** The current flow is: developer edits source → forgets to re-run `install-skill.sh` → installed skill is silently stale → runtime features are missing with no error. The build+install is correct but never triggered automatically.
**How:**
```bash
# After the build line, add:
if [ "$TARGET" = "claude" ] || [ "$TARGET" = "both" ]; then
  INSTALLED="$HOME/.claude/skills/code-dreaming"
  if [ -d "$INSTALLED" ]; then
    if ! diff -rq "$BUILD_DIR/scripts" "$INSTALLED/scripts" --exclude='__pycache__' >/dev/null 2>&1; then
      echo "warning: installed skill at $INSTALLED differs from source — run: bin/install-skill.sh" >&2
      if [ "${MCE_CHECK_STALE:-0}" = "1" ]; then
        exit 1
      fi
    fi
  fi
fi
```
Add `--check` flag parsing: when set, `MCE_CHECK_STALE=1` and the script exits 1 if stale (non-destructive, no install performed).
**Acceptance:**
- After source changes, running `bin/install-skill.sh --check` prints warning and exits 1
- After `bin/install-skill.sh` (full install), `--check` exits 0
- Normal `bin/install-skill.sh` still works unchanged (warning is informational only)

### C4: Add `pre-invocation sync` note to SKILL.md (F1 documentation)

**File:** `SKILL.md` — Default `/code-dreaming` behavior section
**What:** Add a note that the skill entry script (`dream_agent_report.py`) auto-injects its project root onto `sys.path`, so it works from any cwd. Add a note that after source changes, `bin/install-skill.sh` must be re-run to update the installed bundle.
**Why:** Users and agents invoking the skill from outside its directory need to know the import resolution is handled. Developers editing source need to know to re-install.
**How:** Add two lines to the "Default `/code-dreaming` behavior" section:
```
The report script auto-injects its skill root onto `sys.path`, so it works
when invoked by absolute path from any working directory.

After editing source files under this skill, re-run `bin/install-skill.sh`
to sync the installed bundle at `$HOME/.claude/skills/code-dreaming/`.
```
**Acceptance:**
- SKILL.md documents the sys.path behavior
- SKILL.md documents the install-sync requirement

## Priority

C1 and C2 fix the runtime breakage (F2) — do first.
C3 and C4 prevent future staleness (F1) — do second.

## Test Plan

1. **C1+C2 verification:** Create a fresh temp repo with source files. Run `python3 /abs/path/to/skill/scripts/dream_agent_report.py --repo-root /tmp/fresh-repo` without PYTHONPATH. Assert: no `ModuleNotFoundError`, report contains Project Overview section.
2. **C3 verification:** Edit a source file. Run `bin/install-skill.sh --check`. Assert: exit 1, warning printed. Run `bin/install-skill.sh`. Run `bin/install-skill.sh --check`. Assert: exit 0.
3. **Regression:** `python3 -m pytest tests/ -v` — all 251 tests still pass.
