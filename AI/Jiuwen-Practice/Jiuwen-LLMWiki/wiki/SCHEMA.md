# LLMWiki page schema (L3 — human-owned, changed by PR)

The wiki (L2) lives in GBrain and is mirrored to `runtime/wiki/`. It changes **only**
through approved change sets (`llmwiki approve`), except the `_meta/` namespace, which
the glue writes operationally (lint reports, glossary). L1 sources are immutable,
content-addressed snapshots under `runtime/sources/`.

## Page layout (every namespace)

```markdown
---
slug: services/obs
title: Object Storage Service (OBS)     # exact official name; never translated (G3)
type: service                            # see namespace table
last_verified: "2026-09-24"              # set by approve; drives staleness
sources: ["<16-hex sha256 prefix>"]      # L1 snapshots backing this page
links: ["regions/la-sao-paulo1"]         # other wiki slugs; lint checks these
---
# Object Storage Service (OBS)

## Compiled truth
Every sentence or table row that states a fact ends with [S:<source id>].
Values are copied verbatim: no unit or currency conversion, no rounding.

## Timeline
- 2026-09-24 — OBS generally available in LA-Sao Paulo1 [S:<source id>]
```

Frontmatter values are JSON-encoded per line (round-trips through GBrain's YAML
frontmatter and `Page.from_markdown`).

## Namespaces

| Namespace | type | One page per | Protected | Notes |
|---|---|---|---|---|
| `services/` | service | Huawei Cloud service | no | official English name as title |
| `regions/` | region | LATAM region | no | title = exact region name (`LA-Sao Paulo1`) |
| `availability/` | availability | service × region pair | **yes** | FR-C4: human approval |
| `comparisons/` | comparison | Huawei vs AWS/Azure/GCP service | no | table form, cite per row |
| `concepts/` | concept | technical concept (storage class, AZ) | no | |
| `pricing/` | pricing | service pricing (per region when it varies) | **yes** | goes stale after 90 days |
| `compliance/` | compliance | certification/regulation (LGPD, LFPDPPP, ISO 27001) | **yes** | title = checked term |
| `howto/` | howto | procedure | no | steps cite official docs |
| `faq/` | faq | question (slug from the question) | no | filed from verified asks (UC-7) |
| `_meta/` | lint-report / glossary / … | glue-written operational pages | — | never via change sets |

## Rules that the verifier enforces mechanically

- Every number, date, URL, region name and configured term in `Compiled truth` must
  appear in a source cited in the **same sentence or table row** (`[S:id]`).
- Region and certification names are ground truth terms taken from `regions/` and
  `compliance/` page titles; service titles and `wiki/glossary-terms.txt` are checked
  terms too.
- Units are part of the claim: `48.8 GB` is not grounded by a source saying `48.8 TB`.
- `Timeline` is append-only, newest first, and cites the source that records the change.

## Staleness

`last_verified` older than `[ask].stale_after_days` (90) → stale. Pricing pages are
stale when either `last_verified` **or** the newest backing snapshot
(`sources[].fetched_at`) is older than `[ask].pricing_stale_after_days` (90).
