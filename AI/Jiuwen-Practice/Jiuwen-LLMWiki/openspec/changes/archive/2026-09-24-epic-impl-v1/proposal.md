# Proposal: implement the LLMWiki EPIC backlog (V1.0 → V1.1) on 247

## Background
The PRD (PRD_HUAWEICLOUD_LATAM_LLMWIKI_V1.md) and its EPIC breakdown
(EPICS_HUAWEICLOUD_LATAM_LLMWIKI_V1.md, 16 epics / 101 stories) describe a
cited-answer knowledge wiki for the Huawei Cloud LATAM team, delivered as one
JiuwenSwarm role plus stdlib glue. At baseline (2026-09-23): glue logic largely
present, 36 unit tests green, but nothing had run end to end live with the final
parser, GBrain/embeddings were absent, and four known defects plus several
repo-hygiene problems were open.

## Options
1. Code-only pass (fix defects, add features, stay unit-verified). Rejected: the
   PRD's own acceptance gates (§11) forbid treating "all unit tests green" as
   acceptance, and the highest-risk items (R-3 headless deny, role wiring) are
   only answerable live.
2. Full implementation pass with live verification on 247 against the dedicated
   instance, real model, real GBrain. Chosen.

## Recommendation
Option 2, executed in dependency order: foundations (E0) → defect fixes →
content scaffolding + seeds → live compile/approve → live asks → gates →
ops hardening → status re-baselining (EPICS V1.1).

## Risks
- 247 is shared: mitigated by dedicated ports/containers/units (verified:
  shared services stayed active throughout) and a ≤4 GiB budget (measured ~1 GiB).
- Real-model compiles can propose wrong facts: mitigated by the mechanical
  verifier (one live change set was correctly rejected during the pass).
- Seed content is bootstrap-authored, not curator-pulled: labelled as such
  (seeds/README.md) and excluded from pricing/ namespaces.
