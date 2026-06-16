# PRD v5: Coupling Scope, Unresolved Edges, Relative Paths

Date: 2026-06-16
Source: E2E Round 2 findings (prd-v4-e2e-round2.md F2/F3/F4)

## Changes

### C1: Coupling section 加项目路径过滤 (F3)

**File:** `scripts/dream_agent_report.py` — `_section_coupling()`
**What:** Filter coupling pairs to only include paths under `repo_root`. Cap display to top 20 pairs by score.
**Why:** Currently dumps 184,994 cross-project pairs (37MB), zero from target project.
**How:** After fetching from `cq.coupling()`, filter each `file_path` to start with or be under repo_root name. Add `max_pairs=20` limit.
**Acceptance:**
- Coupling section only contains paths within the project
- Section has at most 20 pairs
- Report size drops from 37MB to <100KB

### C2: Import/extends edges 保留未解析目标 (F2)

**File:** `scripts/code_index.py` — `index_all()` edge writing + schema
**What:** Add `target_name TEXT` column to `edges` table. When target symbol not in DB, set `target_id=NULL` and store `target_name`. `callers()`/`callees()` still only return resolved edges.
**Why:** 11 import edges + 2 extends edges per file are generated but silently dropped because targets are stdlib. SKILL.md claims these edge kinds exist.
**How:**
- ALTER edges table: `ADD COLUMN target_name TEXT`
- In edge writing loop: if `tgt_id` is None, insert with `target_id=NULL, target_name=edge.target_name`
- `callers()`/`callees()` unchanged (they JOIN on target_id, NULL rows naturally excluded)
- `overview()` edge count unchanged (COUNT(*) includes unresolved)
**Acceptance:**
- `edges` table has rows with `target_id IS NULL` and `target_name` set
- Edge kinds include `imports` and `extends`
- `callers()`/`callees()` behavior unchanged
- `overview()["total_edges"]` count includes all edges

### C3: git_adapter 存 repo-root 相对路径 (F4)

**File:** `scripts/git_adapter.py`
**What:** Compute file paths relative to `--repo-root` instead of git worktree root.
**Why:** `commit_files.file_path` stores worktree-relative paths (e.g. `AI/AI-Coding/.../scripts/code_index.py`), so `coupling("scripts/code_index.py")` finds nothing.
**How:** After parsing `git log --numstat`, strip the repo-root prefix from each file path. If a path doesn't start with the prefix, skip it (it's outside the project).
**Acceptance:**
- `commit_files.file_path` values are relative to repo-root
- `coupling("scripts/code_index.py")` returns results
- Coupling section in report shows project-local paths
