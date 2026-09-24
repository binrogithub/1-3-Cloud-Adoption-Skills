# PRD — Huawei Cloud LATAM LLMWiki (Knowledge Q&A Platform)

| Field | Value |
|---|---|
| Document | `PRD_HUAWEICLOUD_LATAM_LLMWIKI_V1.md` |
| Version | V1.0 |
| Status | Draft for review. Requirements only; implementation is not in scope of this document. |
| Date | 2026-09-23 |
| Project root | `root@110.238.103.247:/root/HuaweiCloudLatam_LLMWiki` (SSH port 8443) |
| Foundations | **JiuwenSwarm 0.2.3** (agent runtime) + **GBrain** (knowledge store and retrieval) |
| Hard constraint | **No changes to JiuwenSwarm or GBrain source code.** LLMWiki is delivered as (1) one new JiuwenSwarm **role** (`llmwiki`, configuration and prompt only) and (2) **glue code** in this project directory. |
| Primary model | `glm-5.2` via Huawei Cloud ModelArts MaaS (`ap-southeast-1`) |
| Overall verdict | **Feasible under the constraint.** The role mechanism was verified live on 247 in code mode. One hard blocker remains: B-1, no embedding model. The design must work around four JiuwenSwarm 0.2.3 behaviours (§5.3), two of which were discovered while writing this PRD. |

---

## 1. Summary

The Huawei Cloud LATAM team repeatedly answers the same questions:
- Which services exist in which LATAM region?
- What is the AWS/Azure/GCP equivalent of a given service?
- What are the quotas, limits and SLAs?
- How does pricing work?
- Which certifications apply (LGPD, LFPDPPP and others)?
- How do I migrate workload X?

The answers are scattered across official documentation, price pages, SA notes, past proposals and chat threads, in English, Spanish and Portuguese, and they go stale silently.

**LLMWiki** is a knowledge Q&A platform built on the *LLM Wiki* pattern. It does not re-retrieve raw document chunks on every question, as classic RAG does. Instead, an LLM role **compiles** raw sources into a persistent, interlinked, human-readable Markdown wiki: one page per service, region, concept, comparison and FAQ, every fact cited to a dated source. Questions are answered **from the wiki**. Good answers are filed back, and the wiki is continuously linted for stale, contradictory or orphaned content.

Responsibilities are split cleanly:

| Layer | Delivered as | Does |
|---|---|---|
| **GBrain** (unmodified) | Installed as-is | Stores wiki pages ("compiled truth + timeline"). Provides hybrid (keyword + vector) search and a page store. |
| **JiuwenSwarm** (unmodified) | Existing runtime + a **dedicated instance** | Hosts the `llmwiki` role, handles model access, and exposes a headless CLI. |
| **`llmwiki` role** (new, config only) | `agents/llmwiki.md` + one config key | Language work only: answers from an evidence pack, and compiles a source into a proposed change set. No tools. |
| **Glue code** (new) | Python 3.12, stdlib-only CLI/service | Retrieval from GBrain, evidence packing, role invocation, claim verification, change-set review, **all writes**, source store, lint, telemetry. |

## 2. Problem, goals, non-goals

### 2.1 Problems

| # | Problem | Consequence today |
|---|---|---|
| P1 | Knowledge is fragmented across the docs site, price pages, SA notes, proposals and chats | SAs spend hours per RFP re-finding facts |
| P2 | There is no single source of truth for service × region availability | Proposals promise services a region lacks |
| P3 | Content is split across three languages | ES/PT customers get English-only or outdated answers |
| P4 | Prices, quotas and launches change silently | Wrong numbers reach customers |
| P5 | Generic LLM chat invents prices, URLs and service names when data is missing | Loss of trust. We have already seen GLM-5.2 fabricate a price table after a tool failure. |

### 2.2 Goals (V1)

- **G1 — Trustworthy answers.** Every number, price, region, URL and certification in an answer is traceable to a wiki page, and every wiki fact is traceable to a dated raw source.
- **G2 — Compounding knowledge.** Each ingested source and each validated answer improves the wiki.
- **G3 — Trilingual.** Users can ask in EN, ES or PT-BR and get the answer in the same language, with identical facts and citations.
- **G4 — Freshness is visible.** Stale or conflicting facts are flagged, never silently served.
- **G5 — Zero footprint on the foundations.** No JiuwenSwarm/GBrain code changes, and no changes to the shared default JiuwenSwarm instance on 247.

### 2.3 Non-goals (V1)

- Binding price quotations (those stay with the HCSA quote engine).
- Public customer-facing deployment (V1 is for internal staff and partners).
- Real-time tenant data (bills, customer resources).
- Replacing the official documentation site.
- JiuwenSwarm team mode or multi-agent orchestration.
- Patching JiuwenSwarm defects. They are worked around and reported upstream (§5.3).

## 3. Users and use cases

| Persona | Typical questions | Success looks like |
|---|---|---|
| Solution Architect | "Is GaussDB available in LA-Mexico City2?", "Huawei equivalent of Aurora + DMS?" | Cited answer they can paste into a proposal |
| Pre-sales / Account Manager | "Explain OBS storage classes to a CFO in Spanish" | Plain-language answer in the customer's language |
| Partner engineer | "How do I set up CCE with ELB in São Paulo?" | Steps plus official doc links |
| Knowledge curator | "What changed this week? What contradicts what?" | Review queue and lint report |
| Platform admin | Onboarding sources, access, cost | Health check, audit log, token metrics |

Use cases:
- **UC-1** Ask a question and get a cited answer.
- **UC-2** Compare services or regions as a table.
- **UC-3** Ingest a source (file, URL or crawl).
- **UC-4** Review and approve proposed wiki edits.
- **UC-5** Browse the wiki.
- **UC-6** Nightly lint.
- **UC-7** File a good answer back as an FAQ page.

## 4. Concept: the LLM Wiki pattern

The system has three layers:

```
L3  SCHEMA      wiki/SCHEMA.md + page templates + role prompt       (human-owned, changed by PR)
L2  THE WIKI    GBrain pages: "Compiled truth" + append-only "Timeline", cited   (changed only via approved change sets)
L1  SOURCES     immutable, sha256-addressed snapshots + metadata                (never edited)
```

The platform runs three loops:
1. **Ingest → Compile → Review → Apply.** A source becomes an L1 snapshot. The role proposes page edits as a change set. The glue validates them mechanically, a curator approves, and the glue writes to GBrain.
2. **Ask → Retrieve → Answer → Verify.** The glue retrieves wiki pages from GBrain and packs them as evidence. The role answers from that evidence only. The glue verifies every claim against the cited pages before serving the answer.
3. **Lint.** Glue jobs flag stale pages, broken links, orphans, unknown sources and uncited facts. The role may propose fixes, but only as change sets.

## 5. Environment baseline (verified on 247, 2026-09-23)

### 5.1 Host facts

| Item | Observed |
|---|---|
| Host | Ubuntu 24.04, 4 vCPU, 14 GiB RAM (~9 GiB available), 91 GB free |
| JiuwenSwarm | **0.2.3** (uv tool at `/root/.local/share/uv/tools/jiuwenswarm`), openjiuwen 0.1.16. Shared default instance runs as systemd `jiuwenswarm-gateway` / `jiuwenswarm-agentserver` on 19001 (WS `/acp`, `/tui`), 19000 (Web) and 18092 (AgentServer). |
| Model config | `~/.jiuwenswarm/config/.env`: `API_BASE=https://api-ap-southeast-1.modelarts-maas.com/v1`, `MODEL_NAME=glm-5.2`, `MODEL_PROVIDER=OpenAI` |
| Shared instance settings | `permissions.enabled: false`; `mcp.servers: []`; `EMBED_*` unset (the memory rail logs "Embedding API key not configured") |
| GBrain | **Not installed.** No `bun`, no `psql`. Docker is available. |
| Runtimes | `python3.12`, Node, Docker |
| Shared neighbours (must not disturb) | LiteLLM `:4000` (+ Postgres, Prometheus `:9090`, Grafana `:3000`), Latam AI Workbench `:8000/:8444`, Caddy `:80/:443/:9443`, apps on `:4444`, `:8090`, `:8022`, `:8765` |
| Embedding models on the LiteLLM gateway | **None** (28 `model_name` entries, no embed/rerank) |

### 5.2 Hard blocker

**B-1 — No embedding endpoint.** GBrain's vector search needs an embedding model. Its defaults (OpenAI/Voyage) are US-hosted external APIs, which may be unacceptable for internal LATAM content. The decision must be recorded in ADR-001 during M0. Options, in order of preference:
1. A MaaS-hosted multilingual embedding model, if the account offers one.
2. A self-hosted multilingual model (bge-m3 / multilingual-e5-large) in Docker on 247, which needs about 2 GB RAM. Throughput must be measured.
3. An external API for **public** sources only.

Without embeddings, only keyword search works, and **keyword search cannot answer cross-language questions**. We verified this: the query "tamanho máximo objeto OBS" does not rank the English `services/obs` page first. Keyword-only mode is therefore acceptable for development only, not for launch (G3).

### 5.3 JiuwenSwarm 0.2.3 behaviours the design must respect

| ID | Behaviour | Evidence | Design response |
|---|---|---|---|
| R-1 | Headless `jiuwenswarm chat` is a WS thin client. It needs the Gateway (exit 3 otherwise). Exit codes 0/1/3 are reliable. | Earlier measurement (Aug 2026) + probe on 247 | The glue maps exit 3 to "infra down" and never to "no answer" |
| R-2 | `--mode team` does not create a team | Earlier measurement | Not used |
| R-3 | In headless mode, `permissions: ask` does not block tools | Earlier measurement | The dedicated instance sets **`deny`**, not `ask`, for shell/write/cron tools. Whether `deny` is enforced headless is **not yet verified** (AG-6). |
| **R-6** | **Custom `.md` roles crash on dispatch in `--mode agent`.** `_agent_def_to_subagent_config` passes tool-name strings into `SubAgentConfig.tools`, which expects ToolCard objects. Log: `[TaskTool] Subagent creation failed: type=llmwiki, error='str' object has no attribute 'name'`. The sub-agent result is `""`, and the main agent then answers **by itself**, uncited. | **Reproduced live on 247** (dedicated instance) | **Use `--mode code`**, where custom roles go through `CodeAgentRail`/`AgentTool`, which filters real ToolCards. **Verified live**: the role was created and returned a correctly cited answer. Report upstream. |
| **R-7** | **MCP servers do not reach custom sub-agents.** The parent registers MCP as `McpServerConfig`, but the sub-agent only inherits `ToolCard`s. | Source reading (`code_agent_rail.py`, `interface_deep.py`). Not yet confirmed live. | **Retrieval lives in the glue**, not in the role. The role receives an evidence pack and needs no tools. |
| **R-8** | **`tools: []` in a role file silently means "all tools"** (`list(tools) if tools else ["*"]`) | Source reading | The role declares a sentinel whitelist (`tools: [__llmwiki_no_tools__]`) that matches no tool |
| R-9 | Multi-instance isolation is built in. `JIUWENSWARM_DATA_DIR` relocates all state, and ports come from `AGENT_SERVER_PORT` / `GATEWAY_PORT` / `WEB_PORT`. Roles are loaded from `$JIUWENSWARM_DATA_DIR/agents/*.md` and enabled by `react.subagents.<name>.enabled: true`. | **Verified live**: a dedicated instance ran on 20092/20001/20000 while the shared instance stayed untouched. The log showed `loaded custom agent 'llmwiki' from user`. | LLMWiki runs its **own instance**. The shared `~/.jiuwenswarm` is never edited. |
| R-10 | Code-mode sessions create working folders (`coding_memory/`, `sub_agents/`, `prompt_attachment/`, `logs/`) in the process working directory | Observed after the smoke run | The dedicated instance's `WorkingDirectory` must be `runtime/jiuwen/work`, not the project root |

### 5.4 Measured baseline (for sizing)

| Measurement | Value | Implication |
|---|---|---|
| Trivial "Reply PONG" through the shared instance, agent mode | **24,658 input tokens**, **TTFT 7.1 s** | The framework's system prompt costs ~25k tokens per call before any evidence. Cost and latency targets in §10 are set against this floor. |
| Role dispatch in code mode (1-page evidence) | Correct cited answer: `A single object can be up to 48.8 TB [W:services/obs].` | The role + evidence-pack contract works |
| Code-mode event stream | Dispatch = `chat.tool_call` with name `Agent`. Role output = `chat.tool_result` with `tool_name: "Agent"` and `result: "success=True data={'output': '…', 'agent_id': 'llmwiki'} error=None"` (a Python-repr string, not JSON). | The glue must parse this format and take the answer from the role's own result, **not** from `chat.final`, which the main agent may reword. |

## 6. Architecture

### 6.1 Component view

```
 Browser / CLI / Slack-bot (later)
        │
        ▼
 ┌──────────────────────────── Glue (new, this repo) ─────────────────────────────┐
 │  API/CLI: ask · ingest · compile · review · approve/reject · lint · doctor      │
 │  Retriever ──► GBrain (CLI or MCP, read)        Source store (L1, sha256)       │
 │  Evidence packer (page blocks + stale flags, char budget)                       │
 │  Role invoker ──► jiuwenswarm chat --mode code --jsonl  (dedicated instance)    │
 │  Event parser (role output from Agent tool_result; fail closed if absent)       │
 │  Claim verifier (numbers, prices, URLs, regions, certs vs CITED pages)          │
 │  Change-set store + validator ──► the ONLY writer to GBrain (on human approval) │
 │  Lint jobs · telemetry (tokens, TTFT, verdicts) · audit log                     │
 └──────────────┬──────────────────────────────────────────────┬──────────────────┘
                │ WS :20001                                     │ gbrain CLI / MCP
 ┌──────────────▼──────────────────────────────┐   ┌───────────▼─────────────────┐
 │ JiuwenSwarm 0.2.3 — DEDICATED instance       │   │ GBrain (unmodified)          │
 │ JIUWENSWARM_DATA_DIR=runtime/jiuwen          │   │ Postgres+pgvector (Docker,   │
 │ ports 20092 / 20001 / 20000                  │   │ own container, NOT litellm's)│
 │ main agent (code mode) ─Agent tool─► llmwiki │   │ + embedding endpoint (B-1)   │
 │ role (no tools)                              │   └──────────────────────────────┘
 └──────────────┬──────────────────────────────┘
                ▼
       ModelArts MaaS glm-5.2
```

### 6.2 Design decisions

- **D-1 — Dedicated JiuwenSwarm instance, stock binaries.** It runs under systemd units `llmwiki-jiuwen-agentserver` / `llmwiki-jiuwen-gateway`, which call the same `/root/.local/bin/jiuwenswarm-*` binaries with isolated env (R-9). Its config is a **copy** of the default config with four changes: the role enabled, other acting sub-agents disabled, MCP empty, and permissions `deny` for `bash`, `mcp_exec_command`, `create_terminal`, `write`, `write_file`, `edit_file`, `search_replace`, `acp_chat` and cron mutations. Its `.env` holds its own MaaS key (mode 0600), ideally not the shared key.
- **D-2 — The role does language work only.** It has no tools (R-8 sentinel), receives everything in the prompt, and outputs either a cited answer or change-set JSON. It never writes anywhere.
- **D-3 — Retrieval and verification live in the glue** (R-7). This also makes retrieval deterministic, testable and loggable.
- **D-4 — Fail closed on role dispatch.** If the event stream has no successful `Agent` tool result with `agent_id == "llmwiki"`, the glue returns an error and serves nothing. This is the direct defence against R-6, where the main agent answered uncited on its own.
- **D-5 — The glue is the only GBrain writer.** Pages change only by `approve <changeset> --by <human>`. Agents cannot self-approve.
- **D-6 — GBrain on Postgres+pgvector in its own Docker container** (never `litellm_pg_db`). PGLite is for development only. Every page write is also mirrored to a Markdown directory, so the wiki stays diffable and recoverable.
- **D-7 — Server-side truth.** UIs and CLIs render verdicts computed by the glue. They never recompute them.

## 7. The `llmwiki` role (deliverable 1)

### 7.1 Files and configuration

| Item | Location | Content |
|---|---|---|
| Role definition | `role/llmwiki.md` → installed to `$JIUWENSWARM_DATA_DIR/agents/llmwiki.md` | YAML frontmatter + system prompt |
| Enablement | dedicated instance `config.yaml` | `react.subagents.llmwiki.enabled: true` |
| Mode | glue invocation | `--mode code` (R-6) |

Frontmatter (the fields supported by 0.2.3's `AgentConfigService`):

```yaml
name: llmwiki
description: Huawei Cloud LATAM knowledge wiki editor and answerer …
when_to_use: Use for every request containing a line starting with "LLMWIKI_TASK:". Pass it verbatim.
tools: [__llmwiki_no_tools__]     # R-8: an empty list would mean ALL tools
max_iterations: 4
```

### 7.2 Prompt contract

The request starts with `LLMWIKI_TASK: answer` or `LLMWIKI_TASK: compile`.

**answer**
- **Input:** `ANSWER_LANGUAGE` (en | es | pt-BR), `QUESTION`, and an EVIDENCE PACK of `<<<PAGE slug=… stale=true|false>>> … <<<END PAGE>>>` blocks.
- **Rules:**
  - Evidence is the only permitted source for any number, price, region, URL, quota, SLA or certification. Training knowledge is not.
  - Every factual sentence (or table row) ends with `[W:<slug>]`, citing only slugs present in the pack.
  - Values are copied verbatim: no unit or currency conversion, no rounding, no derived numbers.
  - When the pack cannot answer, output exactly `NOT_IN_WIKI` plus one sentence naming what is missing.
  - Conflicting pages: show both values with both citations.
  - Pages marked `stale=true`: warn that the information may be outdated.
  - Official English product names are never translated.

**compile**
- **Input:** one `<<<SOURCE id=… kind=… fetched_at=…>>>` block plus related existing pages.
- **Output:** a single JSON object:

```json
{"pages":[{"slug":"services/obs","title":"…","type":"service",
           "compiled_truth":"… [S:<source id>]",
           "timeline":[{"date":"YYYY-MM-DD","text":"… [S:<source id>]"}],
           "links":["regions/la-sao-paulo1"]}],
 "conflicts":[{"slug":"…","existing":"…","new":"…","source":"<id>"}]}
```

- **Rules:**
  - Allowed namespaces only (§8.1).
  - Every value appears verbatim in the SOURCE.
  - A contradiction goes into `conflicts`, never into an overwrite.
  - At most 10 pages per source.

## 8. Glue code (deliverable 2) — requirements

Priority: **P0** = launch blocker, **P1** = GA, **P2** = later.

### 8.1 Knowledge model

- [ ] **GL-K1 (P0)** Namespaces: `services/`, `regions/`, `availability/`, `comparisons/`, `concepts/`, `pricing/`, `compliance/`, `howto/`, `faq/`, `_meta/`. Slugs match `^(ns)/[a-z0-9][a-z0-9._-]*`, and path traversal is rejected.
- [ ] **GL-K2 (P0)** Page = frontmatter (`slug`, `title`, `type`, `last_verified`, `sources[]`, `links[]`) + `## Compiled truth` + `## Timeline` (append-only, newest first, `- YYYY-MM-DD — text [S:id]`).
- [ ] **GL-K3 (P0)** L1 source record `{id=sha256[:16], ref, format, kind, licence: public|internal|confidential, lang, owner, fetched_at, last_seen, chars}` plus an extracted-text file. Records are immutable, and re-ingesting the same content only updates `last_seen`.
- [ ] **GL-K4 (P1)** The LATAM region list and codes are loaded from an authoritative source. They are never typed by hand or by an LLM.

### 8.2 GBrain adapter

- [ ] **GL-G1 (P0)** GBrain is accessed only through its public CLI (or its MCP server, called by the glue, not by the role). Command templates for search, get and put are configurable, so CLI changes need config changes, not code changes. **The exact installed CLI syntax is verified in M0.**
- [ ] **GL-G2 (P0)** Search output is parsed from JSON (`slug`/`path` fields) or from text (namespace-slug regex). Unknown or invalid slugs are dropped.
- [ ] **GL-G3 (P0)** A keyword-only Markdown-directory backend with the same interface exists for development and as the B-1 fallback. It is marked as not launch-grade (cross-language limitation, §5.2).
- [ ] **GL-G4 (P0)** GBrain errors or timeouts produce an explicit `retrieval_failed` error. The glue never proceeds to answer with an empty pack.

### 8.3 Ask pipeline

- [ ] **GL-A1 (P0)** Answer language: detect EN/ES/PT-BR, or take the user's override.
- [ ] **GL-A2 (P0)** Retrieve top-k pages (default 6) from GBrain and build the evidence pack within a character budget (default 60k), with per-page `stale` flags. Pricing pages go stale after 90 days, others after a configurable period.
- [ ] **GL-A3 (P0)** If retrieval returns nothing, **abstain without calling the model**. This saves the ~25k-token floor.
- [ ] **GL-A4 (P0)** Invoke `jiuwenswarm chat --mode code --jsonl --timeout N` with `JIUWENSWARM_DATA_DIR` and `GATEWAY_PORT` set to the dedicated instance. Stdin is closed. Exit 3 maps to `gateway_down`, exit 1 to `agent_failed`, and a timeout to `timeout`.
- [ ] **GL-A5 (P0)** Parse events per §5.4. The answer is the role's own `Agent` tool result (`agent_id == llmwiki`, `success=True`). If none exists, return `role_not_dispatched` and serve nothing (D-4). Record `input_tokens`, `output_tokens`, `ttft_ms` and `total_latency_ms` from `chat.usage_metadata`.
- [ ] **GL-A6 (P0)** Run the claim verifier (§9) on the role output. Serve the redacted text with a status of `grounded`, `partially_verified`, `abstained` or `no_claims`. A `no_citations` result is **never** served as an answer; it is replaced by the NOT_IN_WIKI message.
- [ ] **GL-A7 (P1)** A streaming API (SSE): emit `ack` immediately, then `retrieval`, `final{answer, status, citations, stale, issues}` and `error`. Because the verified text is only known after verification, V1 streams progress events and sends the verified answer once. Token streaming of unverified text is forbidden.
- [ ] **GL-A8 (P1)** Multi-turn: conversation ownership is recorded at creation, never inferred from persisted turns.
- [ ] **GL-A9 (P1)** Every ask is logged to JSONL: question, lang, status, citations, retrieved, stale, issues, tokens, elapsed. Raw answers are kept only when policy allows.

### 8.4 Ingest, compile, review, apply

- [ ] **GL-C1 (P0)** Ingest file (MD/TXT/HTML/PDF via `pdftotext`) or URL. Deterministic extraction only, no LLM. Extractions under a minimum length are rejected, so no empty snapshots are stored.
- [ ] **GL-C2 (P0)** Parser self-checks must be falsifiable. Row and value samples from price/quota tables are compared with the rendered source, and a mismatch fails the ingest. (Lesson from a sister project: a PDF parser over-extracted 2–5× while its self-check always reported 0.00%.)
- [ ] **GL-C3 (P0)** Compile: retrieve related pages, invoke the role with `LLMWIKI_TASK: compile`, and parse the JSON (tolerating code fences). Invalid JSON produces an `invalid` change set, never a crash.
- [ ] **GL-C4 (P0)** Mechanical validation:
  - Valid slugs, page count ≤ 10, valid dates.
  - Every claim in `compiled_truth` is checked against the snapshot of **the source it cites**. Kept older facts are resolved through their own `[S:old-id]` snapshot.
  - Timeline entries must cite the new source.
  - Any failure marks the change set `invalid`.
- [ ] **GL-C5 (P0)** Change-set store with statuses `pending | invalid | applied | rejected`, a history, and a `protected` flag for `pricing/`, `compliance/` and `availability/`.
- [ ] **GL-C6 (P0)** `approve --by <human>` merges proposals into pages:
  - Compiled truth is replaced only when non-empty.
  - The timeline is appended with dedup and sorted.
  - Links are unioned, the source is added, and `last_verified` is set to today.
  - The page is written to GBrain and the mirror.
  - The actor `llmwiki` or an empty actor is refused, and only `pending` sets can be approved.
- [ ] **GL-C7 (P1)** Conflicts from the role are shown side by side with both sources in the review queue.
- [ ] **GL-C8 (P1)** File-back (UC-7): a verified answer becomes an `faq/` change set.

### 8.5 Lint

- [ ] **GL-L1 (P0)** A nightly report covering stale pages, broken links, orphans, citations to unknown sources, and uncited facts in compiled truth.
- [ ] **GL-L2 (P1)** Cross-page contradiction detection: the same entity and attribute with different values on two pages.
- [ ] **GL-L3 (P1)** Re-verification: re-fetch crawlable stale sources, diff them, and compile when changed.

### 8.6 Operations

- [ ] **GL-O1 (P0)** `doctor` checks the jiuwenswarm binary, the dedicated data dir, the role file, whether the dedicated gateway is listening, the GBrain binary/DB, the embedding endpoint, and (optionally) `pdftotext`. It exits non-zero on any required failure.
- [ ] **GL-O2 (P0)** An installer that creates the dedicated instance from the default config. It **dry-runs by default** and prints the config diff. It never edits `~/.jiuwenswarm`, never starts services by itself, and writes `.env` with mode 0600.
- [ ] **GL-O3 (P0)** systemd units for the dedicated instance with `Restart=on-failure` and `WorkingDirectory=runtime/jiuwen/work` (R-10). Ops use `systemctl` or PID, never `pkill -f jiuwenswarm`, which kills the calling shell.
- [ ] **GL-O4 (P1)** Health endpoint reporting the running glue version and git SHA, so an out-of-date process can be detected (AG-8).
- [ ] **GL-O5 (P1)** Token, latency and verdict metrics exported to the existing Prometheus, plus a Grafana dashboard.
- [ ] **GL-O6 (P1)** Nightly `pg_dump` of GBrain plus a tarball of L1 and the mirror, with 14-day retention and one tested restore.
- [ ] **GL-O7 (P0)** Implementation constraint: Python ≥ 3.11, standard library only for the glue core. PyYAML is used only by the installer, which runs on JiuwenSwarm's own interpreter.

### 8.7 Access control

- [ ] **GL-S1 (P0)** Roles `reader`, `contributor`, `curator` and `admin`. No demo credentials in source or bundles.
- [ ] **GL-S2 (P0)** Pages derived from `confidential` sources are filtered by the asker's role **before** retrieval, not after generation.
- [ ] **GL-S3 (P1)** An audit log of asks, approvals, rejects and exports.

## 9. Claim verification (hard requirements)

Earlier projects on this infrastructure showed that "grounding numbers somewhere in the context" is not evidence: 98.7% of fabricated amounts passed such a check, and fabricated URLs and names went unchecked.

- [ ] **GR-1 (P0)** Claim types: numbers (including prices, %, sizes and years), URLs, and configured terms (region and certification names, taken from the wiki's `regions/` and `compliance/` page titles).
- [ ] **GR-2 (P0)** A claim is grounded only if its value appears in a page **cited in the same sentence or table row**. A value found in an uncited retrieved page is **not grounded**.
- [ ] **GR-3 (P0)** Number matching accepts EN (`1,024.5`) and ES/PT (`1.024,5`) formats. Values are compared as numbers, not as digit strings.
- [ ] **GR-4 (P0)** URLs must be on an allow-list of domains (`huaweicloud.com` and its subdomains) **and** appear in a cited page. Competitor-hosted links are rejected.
- [ ] **GR-5 (P0)** Ungrounded claims are redacted in place with `⟦unverified⟧`, and the status becomes `partially_verified`. The issues list (claim, sentence, reason) is returned to the UI, which must display it.
- [ ] **GR-6 (P0)** The same verifier checks compile output (`[S:id]` over source snapshots) before a change set can become `pending`.
- [ ] **GR-7 (P0)** The verifier's quality is reported only with a **discrimination test**:
  - Seeded perturbations of correct answers must be flagged ≥ 95% of the time.
  - Correct answers must pass ≥ 95% of the time.

  "0 ungrounded" on its own is never accepted as evidence.

## 10. Non-functional requirements

These targets are calibrated to the §5.4 floor of ~25k framework tokens and ~7 s TTFT per call.

| ID | Requirement | Target (V1) |
|---|---|---|
| NFR-1 | Latency (single question, wiki hit) | `ack` < 1 s. Final verified answer P50 < 25 s, P95 < 60 s. Re-baseline in M0 in code mode. |
| NFR-2 | Concurrency | 10 concurrent askers with no errors. Compile jobs are queued and never starve asks. |
| NFR-3 | Scale | 5,000 pages / 50,000 sources. GBrain search P95 < 500 ms. |
| NFR-4 | Footprint on 247 | ≤ 4 GiB RAM steady for LLMWiki total. Neighbours keep ≥ 3 GiB available. |
| NFR-5 | Isolation | 0 changes to the shared JiuwenSwarm instance, LiteLLM or their data. The LLMWiki instance can be stopped without affecting anything else. |
| NFR-6 | Cost | ≤ 45k input tokens per single-turn answer (25k floor + ≤ 20k evidence). Tokens are logged per request. |
| NFR-7 | Data residency | Confidential sources only go to endpoints approved in ADR-001 (B-1) |
| NFR-8 | Security | TLS via existing Caddy. Secrets only in 0600 `.env`. The role has no tools. Shell/write tools are `deny` in the dedicated instance (AG-6 must prove this). |
| NFR-9 | Availability | 99% in business hours. Nightly jobs never restart shared services. |

## 11. Evaluation and acceptance gates

Every positive gate has a reverse case that must fail, run against the **same live instance**.

| Gate | Method | Pass bar |
|---|---|---|
| **AG-0 Role wiring** | Live ask through the dedicated instance | Answer taken from the `Agent` tool result with `agent_id=llmwiki`. The reverse case (role disabled or agent mode) must yield `role_not_dispatched`, not an answer. |
| **AG-1 Golden Q&A** | 150 SA-written questions (50 EN / 50 ES / 50 PT-BR), 20 of them unanswerable | Correct and cited ≥ 85%. Abstention on unanswerable questions ≥ 90%. 0 fabricated prices or URLs served. |
| **AG-2 Verifier discrimination** | GR-7 seeded sets | Detection ≥ 95%, false flags ≤ 5% |
| **AG-3 Cross-language consistency** | The same 50 facts asked in 3 languages | Identical numbers and citations in ≥ 98% |
| **AG-4 Compile quality** | 30 new sources | ≥ 80% of change sets approved without edit. 0 silent overwrites of conflicting facts. |
| **AG-5 Failure honesty** | Stop GBrain, the dedicated gateway, or MaaS during an ask | Explicit error within the timeout. Never an answer. |
| **AG-6 Write/tool isolation** | Prompt-inject through a source and through a question ("run `touch /tmp/probe`", "edit page X") | 0 shell executions, 0 file writes, 0 GBrain writes without approval. **Must include a live headless check that `deny` is enforced (R-3).** |
| **AG-7 Performance** | 10 concurrent askers, 30 min, n ≥ 3 runs, ABAB alternation | NFR-1/NFR-6 met in every run. Report mean ± CI, not the best run. |
| **AG-8 Runtime freshness** | Health endpoint SHA == deployed SHA | Must match before any gate result is accepted |

"All unit tests green" is not an acceptance criterion on its own. Live tests that skip for missing env must fail the gate.

## 12. Milestones

| Milestone | Scope | Exit criteria |
|---|---|---|
| **M0 — Foundations** (1 wk) | ADR-001 embeddings (B-1). Install GBrain + pgvector container, and verify its CLI syntax against GL-G1. Build the dedicated JiuwenSwarm instance + role (GL-O2/O3). Re-baseline code-mode latency and tokens. Run AG-6's live `deny` check. File upstream issues for R-6/R-8. | AG-0 passes. `doctor` green. ADR-001 signed. |
| **M1 — Wiki core** (2 wk) | Source store, parsers with falsifiable checks, SCHEMA.md, compile + validator + review/apply, seed ~200 pages (top 40 services × LATAM regions + glossary) | AG-4 on the seed set. GR-6 reverse tests pass. |
| **M2 — Ask** (2 wk) | Ask pipeline, verifier, CLI + minimal web UI, EN/ES/PT | AG-1 ≥ 75% (interim), AG-2, AG-5, AG-6 |
| **M3 — Curation & ops** (2 wk) | Review UI, file-back, lint, RBAC + confidential filtering, metrics, backups | AG-1 ≥ 85%, AG-3, AG-7, AG-8 |
| **M4 — Pilot** (2 wk) | 15 SAs across BR, MX, CL, AR, PE | ≥ 60% of pilot questions resolved without curator follow-up. 0 P0 incidents. |

## 13. Risks and open questions

| # | Risk / question | Mitigation / owner |
|---|---|---|
| RK-1 | B-1: no embeddings, or CPU embeddings too slow | Measure bge-m3 on 247 in M0. Keyword fallback for development only. |
| RK-2 | JiuwenSwarm upgrades change role loading, event format or R-6 behaviour | Pin 0.2.3. AG-0 is the upgrade canary. Event parsing is isolated in one module. |
| RK-3 | `deny` is not enforced headless (R-3 family) | AG-6 live check in M0. If it fails, remove shell/write tools via `modes.code.rails/tools` in the dedicated config, or run the dedicated instance under a sandboxed user. |
| RK-4 | The main agent in code mode rewrites or truncates the evidence pack before dispatch | The verifier checks against the glue's own pack, so a truncated pack causes abstention, not fabrication. Measure the drop rate in M0. |
| RK-5 | ~25k-token framework floor per call dominates cost | GL-A3 skip-on-empty. Track per-request tokens. Evaluate a trimmed code-mode rail set in the dedicated config. |
| RK-6 | 247 is shared, and concurrent sessions restart services | Dedicated instance and ports. Evaluation runs check a lock file. Never touch the shared LiteLLM. |
| RK-7 | Licensing of crawled docs and internal proposals | Legal review before M1. `licence` field. Confidential sources are opt-in. |
| RK-8 | 14 GiB host is tight | NFR-4 budget. Move Postgres to RDS/GaussDB if sustained usage exceeds 70%. |
| OQ-1 | Authoritative source for the service × region matrix? | LATAM product team |
| OQ-2 | SSO provider? | Platform admin |
| OQ-3 | Should the dedicated instance get its own MaaS key for cost attribution? | Platform admin |
| OQ-4 | Retention of question logs (they may contain customer names) | Legal / compliance |

## 14. Appendix

### 14.1 Proposed repository layout

```
HuaweiCloudLatam_LLMWiki/
├── PRD_HUAWEICLOUD_LATAM_LLMWIKI_V1.md
├── role/llmwiki.md                 # the JiuwenSwarm role (deliverable 1)
├── llmwiki/                        # glue package (deliverable 2)
│   ├── config.py  pages.py  store.py (GBrain + file backends)  sources.py
│   ├── jiuwen.py (headless client + event parser)  grounding.py (verifier)
│   ├── changesets.py  pipeline.py (ask/compile/approve/lint)  cli.py
├── bin/llmwiki                     # CLI launcher
├── deploy/install_instance.py      # dedicated instance installer (dry-run default)
├── deploy/systemd/                 # llmwiki-jiuwen-{agentserver,gateway}.service
├── wiki/SCHEMA.md  wiki/templates/
├── eval/                           # golden set, discrimination sets
├── tests/                          # unit + reverse + fake jiuwenswarm replaying real events
├── llmwiki.toml(.example)
└── runtime/                        # gitignored: jiuwen/ (instance), sources/, changesets/, wiki mirror, logs
```

### 14.2 Glossary

- **Evidence pack**: the wiki pages the glue retrieved, passed verbatim to the role. The only permitted knowledge for an answer.
- **Change set**: a role-proposed, glue-validated, human-approved batch of page edits. It is the only write path to the wiki.
- **Grounded claim**: a value that appears in a page cited in the same sentence or row (§9).
- **Dedicated instance**: a JiuwenSwarm instance with its own `JIUWENSWARM_DATA_DIR` and ports, running stock binaries.
