# design-pages-composition Specification

## Purpose
A multi-page product composes: the main template carries the skeleton
and each pages.md page matches its own secondary templates.

## Requirements

### Requirement: each page matches its own secondary templates

design-pages SHALL parse every `## ` section of design/pages.md,
score the eligible pool per page with the deterministic retrieval
(idf-weighted, deduped), exclude the D0 main template from the picks,
and record the per-page shortlist with matched_features in
state.json design_pages; with no pages.md or no sections it SHALL
stop inconclusive with a remedy naming design-specify.

#### Scenario: nominal

- **WHEN a pages.md carries a Pricing page and a Blog page**
- **THEN pricing-page and blog-post SHALL top their pages' picks
  and the main template SHALL not appear as secondary**

### Requirement: per-page material is pinned and never overwritten

design-materialize --page <slug> SHALL copy template material under
design-material/pages/<slug>/ with a manifest naming the page, SHALL
reject non-slug page values, and SHALL refuse re-materialization of
any slot whose manifest already stands — the main slot and page
slots coexist.

#### Scenario: nominal

- **WHEN a page slot is materialized and then the main slot follows**
- **THEN both manifests SHALL stand and a re-run of either SHALL be
  refused**
