# E8: Nightly Pipeline

**Depends on:** E1, E2, E5  
**Blocks:** E9  
**Parallel with:** E6, E7  
**Estimate:** 0.5 day  
**PRD sections:** 6.2, 6.3

## Goal

Create an automated nightly pipeline that runs incremental indexing, git history
sync, and dream report generation. Includes scheduling gates to avoid
unnecessary runs (adapted from MiMo Code's auto-dream pattern).

## Stories

### S8.1: should_run.py scheduling gate

Create `scripts/should_run.py`:

```python
def should_run(repo_root: Path, db_path: Path, *, 
               min_interval_hours: int = 24,
               min_project_age_days: int = 1) -> tuple[bool, str]:
    """Determine if a nightly dream run is warranted."""
```

Checks (any True triggers a run):
1. **No DB exists:** always run (first time)
2. **Interval elapsed:** `last_indexed` in `project_metadata` older than N hours
3. **Git changes:** new commits since `last_indexed`
4. **File changes:** any file with `mtime_ns > last_indexed`

Skip conditions:
1. **Too young:** project created < N days ago (from oldest commit)
2. **Recently ran:** last run < min_interval_hours ago AND no new commits
3. **No source files:** directory has no parseable files

Return `(should_run: bool, reason: str)`.

**Acceptance:**
- Fresh project: `(True, "no existing index")`
- Just ran 1 hour ago, no changes: `(False, "last run 1h ago, no changes")`
- Ran yesterday, 3 new commits: `(True, "3 new commits since last run")`
- Empty directory: `(False, "no source files")`

### S8.2: dream-nightly.sh pipeline script

Create `bin/dream-nightly.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${1:-.}"
DB_PATH="${REPO_ROOT}/.maas-dreaming/code-index.db"

# Gate: should we run?
python3 scripts/should_run.py "$REPO_ROOT" "$DB_PATH" || exit 0

# Step 1: Incremental code index
python3 scripts/code_index.py --repo-root "$REPO_ROOT" --db "$DB_PATH"

# Step 2: Git history sync
python3 scripts/git_adapter.py --repo-root "$REPO_ROOT" --db "$DB_PATH"

# Step 3: Dream report
python3 scripts/dream_agent_report.py --repo-root "$REPO_ROOT" --db "$DB_PATH"

# Step 4: Export artifact (optional, for team sharing)
if [ "${EXPORT_ARTIFACT:-false}" = "true" ]; then
    python3 -m mce artifact export --db "$DB_PATH"
fi
```

- Executable with `chmod +x`
- Each step prints progress
- Gate check prevents unnecessary runs
- Exit 0 on skip (not error)

**Acceptance:**
- `./bin/dream-nightly.sh .` runs the full pipeline
- Skip when no changes: exits 0 with "no changes" message
- Each step's output visible
- Failure in one step stops the pipeline (set -e)

### S8.3: Cron integration helper

Add to `scripts/should_run.py`:

```python
def print_cron_suggestion(repo_root: Path):
    """Print a crontab entry for nightly runs."""
    abs_path = repo_root.resolve()
    print(f"# maas-dreaming nightly pipeline")
    print(f"0 3 * * * cd {abs_path} && ./bin/dream-nightly.sh .")
```

Also add `--cron-setup` flag that prints the crontab entry and usage instructions.

**Acceptance:**
- `python3 scripts/should_run.py --cron-setup .` prints a valid crontab entry
- Path in crontab is absolute
- Instructions mention `crontab -e`

### S8.4: Incremental dream report delta

When running in nightly mode, the dream report should include a "Changes Since
Last Run" section:

```markdown
## Changes Since Last Run (2026-06-14)

- 3 new commits (abc123, def456, ghi789)
- 2 files added: `epics/E7-team-sharing.md`, `epics/E8-nightly-pipeline.md`
- 5 files modified: `scripts/dream.py` (+42 -18), ...
- 12 new symbols, 3 removed symbols
```

- Compare current DB state with `last_indexed` timestamp
- Show: new commits, added/modified/deleted files, symbol delta

**Acceptance:**
- Delta section appears when there are changes since last run
- Delta section omitted on first run (everything is "new")
- File change counts match reality

## Definition of Done

- [ ] `should_run.py` correctly gates pipeline execution
- [ ] `dream-nightly.sh` runs the full pipeline end-to-end
- [ ] Cron setup helper prints a valid crontab entry
- [ ] Dream report includes delta section on incremental runs
- [ ] Pipeline skips gracefully when no changes detected
- [ ] Tests cover: should_run logic, delta calculation
