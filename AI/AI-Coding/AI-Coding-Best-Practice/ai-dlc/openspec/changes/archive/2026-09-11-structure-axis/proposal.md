# STRUCTURE-AXIS-MATCHING

## Why

Upstream OpenDesign gates by artifact shape (od.mode per-mode rails)
before content; our scorer let the word "landing" outrank the
product's actual shape, so Panama (tourism) and VerdeBet (sports
betting) both landed on open-design-landing's material.

## What Changes

- _DATA_STRUCTURE_MARKERS (en+zh: table/odds/live/score/charts/
  盘口/赔率/实时/表格/比分/图表…): a brief carrying >=2 distinct
  markers declares a data-display shape
- scorer rule 7: candidates whose od.scenario/category names the
  shape (operation, live-artifacts, analytics, monitoring) score
  6xidf per distinct marker, capped at 3; single markers change
  nothing, marker-free briefs score exactly as before
- matched_features carries structure_axis for explainability
- 5 tests; suite green; eval unchanged
