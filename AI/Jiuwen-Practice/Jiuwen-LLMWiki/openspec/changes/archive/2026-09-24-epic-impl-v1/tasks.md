# Tasks: EPIC backlog implementation pass

## T1 — Foundations (E0, E15)
- Install GBrain 0.53 via bun (GitHub), dedicated pgvector container, gbrain init,
  self-hosted embeddings (TEI e5-small), ADR-001/002 with measurements.
- git init + .gitignore, remove AppleDouble files, relocate code-mode work dirs,
  archive smoke evidence.
- Acceptance: `llmwiki doctor` green; hybrid search answers a PT query from an EN page.

## T2 — Defect fixes with reverse tests (E1-S4, E3, E4-S5/S6, E5, E6-S7/S8)
- WorkingDirectory → runtime/jiuwen/work; gbrain slugs union with `list`; cached
  term/confidential index; unit-aware number matching; dates, word numbers and
  service titles as claims; retrieval-failure and CLI-level tests.
- Acceptance: the previously documented false-acceptance cases now fail closed
  (48.8 GB vs 48.8 TB; fabricated term in a wrongly-cited sentence).

## T3 — Content, ops, security, web (E7-S6/S7/S8, E8, E9, E10, E11, E12-S1/S2/S3/S5, E13 tooling)
- SCHEMA + templates + glossary + source-onboarding list; auto-approve policy
  (off by default); file-back; contradictions; reverify; lint page + timers;
  backup/restore-test; runbook; resource check; roles/tokens/audit/confidential
  filtering; web API+SSE+UI with health/metrics; gates script + golden runner;
  upstream issue drafts; region-list loader (empty by design pending OQ-1).
- Acceptance: 68-test suite green; web endpoints answer live; backup restores.

## T4 — Live verification (E1-S5/S6, E2-S2/S3/S4, E5-S9, E7-S9, E13 gates)
- Restore instance .env, install+enable units, compile and approve seed sources
  through the real role, run the multilingual golden set, run gates ag0–ag8.
- Acceptance: change sets applied; EN/ES/PT answers cited; unanswerable questions
  abstain; all six runnable gates PASS; EPICS status table updated to V1.1.
