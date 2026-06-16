# E3: Signal Scan Fix

**Depends on:** nothing (independent)  
**Blocks:** E5  
**Parallel with:** E0, E1, E2  
**Estimate:** 0.5 day  
**PRD sections:** 5.2

## Goal

Fix two bugs in `dream_signals.py` that cause the signal classifier to produce
false positives and contaminate dream reports with self-referential noise.

## Stories

### S3.1: Role filter for scan_records()

**Bug:** `scan_records()` in `dream_signals.py` iterates all records without
filtering by role. This means `system` and `attachment` records (including the
skill's own SKILL.md content) are scanned for correction/preference patterns.

**Fix:** Add a `require_role` parameter to `scan_records()`:

```python
SCANNABLE_ROLES = {"human", "assistant"}

def scan_records(records, *, require_role=SCANNABLE_ROLES):
    for rec in records:
        if rec.get("role") not in require_role:
            continue
        # ... existing pattern matching ...
```

**Acceptance:**
- System prompt records are no longer scanned
- Attachment records (tool results containing file contents) are no longer scanned
- Only `human` and `assistant` role records are classified
- Existing true-positive signal detection unchanged

### S3.2: Fix `\bwrong\b` false positive

**Bug:** The correction pattern `r"\bwrong\b"` at line 26 of `dream_signals.py`
matches the string "confidently wrong" in the skill's own SKILL.md description:
> "flags signals where the model was confidently wrong"

This pattern is too broad. It matches legitimate English prose, not just
user corrections.

**Fix:** Replace the bare `\bwrong\b` with more specific correction patterns:

```python
# Before
r"\bwrong\b"

# After - require correction context
r"\bthat(?:'s| is| was) wrong\b",
r"\byou(?:'re| are| were) wrong\b",
r"\bwrong (?:approach|answer|solution|output|result)\b",
```

**Acceptance:**
- `"that's wrong, use X instead"` -> detected as correction
- `"the model was confidently wrong"` -> NOT detected
- `"wrong approach here"` -> detected as correction
- `"what went wrong"` -> NOT detected (no correction intent)

### S3.3: Test coverage for signal classifier

Create or update `tests/test_dream_signals.py`:

- Test: system-role record is skipped
- Test: attachment-role record is skipped
- Test: human-role record with correction is detected
- Test: "confidently wrong" in SKILL.md text produces no signal
- Test: "that's wrong" in human message produces correction signal
- Regression: existing true-positive patterns still work

**Acceptance:**
- All 6+ test cases pass
- No false positives from skill self-description

## Definition of Done

- [ ] `dream_signals.py` has role filtering in `scan_records()`
- [ ] `\bwrong\b` pattern replaced with contextual patterns
- [ ] `test_dream_signals.py` covers role filtering and regex fixes
- [ ] Running `/maas-dreaming` on itself no longer produces self-referential signals
