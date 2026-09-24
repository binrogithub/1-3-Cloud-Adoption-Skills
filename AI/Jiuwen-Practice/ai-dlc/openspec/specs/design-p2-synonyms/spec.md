# design-p2-synonyms Specification

## Purpose
A query written in one vocabulary reaches the template named in
another — 中文 queries reach English-only templates, generic-word
queries reach the specific page-type name.

## Requirements

### Requirement: synonyms bridge vocabulary without outranking it

The scorer SHALL credit each unique curated-synonym token present in
the query at 4×idf — below a name hit — and SHALL dedup tokens across
a template's synonyms; the sidecar reader SHALL ignore the axis under
AI_DLC_NO_INTENT_META like every other od-intent key.

#### Scenario: nominal

- **WHEN a zh query bridges via curated synonyms to an en-only
  template competing against a prose-only candidate**
- **THEN the carrier SHALL outscore the prose-only candidate and
  matched_features SHALL name the bridged tokens**

### Requirement: the fill is full-coverage and the curation is auditable

fill-od-intent.py SHALL derive sidecars for every SKILL.md under
design-templates/ and skills/ (no example.html requirement) and SHALL
merge --synonyms terms lowercased, deduped and capped at 8; the
curated table SHALL live in the plane repo (scripts/od-synonyms.json)
and metadata-validate SHALL accept the synonyms key.

#### Scenario: nominal

- **WHEN the filler runs with --synonyms on a tree with a template
  lacking example.html in skills/**
- **THEN a sidecar SHALL be written there carrying the capped curated
  terms**
