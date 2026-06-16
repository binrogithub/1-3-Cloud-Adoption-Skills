# E12: Dream Report Quality Fixes

**Depends on:** E10 (edges — Key Symbols section), E3 (signal fix)
**Blocks:** nothing
**Estimate:** 0.5 day
**PRD sections:** 2.3 (F3), 2.4 (F4), 2.5 (F5)

## Goal

Fix three quality issues discovered in E2E testing: coupling noise, cold-start
layout, and API type inconsistency.

## Stories

### S12.1: Filter coupling noise files

Add noise filtering to `_section_coupling()` in `dream_agent_report.py`:

```python
_NOISE_PATTERNS = frozenset({".gitkeep", ".keep", ".empty", ".gitmodules"})

def _is_noise_path(path: str) -> bool:
    name = Path(path).name
    if name in _NOISE_PATTERNS:
        return True
    if not Path(path).suffix:  # no extension
        return True
    return False
```

In `_section_coupling()`:
- Filter out pairs where either file matches `_is_noise_path()`
- Raise `min_score` from 0.3 to 0.4 in the `cq.coupling()` call

**Acceptance:**
- `.gitkeep` files never appear in Frequently Co-Changed Files section
- Pairs with Jaccard < 0.4 are excluded
- Existing tests still pass (update test fixtures if needed)

### S12.2: Fix cold-start Steering Instructions layout

In `_cold_start_report()` in `dream_agent_report.py`, move the Steering
Instructions block to appear between Status and How to Get Started:

```markdown
## Status
...
## Steering Instructions   <-- move here
...
## How to Get Started      <-- after steering
...
## Next Steps
```

**Implementation:**
- Move the `if instructions:` block to execute before the `## How to Get Started`
  header is appended to `lines`
- Remove the instructions block from its current position (after How to Get
  Started header, before git conditional)

**Acceptance:**
- Cold-start report with `--instructions` shows sections in order:
  Status → Steering Instructions → How to Get Started → Next Steps
- Cold-start report without `--instructions` has no Steering Instructions section
- Test in `test_dream_agent_report.py` verifies section order

### S12.3: Fix CodeQueries.overview() last_indexed type

In `code_queries.py` `overview()`, convert `last_indexed` from epoch to ISO:

```python
# After fetching last_indexed from DB
if last_indexed:
    try:
        ts = float(last_indexed)
        if ts > 1e9:  # looks like Unix timestamp
            last_indexed = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        pass  # keep as-is if already a string
```

Add required import: `from datetime import datetime, timezone`

**Acceptance:**
- `CodeQueries.overview()["last_indexed"]` returns ISO 8601 string
- Dream report still works (no double-conversion)
- New test in `test_code_queries.py` verifies the type

## Definition of Done

- [ ] `.gitkeep` and other noise files excluded from coupling section
- [ ] Coupling min_score raised to 0.4
- [ ] Cold-start Steering Instructions appears between Status and How to Get Started
- [ ] `overview()["last_indexed"]` returns ISO 8601 string
- [ ] All existing tests pass
- [ ] New tests for each fix
