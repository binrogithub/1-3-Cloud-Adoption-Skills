# des5-fixes Specification

## Purpose
What one live campaign measured wrong, the plane fixes — the bridge
phrase, the session's answer, the page list, and the counter all
report facts as they are.

## Requirements

### Requirement: a verbatim synonym phrase is a phrase-class signal

The scorer SHALL credit a curated synonym of ≥2 tokens appearing
verbatim in the negation-stripped query text at 8×idf per token —
below a native trigger phrase (12), above the token rule (4) — and
SHALL exclude those tokens from the token rule so the hit is never
double-counted.

#### Scenario: nominal

- **WHEN a competitor's native trigger and a carrier's curated
  synonym are the same phrase and the carrier bridges a second
  verbatim phrase**
- **THEN the carrier SHALL outscore the competitor**

### Requirement: a session naming the template by directory name is a pick

Reply parsing SHALL accept the full SKILL.md path or the candidate's
directory name as a standalone token (lookaround-guarded so
near-duplicate names do not swallow each other); a name-only answer
SHALL produce a judged (or judged-2nd) selection, never a degrade,
and a reply naming nothing SHALL still degrade honestly.

#### Scenario: nominal

- **WHEN the arbiter replies with only the template's directory
  name**
- **THEN the selection SHALL be method=judged**

### Requirement: page matching reads product pages, not spec meta

design-pages SHALL accept --task-dir, and the pages.md parser SHALL
prefer Page:-titled sections (prefix stripped from title and slug),
else drop meta-titled sections (responsive/interaction
flow/accessib/audit/compliance/quality/checklist/content-N/p0),
recording the dropped count; when every section looks meta the
original sections SHALL stand.

#### Scenario: nominal

- **WHEN pages.md carries "## Page: Pricing" plus "## Responsive
  Behavior Summary" and "## Accent Usage Audit"**
- **THEN exactly the Pricing page SHALL be matched and
  meta_sections_dropped SHALL be 2**

### Requirement: the filler's dry run counts

fill-od-intent.py --dry-run SHALL report the number of sidecars it
would write.

#### Scenario: nominal

- **WHEN dry-running over a one-template root**
- **THEN the summary SHALL say it would write 1 sidecar**
