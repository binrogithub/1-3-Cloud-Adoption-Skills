# Design — plane git safe.directory + rollback-anchor SKIP state

## G1 — `git_run()` helper (bin/plan.py)

```python
def git_run(args: list[str], repo: Path, cwd=None,
            timeout=None) -> subprocess.CompletedProcess:
    """Like run(["git", "-C", str(repo)] + args), but always scopes a
    per-invocation safe.directory override to exactly this path — never
    written to any config file, never affecting any call outside this one
    subprocess. Exists because plane_root() paths are chowned to a
    different uid (swarm) than the caller's own, which trips git's
    dubious-ownership refusal; this is git's own documented answer to
    that scenario, applied narrowly."""
    return run(["git", "-c", f"safe.directory={repo}", "-C", str(repo)]
               + args, cwd=cwd, timeout=timeout)
```

Placed next to the existing `run()` (line ~343), same file, no new import.

## G2 — `git_status_paths()` routes through it

Current body calls `run(["git", "-C", str(repo), "status", "--porcelain",
"-uall"])`. Change the one line to `git_run(["status", "--porcelain",
"-uall"], repo)`. No signature change — every caller (`boundary_scan`,
`_run_role`'s baseline snapshot) is unaffected and gets the fix for free.

## G3 — `cmd_sweep`'s two direct calls

Lines ~2272 (`ls-files`) and ~2299 (`checkout --`) currently build
`run(["git", "-C", str(root), ...])` directly (`root = plane_root(repo)`
at line 2257). Both become `git_run([...], root)`.

## G4 — boundary-failure classification

`_run_role`'s baseline snapshot (around line 2681) today does:

```python
pre_paths = git_status_paths(tree)
if pre_paths is None:
    return {"artifact": role, "change": change,
            "error": "git status failed (baseline snapshot)",
            "boundary": "unknown"}, EXIT_INCONCLUSIVE
```

`git_status_paths` returning `None` currently conflates two causes: the
target simply isn't a git repo / doesn't exist (a real "don't know"), and
git refusing on ownership grounds (which G1-G3 should eliminate for
plane-owned paths, but the classification should exist regardless of which
cause produces `None`, for future-proofing and for non-plane callers of
the same function). Since `git_status_paths` only returns `None` on
non-zero exit today with no further detail, this task extends it to also
return the captured stderr on failure (a second return value or a small
result object) so `_run_role` can report *why* status failed, not just
that it failed — turning `"boundary": "unknown"` into something a human
reading the report can act on, while keeping `"boundary": "unknown"` as
the umbrella outcome for genuinely indeterminate cases (target doesn't
exist, unreadable).

## G5 — `dt1_gates.sh` rollback-anchor SKIP

Current (lines 85-87):

```bash
git cat-file -e v0.8.0:bin/oracle.py \
  || { echo "FAIL: v0.8.0:bin/oracle.py missing — deletion has no rollback anchor"; exit 1; }
```

New:

```bash
if ! git rev-parse -q --verify v0.8.0 >/dev/null 2>&1; then
  echo "SKIP: v0.8.0 anchor not carried by this repo's history (republished copy) — see SKILL.md"
elif ! git cat-file -e v0.8.0:bin/oracle.py 2>/dev/null; then
  echo "FAIL: v0.8.0:bin/oracle.py missing — deletion has no rollback anchor"
  exit 1
fi
```

The distinction: `git rev-parse -q --verify v0.8.0` failing means the tag
itself doesn't exist (→ SKIP, not this repo's failure to carry). The tag
existing but `git cat-file -e v0.8.0:bin/oracle.py` failing means the tag
is there but doesn't contain the file (→ still FAIL, a genuinely broken
anchor). SKIP does not change the script's overall exit code contribution
for this check; FAIL still does.

## G6 — SKILL.md correction

`## Retired (rollback anchors)` section gains one line under the
`Oracle plane: v0.8.0` bullet:

```
- Oracle plane: `v0.8.0` (not reachable in this repo's history — a
  republished copy; the anchor is real in the original lineage, not this one)
```
