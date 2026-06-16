# E2: Git History Adapter

**Depends on:** E0  
**Blocks:** E5, E8  
**Parallel with:** E1, E3  
**Estimate:** 1 day  
**PRD sections:** 4.1, 4.2, 4.3

## Goal

Read `git log` and produce two outputs:
1. Populate `commits` + `commit_files` tables in code-index.db
2. Produce `TrajectoryResult` compatible with `dream_sources.py` so the dream
   report can use git history as a fallback when no `.jsonl` sessions exist.

## Stories

### S2.1: Git log parser

Create `scripts/git_adapter.py` with `parse_git_log(repo_root, max_commits, since_date)`:

```python
def parse_git_log(
    repo_root: Path,
    max_commits: int = 200,
    since_date: str | None = None,
) -> list[GitCommit]:
    """Parse git log --numstat into structured commit objects."""
```

- Run: `git -C <repo> log --max-count=N --format='%H|%an|%aI|%s' --numstat [--since=DATE]`
- Parse output into `GitCommit` dataclass: hash, author, date, message, files list
- Each file entry: path, change_type (inferred from numstat), additions, deletions
- Handle edge cases: merge commits (may have no numstat), binary files (- - path)
- Graceful failure: if not a git repo, return empty list (not crash)

**Acceptance:**
- On maas-dreaming repo: returns ~142 commits
- Each commit has hash, author, date, subject, file list
- `--since` filters correctly
- Non-git directory returns empty list

### S2.2: Write commits to code-index.db

Add `write_git_history(conn, commits)` to `git_adapter.py`:

- INSERT OR IGNORE into `commits` table (hash is unique)
- INSERT OR IGNORE into `commit_files` table
- Incremental: only insert commits newer than `max(date)` in existing table

**Acceptance:**
- First run: all commits inserted
- Second run: 0 new inserts (all already exist)
- After new commits: only new ones inserted

### S2.3: File coupling analysis

Add `compute_file_coupling(conn, min_co_commits=3)`:

- Query `commit_files` to find file pairs that change together in >N commits
- Compute Jaccard similarity: `|commits_both| / |commits_either|`
- Store as `file_changes_with` edges in `edges` table (via synthetic symbol IDs
  for files, or direct query results)

**Acceptance:**
- `dream.py` and `dream_signals.py` show coupling if they changed together often
- Coupling score is between 0.0 and 1.0
- Files that never co-changed have no coupling edge

### S2.4: TrajectoryResult adapter for dream_sources.py

Add `read_git_history(repo_root, max_commits) -> TrajectoryResult`:

- Convert each `GitCommit` to an `EvidenceRecord`:
  - `evidence_id = "git-" + short_hash`
  - `timestamp = author_date`
  - `role = "git"`
  - `tool = "commit"`
  - `preview = "subject | N files | +A -D"`
  - `project_match = True`
- Return `TrajectoryResult(adapter="git", ...)`

**Acceptance:**
- Returns `TrajectoryResult` with `adapter="git"`
- Each commit is one `EvidenceRecord`
- Preview is bounded and human-readable

### S2.5: Integrate git fallback into dream_sources.py

Modify `discover_source()` in `dream_sources.py`:

```python
def discover_source(memory_dir, repo_root):
    # ... existing candidates (mimocode.db, .jsonl, .md) ...

    # NEW: git fallback when no other source found
    source = next((p for p in candidates if p.exists()), None)
    if source:
        return source
    # Return a sentinel that load_trajectory() recognizes as "use git"
    return _GIT_SENTINEL if _is_git_repo(repo_root) else None
```

Add to `load_trajectory()`: when source is the git sentinel, call
`read_git_history()`.

Priority order (existing sources unchanged, git added as last fallback):
1. Explicit `--trajectory` path
2. `mimocode.db` / `trajectory.db`
3. `*.jsonl` session transcripts
4. **`git log` (new)**

**Acceptance:**
- Existing `.jsonl` discovery unchanged (no regression)
- On a repo with no `.jsonl`: `load_trajectory()` returns git-based results
- On a non-git directory with no `.jsonl`: returns `no_trajectory=True`

## Definition of Done

- [ ] `git_adapter.py` exists with all functions
- [ ] `test_git_adapter.py` covers: parse, write, coupling, trajectory adapter
- [ ] `dream_sources.py` modified with git fallback
- [ ] Existing `test_dream_sources.py` still passes
- [ ] On a fresh project, `load_trajectory()` returns git history
