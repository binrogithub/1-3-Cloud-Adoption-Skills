# page-compose-loop Specification

## Purpose
A multi-page product composes end to end: the D1.6 picks become
per-page specs, and the vocabulary bridge covers the common web
template families.

## Requirements

### Requirement: per-page picks reach per-page specs

design-pages-specify SHALL require design_pages in state (else stop
inconclusive with a remedy naming design-pages), dispatch exactly one
ui-designer session over the standing design artifacts plus each
picked SKILL.md, cap the run at --max-pages (default 3), and write
design/pages/<slug>.md per page; each page's skill sha256 SHALL be
pinned in state.json design_page_specs and the outcome SHALL be the
mechanical existence check — a missing file is inconclusive even
when the session claimed success.

#### Scenario: nominal

- **WHEN two pages carry picks and the session writes both files**
- **THEN design_page_specs records both slugs with sha pins and
  all_written true**

#### Scenario: session claims but does not write

- **WHEN one page's file is missing after the session**
- **THEN the command exits inconclusive and records
  all_written false**

### Requirement: batch 2 bridges keep the discipline

scripts/od-synonyms.json SHALL carry the second curated batch (12
additional templates, ≤8 terms each) with no term wiring a competing
page-type family's token (docs owns 文档/手册, kanban owns 看板,
dashboard owns 管理面板/仪表盘).

#### Scenario: nominal

- **WHEN the table is loaded**
- **THEN each batch-2 template SHALL be present with 1-8 terms and
  none of the banned family tokens**
