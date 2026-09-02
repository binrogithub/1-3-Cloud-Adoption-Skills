## Why

The pipeline can take a website from requirements to running, but not
to *looking like anything*: every page country-b-tourism, country-e-tourism,
and landing delivered was CSS written from model memory.
Design is the one delivery dimension with no artifact, no criterion and
no record. OpenDesign (`nexu-io/open-design`, 139 skills / 115
templates / 154 design systems, all markdown on a filesystem) is the
standing asset for that dimension — but handing it to Claude Code
directly repeats the two paid-for mistakes: the judge and the judged
from the same source, and `skill_mode: all` making every workspace
skill visible to every dispatch. the product owner's directive (2026-09-01):
「实施prd」 — implement `docs/prd-uidesigner-opendesign.md` (P0–P3;
P4, the `od` daemon for PDF/PPTX/MP4 export, is explicitly out and is
not claimed anywhere).

## What Changes

- Applicability is **measured, never asserted**: the change's product
  surface is classified by file extension (`web` / `deck`), and the
  design dispatch refuses a surface with neither (exit 24).
- One pointer skill (`ui-designer`) enters the gateway workspace —
  where the upstream tree is, how to pick from it by frontmatter, and
  that the chosen `SKILL.md` must be read in full before acting. No
  upstream content ships in this repo; a pin (tag + sha +
  `tree_sha256`) is the only reference.
- `plan.py design` dispatches one fresh session whose write boundary is
  the measured frontend surface, and the caller reads the session's
  frames — never the model's conclusion sentence — for five facts:
  which template `SKILL.md` was read, which files were written (then
  verified against the filesystem), whether every referenced asset
  resolves, whether the pages render (200, non-empty DOM), and that no
  placeholder text stands. All five pass → an HMAC-signed
  `design-<seq>.json` record; any fail → no record and the reason.
- `report.py deliver` states four design states — `design_applied`,
  `design_declined` (a recorded skip with its reason),
  `design_unverified`, `design_not_applicable`. `design_unverified`
  never folds into failure and never triggers a re-run.
- `aidlc-shell` masks `/opt/open-design` and every `od` on PATH under
  the same missing-mask-refuses-to-start rule as openspec; `bin/`
  gains zero process calls to `od` / `open-design` (I1, AST-gated as a
  regression).

## Capabilities

### spec: `ui-design`

The design dispatch, its applicability measurement, its signed record,
and the containment that keeps the upstream tree plane-side only.
