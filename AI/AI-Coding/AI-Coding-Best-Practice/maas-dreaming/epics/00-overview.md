# Epic Dependency Map

PRD: `prd-v2-project-knowledge-engine.md` (E0–E9) + `prd-v3-e2e-hardening.md` (E10–E12)

## Dependency Graph

```
E0 Schema & Foundation ─────┬──────────────────────────────────┐
                            │                                  │
              ┌─────────────┼──────────────┐                   │
              v             v              v                   │
    E1 Tree-Sitter    E2 Git Adapter    E3 Signal Fix          │
      Indexer           (parallel)      (independent)          │
              │             │              │                   │
              v             v              │                   │
         E4 Code Queries API               │                   │
              │             │              │                   │
              └─────────────┼──────────────┘                   │
                            v                                  │
                   E5 Enhanced Dream Report                    │
                            │                                  │
              ┌─────────────┼──────────────┐                   │
              v             v              v                   │
    E6 CLI &          E7 Team Sharing    E8 Nightly            │
    Integration       & Artifact         Pipeline              │
              │             │              │                   │
              └─────────────┼──────────────┘                   │
                            v                                  │
                   E9 Documentation & SKILL.md ────────────────┘
                            │
                            v
              ┌─────────────┼──────────────┐
              v             v              v
    E10 Edge         E11 SKILL.md        E12 Report
    Extraction       Completeness        Quality Fixes
    (P0)             (P0)               (P1)
```

## Summary Table

| Epic | Title | Depends On | Est. | New Files | Modified Files |
|------|-------|------------|------|-----------|----------------|
| E0 | Schema & Foundation | none | 0.5d | `code_index.py` (skeleton) | `pyproject.toml` |
| E1 | Tree-Sitter Indexer | E0 | 1.5d | `install_grammars.py`, `test_code_index.py` | `code_index.py` |
| E2 | Git History Adapter | E0 | 1d | `git_adapter.py`, `test_git_adapter.py` | `dream_sources.py` |
| E3 | Signal Scan Fix | none | 0.5d | -- | `dream_signals.py`, `test_dream_signals.py` |
| E4 | Code Queries API | E0, E1 | 1d | `code_queries.py`, `test_code_queries.py` | -- |
| E5 | Enhanced Dream Report | E1, E2, E3, E4 | 1.5d | -- | `dream_agent_report.py`, `test_dream_agent_report.py` |
| E6 | CLI & Integration | E1, E4 | 1d | -- | `mce/cli.py`, `mce/executor.py`, `mce/retrieve.py` |
| E7 | Team Sharing & Artifact | E1 | 0.5d | -- | `code_index.py` |
| E8 | Nightly Pipeline | E1, E2, E5 | 0.5d | -- | `bin/dream-nightly.sh`, `should_run.py` |
| E9 | Documentation | all | 0.5d | -- | `SKILL.md`, `AGENTS.md`, `runbook.md` |
| **E10** | **Edge Extraction** | **E1** | **2d** | -- | `code_index.py`, `test_code_index.py` |
| **E11** | **SKILL.md Completeness** | **E10** | **0.5d** | -- | `SKILL.md` |
| **E12** | **Report Quality Fixes** | **E10, E3** | **0.5d** | -- | `dream_agent_report.py`, `code_queries.py` |
| **Total v2** | | | **~8.5d** | **7 new** | **14 modified** |
| **Total v3** | | | **~3d** | **0 new** | **4 modified** |
| **Grand total** | | | **~11.5d** | **7 new** | **18 modified** |

## Parallelism

```
Week 1:  [E0] -> [E1 |||||||||||] [E2 ||||||||] [E3 |||]
Week 2:  [E4 ||||||||] -> [E5 |||||||||||]
Week 2:  [E6 ||||||||] [E7 |||] [E8 |||]
Week 2:  [E9 |||]
Week 3:  [E10 |||||||||||||||||] -> [E11 |||] [E12 |||]
```

E1, E2, E3 can run in parallel after E0.
E4, E6, E7 can run in parallel after E1.
E5 is the critical path — it integrates everything.
E10 is the v3 critical path — edge extraction unblocks E11 and E12.
E11 and E12 can run in parallel after E10.

## v3 E2E Findings Reference

| Finding | Severity | Epic | Status |
|---------|----------|------|--------|
| F1: SCANNABLE_ROLES missing `user` | Bug | E3 (fixed in E2E) | Fixed |
| F2: edges table always 0 | P0 Gap | E10 | Pending |
| F3: Coupling noise (.gitkeep) | P1 | E12 | Pending |
| F4: Cold-start layout | P1 | E12 | Pending |
| F5: overview() last_indexed type | P2 | E12 | Pending |
| F6: SKILL.md missing 9 topics | Doc | E11 | Pending |
