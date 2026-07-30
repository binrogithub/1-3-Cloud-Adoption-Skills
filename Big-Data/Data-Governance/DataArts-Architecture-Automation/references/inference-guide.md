# Inference Guide

## From Source Tables To Architecture Objects

Infer a conservative architecture from table names, column names, and business descriptions.

- Entities: stable nouns such as `citizen`, `vehicle`, `tax_declaration`, `agency`.
- Lookup/code tables: reference prefixes, low-cardinality status/type/category columns, or files named `ref_*`.
- Data standards: reusable identifiers, statuses, categories, dates, monetary amounts, flags, and metrics.
- Dimensions: conformed descriptive tables used to slice facts, usually `dim_*` or reference entities.
- Summary tables: `summary`, `mart`, `kpi`, `aggregate`, or report-ready tables.
- Atomic metrics: single aggregation over one field, such as `sum(amount)`, `count(id)`, `avg(rate)`.
- Derivative metrics: an atomic metric bound to dimensions and optional time/filter context.
- Compound metrics: formulas combining two or more metrics, such as rates, ratios, scores, or normalized KPIs.
- Business metrics: human-readable indicators tied to a business process, purpose, definition, owner, and technical metric.

## Naming

Use stable English codes and readable display names:

- English names: lowercase snake case where the API allows it, with a scenario prefix.
- Display names: scenario prefix plus business-friendly text.
- Avoid collisions with prior demos by adding a scenario discriminator when needed.
- Respect workspace prefix validation errors exactly.

## Metric Rules

- Create atomic metric dependencies before derivative metrics.
- Create derivative metrics before compound metrics.
- Use `sum` for additive counts and amounts.
- Use `avg` for rate fields already materialized as percentages.
- Model true ratios as compound metrics whenever numerator and denominator metrics exist.
- Avoid inventing field IDs. Always list the source table and use returned DataArts attribute IDs.

## ID Rules

Persist IDs after every create:

- directory IDs for standards and code tables
- standard row IDs for field standard bindings
- code table IDs for lookup references
- subject IDs for `l3_id` anchors
- model workspace IDs for table models
- table IDs and field IDs for atomic metrics
- atomic, derivative, and compound metric IDs for higher-level metrics

If a payload field rejects a label, inspect the error: DataArts often expects a numeric ID even when UI labels appear in docs.

## Publication State

Creation APIs commonly return `DRAFT`. Do not assume draft objects can be used everywhere. If a downstream API requires published objects:

1. Prefer already published top-level subjects as anchors.
2. Use official approval/publish APIs only when available and validated in the workspace.
3. Document any draft-state dependency in the report.
