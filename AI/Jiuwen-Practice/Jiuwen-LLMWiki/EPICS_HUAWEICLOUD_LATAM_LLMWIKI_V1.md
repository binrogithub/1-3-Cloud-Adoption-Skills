# EPIC Breakdown — Huawei Cloud LATAM LLMWiki

| Field | Value |
|---|---|
| Source PRD | `PRD_HUAWEICLOUD_LATAM_LLMWIKI_V1.md` (same directory) |
| Version | **V1.1** (2026-09-24 — full implementation pass under AI-DLC task `epic-impl-v1`) |
| Code baseline | `/root/HuaweiCloudLatam_LLMWiki` on 247: git repo (was: none). `python3.12 -m unittest discover -s tests` → **68 tests OK** (36 → 68). |
| Live state | Dedicated instance under systemd (`llmwiki-jiuwen-*`, enabled); gbrain 0.53 on `llmwiki_pg` (pgvector, own network); TEI e5-small embeddings (`llmwiki_embed`); **all 6 runnable acceptance gates PASS** (ag0/2/3/5/6/8) — `eval/results/`, `docs/evidence/live-2026-09-24/` |
| Constraint | No changes to JiuwenSwarm or GBrain source code (PRD header) — held |

## How status is marked

| Mark | Meaning |
|---|---|
| ✅ **Done** | Code exists on 247 and covers the requirement as written |
| 🟡 **Partial** | Some code exists. The gap is stated explicitly. |
| ⬜ **Not started** | No code or artefact |

Every implemented item also carries a **verification level**. Being implemented does not mean the item is verified.

| Level | Meaning |
|---|---|
| **L-live** | Observed working against the real JiuwenSwarm/model on 247 |
| **L-unit** | Covered by unit/integration tests with fakes. Fakes replay event lines captured on 247 where noted. |
| **L-none** | Code exists but no test exercises it |

> **V1.1 note.** On 2026-09-24 the full pipeline ran live for the first time with the final
> parser: 3 live compiles (one correctly rejected by GR-6), 10 wiki pages applied through
> approved change sets, a 12-question EN/ES/PT golden run (8/9 correct+cited, 3/3
> abstention), and all six runnable gates green. Remaining launch blockers are people/work
> items, not code: real content pulls (E12-S4), the SA-written golden set (E13-S4), the
> load/concurrency rehearsal (E13-S8), and the pilot itself (E14).

---

## 1. Summary

| Epic | Title | Milestone | Status | Stories ✅ / 🟡 / ⬜ | Highest verification |
|---|---|---|---|---|---|
| E0 | Foundations: GBrain, embeddings, ADRs | M0 | ✅ | 6 / 0 / 0 | L-live |
| E1 | Dedicated JiuwenSwarm instance | M0 | ✅ | 6 / 0 / 1 | L-live |
| E2 | `llmwiki` role | M0–M1 | ✅ | 4 / 1 / 0 | L-live |
| E3 | Knowledge model & L1 source store | M1 | ✅ | 7 / 1 / 0 | L-live (S4) |
| E4 | GBrain adapter & wiki store | M0–M1 | ✅ | 6 / 0 / 0 | L-live |
| E5 | Ask pipeline | M2 | ✅ | 11 / 1 / 0 | **L-live (E5-S9)** |
| E6 | Claim verification | M2 | ✅ | 7 / 1 / 0 | **L-live (ag2 on real answers)** |
| E7 | Compile, change sets & review | M1–M3 | ✅ | 9 / 0 / 0 | **L-live (E7-S9)** |
| E8 | Lint & maintenance | M3 | ✅ | 4 / 1 / 0 | L-live (S2 first run) |
| E9 | Operations & observability | M0–M3 | ✅ | 7 / 1 / 0 | L-live |
| E10 | Access control & security | M2–M3 | ✅ | 5 / 0 / 0 | **L-live (ag6, S2/S4)** |
| E11 | Web UI & API | M2–M3 | ✅ | 4 / 1 / 0 | L-live |
| E12 | Content: schema, seed pages, glossary | M1 | 🟡 | 4 / 1 / 0 | L-live (seed batch) |
| E13 | Evaluation & acceptance gates | M0–M3 | 🟡 | 7 / 2 / 0 | **L-live (6 gates PASS)** |
| E14 | Pilot | M4 | ⬜ | 0 / 0 / 3 | — |
| E15 | Repository hygiene (defects found in the baseline) | M0 | ✅ | 5 / 0 / 0 | L-live (git history) |

**Critical path after V1.1:** E12-S4 real content pulls → E13-S4 SA golden set → E13-S8 load rehearsal → E14 pilot. The platform side of the critical path is done.

---

## E0 — Foundations: GBrain, embeddings, ADRs ✅

**Goal:** Resolve blocker B-1 and stand up GBrain unmodified. **PRD:** §5.2, D-6, M0.

| ID | Story | Status | Verification | Evidence / gap |
|---|---|---|---|---|
| E0-S1 | Survey 247 (resources, ports, neighbours, JiuwenSwarm version, no embedding models on LiteLLM) | ✅ | — | PRD §5.1 + environment facts restated in ADR-001 (MaaS model list re-verified live 2026-09-24: 6 chat models, no embeddings) |
| E0-S2 | ADR-001 embeddings decision incl. CPU throughput measurement | ✅ | L-live | `docs/adr/ADR-001-embeddings.md`: self-hosted TEI `multilingual-e5-small` (384d) on 247; measured 40–61 ms/doc, 27.1 docs/s batch; PT/ES→EN cosine 0.86+; bge-m3 ONNX crashes the TEI CPU loader (recorded, do not retry blind) |
| E0-S3 | Install bun + GBrain CLI (unmodified) | ✅ | L-live | bun 1.4.0, `bun install -g github:garrytan/gbrain` → gbrain 0.53.0.0 (npm `gbrain` is unrelated — README warns) |
| E0-S4 | Dedicated Postgres+pgvector container + `gbrain init` | ✅ | L-live | `llmwiki_pg` (pgvector/pgvector:pg16, network `llmwiki_net`, 127.0.0.1:25432, 512 MiB cap, never `litellm_pg_db`); engine=postgres, `doctor` green |
| E0-S5 | Record the real GBrain CLI syntax and update `llmwiki.toml` templates | ✅ | L-live | Verified live: `query <q>` (hybrid; keyword fallback w/ stderr warning), `get <slug>` (markdown), `put <slug>` **needs `--force`/`--expected-revision` to replace** (finding folded into templates), `list` (TSV). Templates updated in `llmwiki.toml(.example)` |
| E0-S6 | ADR-002: dedicated MaaS key | ✅ | L-none | `docs/adr/ADR-002`: decision recorded; interim = shared key (documented deviation); key issuance is a platform-admin action |

**Done when:** `doctor` green ✓, embeddings configured ✓ (hybrid search live: PT query hits EN page at 0.96), ADRs written ✓ (human sign-off rides the merge gate).

---

## E1 — Dedicated JiuwenSwarm instance ✅

| ID | Story | Status | Verification | Evidence / gap |
|---|---|---|---|---|
| E1-S1 | Installer from a config COPY, dry-run default, printed diff | ✅ | L-live | `deploy/install_instance.py`; ran `--apply --force` (E1-S5 restore); `~/.jiuwenswarm` untouched throughout |
| E1-S2 | Isolation via env vars/ports | ✅ | L-live | 20092/20001/20000 while shared 18092/19001/19000 stayed `active` |
| E1-S3 | Permission hardening (`deny` …) | ✅ | **L-live** | ag6: headless `bash` attempt → `[PERMISSION_DENIED] Denied by rule: tools.bash`, zero executions (`docs/evidence/live-2026-09-24/ag6-deny-raw.jsonl`) |
| E1-S4 | systemd units with `WorkingDirectory=runtime/jiuwen/work` | ✅ | L-live | Installer + units fixed (R-10); new folders land under `runtime/jiuwen/work/logs`, root stays clean |
| E1-S5 | Instance `.env` (0600) | ✅ | L-live | Restored by installer `--apply --force`; doctor `[ok] instance .env present` |
| E1-S6 | Install + enable units, survive reboot | ✅ | L-live | Units in `/etc/systemd/system`, `active`, `enabled`; shared units untouched |
| E1-S7 | Trim code-mode rails (~25k floor), measured | ⬜ | | Not attempted; needs a token-cost A/B on the trimmed rail set |

---

## E2 — `llmwiki` role ✅

| ID | Story | Status | Verification | Evidence / gap |
|---|---|---|---|---|
| E2-S1 | Role file + sentinel `tools: [__llmwiki_no_tools__]` | ✅ | L-live | `role/llmwiki.md` (V1.1 adds the instructions-inside-data standing rule) |
| E2-S2 | `answer` contract | ✅ | **L-live** | Golden run: 9 answers EN/ES/PT, cited, verbatim values; abstains with NOT_IN_WIKI |
| E2-S3 | `compile` contract | ✅ | **L-live** | 3 live compiles → valid change sets (one GR-6 rejection of a line-wrapped term = verifier working) |
| E2-S4 | Confirm zero tools at runtime | ✅ | **L-live** | `e2s4-raw-code-mode.jsonl`: exactly ONE tool_call (`Agent`); asked to list files, the role declined and answered cited |
| E2-S5 | Upstream issue reports (R-6, R-8) | 🟡 | L-none | Drafts with repro + evidence in `docs/upstream/`; **not yet filed** (needs upstream repo access) |

---

## E3 — Knowledge model & L1 source store ✅

| ID | Story | Status | Verification | Evidence / gap |
|---|---|---|---|---|
| E3-S1 | Namespaces + slug validation | ✅ | L-unit | unchanged; 68-test suite |
| E3-S2 | Page model round-trip | ✅ | L-unit | **V1.1:** parser now also reads gbrain's normalised frontmatter (block lists AND folded `>-` scalars) — both live-verified through real `get`s |
| E3-S3 | Immutable sha256 source snapshots + dedup | ✅ | L-unit | unchanged |
| E3-S4 | Extraction MD/TXT/HTML/PDF/URL | ✅ | L-unit | HTML/URL covered by tests; **pdftotext now installed** on 247 |
| E3-S5 | `lang` detection + `parser_version` | ✅ | L-unit | both recorded on every ingest (`detect_lang` + `PARSER_VERSION`) |
| E3-S6 | Staleness incl. source `fetched_at` for pricing | ✅ | L-unit | `_page_stale` uses newest snapshot age for `pricing/` |
| E3-S7 | Falsifiable parser self-check (GL-C2) | ✅ | L-unit | `_table_self_check`: shape consistency + sampled `<td>` values must survive extraction; a lost cell FAILS the ingest (reverse test) |
| E3-S8 | Authoritative LATAM region list | 🟡 | L-unit | Loader + lint drift check wired (`llmwiki/regions.py`, `wiki/regions.json` empty **by design**); blocked on OQ-1 (docs portals are client-rendered; export/API needed) |

---

## E4 — GBrain adapter & wiki store ✅

| ID | Story | Status | Verification | Evidence / gap |
|---|---|---|---|---|
| E4-S1 | Two backends behind one interface | ✅ | L-live | gbrain backend ran the whole live session |
| E4-S2 | Keyword fallback backend | ✅ | L-unit | unchanged (cross-language limitation now moot when embeddings are up) |
| E4-S3 | Parse gbrain search output | ✅ | L-live | `[score] slug -- snippet` lines parsed live; invalid slugs dropped (unit) |
| E4-S4 | CLI command templates | ✅ | **L-live** | Verified against real 0.53 (see E0-S5); `--force` semantics documented |
| E4-S5 | Writes mirrored; slugs see the whole brain | ✅ | L-live | `slugs()` = mirror ∪ `gbrain list` (lint sees brain-only pages); live `list` used all session |
| E4-S6 | Bounded per-ask cost | ✅ | L-unit | Term/confidential index cached (TTL + eager invalidation on writes); asks add zero term reads (test pins it) |

---

## E5 — Ask pipeline ✅

| ID | Story | Status | Verification | Evidence / gap |
|---|---|---|---|---|
| E5-S1 | Language detection + `--lang` | ✅ | L-unit | Stronger markers; short-question cases pinned (¿cómo…/qual o preço…) |
| E5-S2 | Retrieval + evidence pack + stale flags + budget | ✅ | L-unit | unchanged, plus pricing `fetched_at` staleness |
| E5-S3 | Abstain without model call when empty | ✅ | L-unit | unchanged |
| E5-S4 | Headless invocation + exit-code mapping | ✅ | L-unit | unchanged; ag5 exercised `gateway_down` live |
| E5-S5 | Event parser, fail-closed, usage metrics | ✅ | L-live | ag0 reverse case: agent mode → `role_not_dispatched`, nothing served |
| E5-S6 | Verify, redact, never serve `no_citations` | ✅ | L-live | Golden run; unknown-citation now also redacted when claims are zero |
| E5-S7 | Retrieval errors → `retrieval_failed` | ✅ | L-unit | now tested (dead backend, no model call) |
| E5-S8 | Ask log + retention switch | ✅ | L-unit | `at` timestamps, rotation at N×128 writes, `log_retention_days` (OQ-4 interim 180d) |
| E5-S9 | **Live end-to-end asks (EN, ES, PT, unanswerable)** | ✅ | **L-live** | Golden run 2026-09-24: 8/9 correct+cited (89%), 3/3 abstained, 0 fabricated prices/URLs; one derived-number ("three") correctly redacted |
| E5-S10 | Evidence-pack integrity (RK-4) | 🟡 | L-unit | `evidence_sha256` + pack size recorded per ask; verifier checks against the glue's own pack (truncation → abstention). Drop-rate measurement not yet run |
| E5-S11 | SSE `ack → retrieval → final/error` | ✅ | **L-live** | `/ask` streamed live; token-streaming of unverified text correctly absent |
| E5-S12 | Multi-turn with ownership at creation | ✅ | L-unit | `runtime/conversations/`, owner recorded at creation, immutable; follow-ups widen retrieval with last 2 turns |

---

## E6 — Claim verification ✅

| ID | Story | Status | Verification | Evidence / gap |
|---|---|---|---|---|
| E6-S1 | Claim extraction (numbers, URLs, terms) | ✅ | L-unit | + service titles & glossary as terms |
| E6-S2 | Same-sentence/row citation rule | ✅ | L-unit | unchanged |
| E6-S3 | EN/ES-PT number formats as values | ✅ | L-unit | + decimal-comma perturbations covered |
| E6-S4 | URL allow-list + presence in cited page | ✅ | L-unit | unchanged |
| E6-S5 | In-place redaction + issues list | ✅ | L-live | Golden run showed the redaction in served answers; issues surfaced in UI |
| E6-S6 | Discrimination test | ✅ | **L-live** | ag2 on 20 REAL logged answers: detection 100%, originals pass 100% (≥95% bar) |
| E6-S7 | Wider claim types | ✅ | L-live | Dates, spelled-out small numbers (live redaction of "three"!), service names via titles+glossary. **Still open:** currency-only amounts without digits |
| E6-S8 | Unit-aware matching | ✅ | L-unit | `48.8 GB` no longer grounded by `48.8 TB`; currency folds into the unit key (`USD 0.0235/GB-month` ≠ `/TB-month`) |

---

## E7 — Compile, change sets & review ✅

| ID | Story | Status | Verification | Evidence / gap |
|---|---|---|---|---|
| E7-S1 | Compile: retrieve → role → tolerant JSON parse | ✅ | L-live | 3 live compiles parsed |
| E7-S2 | Mechanical validation, old citations resolved | ✅ | L-live | Live rejection of the line-wrapped-term page proved `not_in_cited` on real output |
| E7-S3 | Change-set store | ✅ | L-unit | unchanged |
| E7-S4 | Approve: merge, refuse agent actor, pending only | ✅ | L-live | 5 approvals executed (seeds + faq + web-e2e) |
| E7-S5 | CLI review/show/approve/reject | ✅ | L-unit | CLI-level tests; used live all session |
| E7-S6 | Conflicts side by side | ✅ | L-none | CLI prints existing/new per conflict; review UI renders the side-by-side table |
| E7-S7 | Auto-approve policy (FR-C4) | ✅ | L-unit | Non-protected + conflict-free + public + truth-unchanged → policy actor; **default off** |
| E7-S8 | File-back (UC-7) | ✅ | **L-live** | Verified answer → `faq/…` change set (0 problems) → approved → page live |
| E7-S9 | Live compile | ✅ | **L-live** | See E2-S3 |

---

## E8 — Lint & maintenance ✅

| ID | Story | Status | Verification | Evidence / gap |
|---|---|---|---|---|
| E8-S1 | Lint report | ✅ | L-live | Ran on the live wiki (region_drift included) |
| E8-S2 | Nightly schedule + `_meta/lint-report-<date>` | 🟡 | L-live (first run) | `lint --write-page` ran live (`_meta/lint-report-2026-09-24`); `llmwiki-lint.timer` unit written, **enable after merge** (units point at the merged checkout) |
| E8-S3 | Cross-page contradiction detection | ✅ | L-unit | availability pairs + per-unit price conflicts |
| E8-S4 | Re-verification of crawlable stale sources | ✅ | L-unit | `llmwiki reverify` (fetch → dedup-check → compile); wired into the nightly script |
| E8-S5 | GBrain maintenance propose-only | ✅ | L-none | dream/autopilot never installed; `maintenance_mode = "propose-only"` documented in config + runbook invariant |

---

## E9 — Operations & observability ✅

| ID | Story | Status | Verification | Evidence / gap |
|---|---|---|---|---|
| E9-S1 | `doctor` | ✅ | **L-live** | All green: binaries, data dir, role, **.env, work dir (R-10), gateway, gbrain engine=postgres, embedding endpoint reachable**, token store |
| E9-S2 | stdlib-only core | ✅ | L-unit | unchanged |
| E9-S3 | Installer | ✅ | L-live | tracked in E1 |
| E9-S4 | Health endpoint with version + git SHA | ✅ | **L-live** | `/health`; ag8 PASS (health sha == deployed sha) |
| E9-S5 | Prometheus metrics + dashboard | 🟡 | L-live (metrics) | `/metrics` live (asks, verdicts, tokens, TTFT); `deploy/grafana-dashboard.json` delivered, **import into the shared Grafana pending ops** |
| E9-S6 | Backups, 14 days, tested restore | ✅ | **L-live** | `backup.sh` + `restore-test.sh`: dump loads into a throwaway container — 9 pages / 18 chunks / 9 mirror files consistent |
| E9-S7 | Runbook | ✅ | L-none | `docs/RUNBOOK.md` incl. the never-`pkill -f jiuwenswarm` rule |
| E9-S8 | Resource budget check | ✅ | **L-live** | 43 (containers) + 969 (instance) + 24 (web) ≈ 1.0 GiB of the 4 GiB budget; neighbours keep 7.5 GiB |

---

## E10 — Access control & security ✅

| ID | Story | Status | Verification | Evidence / gap |
|---|---|---|---|---|
| E10-S1 | Tool denial | ✅ | **L-live** | ag6: `[PERMISSION_DENIED]` headless (R-3 resolved affirmatively) |
| E10-S2 | Roles reader/contributor/curator/admin, no demo creds | ✅ | **L-live** | Token store (sha256, 0600, gitignored); live: anonymous approve → 403, curator token → applied; no credentials in source |
| E10-S3 | Confidential filtering BEFORE retrieval | ✅ | L-unit | GL-S2: filter between search and pack; `filtered_confidential` reported; reader abstains where curator is served |
| E10-S4 | Audit log | ✅ | **L-live** | `runtime/logs/audit.jsonl`: asks, ingests, compiles, approvals with actors |
| E10-S5 | Prompt-injection resistance | ✅ | **L-live** | ag6: injection via question AND via ingested source → 0 shell, 0 writes; role has the standing data-vs-instructions rule |

---

## E11 — Web UI & API ✅

| ID | Story | Status | Verification |
|---|---|---|---|
| E11-S1 | HTTP API: `/ask` SSE, `/pages`, `/search`, `/sources`, `/changesets`, `/lint`, `/health` (+`/metrics`) | ✅ | **L-live** (all endpoints exercised live; /lint 403 for readers = authz working) |
| E11-S2 | Ask UI (EN/ES/PT), status, citations, stale, unverified claims | ✅ | L-live (served + SSE verified; unverified-claim list rendered) |
| E11-S3 | Wiki browse UI | ✅ | L-live |
| E11-S4 | Review queue UI (diff, conflicts, approve/reject) | ✅ | **L-live** (unified diff per page, side-by-side conflicts, token-gated approve) |
| E11-S5 | Caddy route + TLS | 🟡 | `deploy/caddy-llmwiki.conf` snippet; applying touches the neighbour proxy → ops approval (NFR-5) |

---

## E12 — Content: schema, seed pages, glossary 🟡

| ID | Story | Status | Note |
|---|---|---|---|
| E12-S1 | `wiki/SCHEMA.md` + page templates per namespace | ✅ | 8 templates + schema (incl. `_meta` exception) |
| E12-S2 | EN/ES/PT glossary; product names never translated | ✅ | `wiki/glossary-terms.txt` (loaded as checked terms); role rule |
| E12-S3 | Source onboarding list with licence decisions | ✅ | `docs/SOURCES.md` (public/internal/confidential decisions + blockers) |
| E12-S4 | Seed ~200 pages through E7 | 🟡 | **10 pages live** (4 regions, 3 compliance, 1 service, 1 faq, 1 lint-report) via real compile→approve; seeds are labelled bootstrap digests (`seeds/README.md`); scale-up needs the docs export (pull blockers in SOURCES.md) |
| E12-S5 | Replace the smoke data | ✅ | `llmwiki.toml` → gbrain backend + `runtime/wiki`; smoke wiki archived under docs/evidence |

---

## E13 — Evaluation & acceptance gates 🟡

| ID | Story | Status | Evidence / gap |
|---|---|---|---|
| E13-S1 | Unit/reverse suite | ✅ | **68 tests OK** (fake replays captured event shapes) |
| E13-S2 | **AG-0 role wiring**, live, incl. reverse | ✅ | `eval/gates.py ag0` PASS (agent-mode reverse → no dispatch, nothing served) |
| E13-S3 | AG-2 discrimination on real answers | ✅ | ag2 PASS: 20 real answers, 100%/100% (first run exposed a gate-script bug, fixed; the verifier itself was correct on well-formed perturbations) |
| E13-S4 | AG-1 golden set (150 SA-written + 20 unanswerable) | 🟡 | Starter 12-question set + runner live (89% / 100% abstention / 0 fabrications); SA authorship pending E14 |
| E13-S5 | AG-3 cross-language consistency | ✅ | ag3 PASS 3/3 (small-n interim; ≥98% bar needs the 50-fact set once content scales) |
| E13-S6 | **AG-6 isolation** live (R-3) | ✅ | **PASS**: bash denied headless, 0 executions, injection via question+source neutral, 0 unapproved writes |
| E13-S7 | AG-5 failure honesty | ✅ | ag5 PASS (dead gateway → explicit error, no answer); MaaS-stop mid-ask variant still to rehearse |
| E13-S8 | AG-7 performance (10 concurrent, n≥3, ABAB) | 🟡 | Code-mode tokens/TTFT logged per ask (ask.jsonl); the concurrency rehearsal not yet run (needs the real golden set to be meaningful) |
| E13-S9 | AG-8 runtime freshness | ✅ | ag8 PASS (health SHA == deployed SHA) |

---

## E14 — Pilot ⬜

| ID | Story | Status |
|---|---|---|
| E14-S1 | Onboard 15 SAs (BR, MX, CL, AR, PE) | ⬜ |
| E14-S2 | Weekly curator review cadence + feedback → change sets | ⬜ |
| E14-S3 | Pilot exit report against PRD M4 criteria | ⬜ |

All three are people-work. The platform prerequisites (review queue, file-back, lint, metrics, audit) are live.

---

## E15 — Repository hygiene ✅

| ID | Defect | Resolution |
|---|---|---|
| E15-S1 | Not a git repo, no `.gitignore` | git repo (5+ commits); ignores `runtime/`, `llmwiki.toml`, `*.env`, code-mode folders, `._*` |
| E15-S2 | 24 macOS `._*` files | removed; `.gitignore` blocks their return |
| E15-S3 | Code-mode folders in project root | WorkingDirectory moved to `runtime/jiuwen/work` (E1-S4); folders removed; new folders land under `work/` |
| E15-S4 | Smoke artefacts with a real transcript | archived under `docs/evidence/smoke-2026-09-23/` with README |
| E15-S5 | `llmwiki.toml` pointing at smoke data | now points at gbrain + `runtime/wiki` (handled by E12-S5) |

---

## Appendix — Code-to-PRD traceability (V1.1)

| File (repo) | PRD requirements it covers |
|---|---|
| `role/llmwiki.md` | §7 answer+compile contracts, R-8 sentinel, injection standing rule |
| `llmwiki/config.py` | GL-G1, GL-A2/A4, FR-C4 flags, term namespaces, retention, web/auth paths |
| `llmwiki/pages.py` | GL-K1/K2, staleness, gbrain frontmatter compatibility (block lists, folded scalars) |
| `llmwiki/sources.py` | GL-K3, GL-C1, **GL-C2 self-check**, lang detection, parser_version |
| `llmwiki/regions.py` | GL-K4 loader + drift (OQ-1 pending) |
| `llmwiki/store.py` | GL-G1…G3, D-6 mirror, E4-S5 slugs union, env plumbing |
| `llmwiki/jiuwen.py` | GL-A4, GL-A5, D-4 fail-closed |
| `llmwiki/grounding.py` | GR-1…GR-7 incl. units, dates, word numbers, unknown-citation redaction |
| `llmwiki/changesets.py` | GL-C3…C6, GR-6, D-5 |
| `llmwiki/pipeline.py` | GL-A1…A3/A6/A9, GL-C3…C8, GL-L1…L3, GL-S2/S3, E4-S6 index, fileback, auto-approve |
| `llmwiki/auth.py` | GL-S1 (roles, hashed tokens) |
| `llmwiki/web.py` | GL-A7 SSE, GL-A8 conversations, GL-O4 health, GL-O5 metrics, E11 UI/API |
| `llmwiki/cli.py` | CLI surface, GL-O1 doctor (extended), regions/token/serve/reverify/fileback |
| `deploy/*` | GL-O2/O3/O6 (installer, units+timers, backup/restore), Caddy snippet, Grafana dashboard |
| `eval/*` | AG-0…AG-8 gates + golden runner |
| `docs/` | ADR-001/002, RUNBOOK, SOURCES, upstream issue drafts, evidence archives |
| `tests/` (68) | E13-S1 incl. every fix's reverse case |
