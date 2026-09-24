# LLMWiki — a cited, verifiable wiki for Huawei Cloud LATAM

LLMWiki turns raw documents into a small trustworthy wiki and answers questions
**with citations only**: every number, price, date, region and URL in an answer
is mechanically verified against immutable source snapshots before it is served.

Built as glue around three moving parts — no framework, Python stdlib only for
the core:

```
L1  immutable source snapshots (sha256-addressed, markdown/PDF/HTML/…)
L2  wiki pages — "compiled truth", one topic per page, per-statement [S:id] citations
L3  the page you see (Ask / Wiki / Sources) + audited change sets as the ONLY write path
```

An LLM (JiuwenSwarm + DeepSeek/GLM on Huawei Cloud MaaS) does the language work
(compiling sources into pages, answering); the glue does everything that must be
trustworthy: retrieval, evidence packing, claim verification, writes, audit.

## Features

- **Grounded ask (SSE streaming)** — thinking, provisional and the final verified
  answer; claims that fail verification are redacted, never served
- **Multi-turn conversations** — history widens retrieval and travels into the
  prompt as context-only; grounding rules never loosen; left sidebar history,
  ChatGPT-style layout
- **Upload → wiki** — drop a document (MD/TXT/HTML/PDF/CSV/JSON/YAML) on the
  Sources page; the real model compiles it; clean public change sets auto-apply,
  everything else queues for a curator
- **Recompile** — re-run the compile pipeline on a stored source (validation-rule
  or model upgrades) without re-uploading
- **Cascade delete** — delete a source together with the statements citing it;
  pages left with no statements are removed
- **Web editor** — edit a page's compiled truth online through the same
  mechanical grounding gate as model compiles (D-5 change sets, always)
- **Nightly maintenance** — backup, lint (conflicts, orphans, stale pricing) and
  a "dream" reconcile pass (newest source wins, audited change sets)
- **RBAC** — reader / contributor / curator / admin tokens; protected namespaces
  (`pricing/`, `compliance/`, `availability/`) require a curator

## Quickstart

```bash
git clone <this-repo> && cd <this-repo>
./install.sh                 # checks prerequisites, writes llmwiki.toml, bootstraps runtime
./bin/llmwiki doctor         # verifies the wiring end to end
./bin/llmwiki ingest seeds/obs-bootstrap.md
./bin/llmwiki compile <source-id>          # model compile → change set
./bin/llmwiki review && ./bin/llmwiki approve <changeset-id> robin
./bin/llmwiki serve --host 127.0.0.1 --port 20080
```

Then open the server-rendered UI at `http://127.0.0.1:20080/` — or run the
Agent Studio front-end (Next.js + Caddy TLS) from the companion workbench repo
for the full three-page experience (Ask / Wiki / Sources, upload, editor,
history sidebar).

## Prerequisites

| Component | Why | Notes |
|---|---|---|
| Python ≥ 3.11 | glue + tests | stdlib only, zero pip deps |
| [gbrain](https://github.com/garrytan/gbrain) 0.53 | L2 page store, hybrid retrieval | `bun`-installed; `backend = "files"` works for keyword-only development |
| PostgreSQL + pgvector | gbrain engine | container `pgvector/pgvector:pg16` in production |
| Text Embeddings Inference | semantic retrieval (e5-small) | optional; retrieval degrades to keyword with a warning |
| [JiuwenSwarm](https://...) + a model endpoint | the LLM | dedicated instance via `deploy/install_instance.py`; DeepSeek/GLM on Huawei Cloud MaaS tested |

`install.sh` checks all of these and tells you exactly what is missing; it never
installs system packages silently.

## Configuration

Copy `llmwiki.toml.example` → `llmwiki.toml` (done by `install.sh`) and set:

- `[gbrain]` — backend (`gbrain-mcp` in production), binary path, command templates
- `[jiuwen]` — dedicated JiuwenSwarm instance binary/data dir, the `llmwiki` role
- `[ask]` — retrieval width, stale windows, allowed URL domains, glossary
- `[review]` — auto-apply policy flags (kept conservative by default)
- `[web]` — bind address, token store; front it with Caddy for TLS

Secrets (model API keys, DB passwords) live in env files under `runtime/` —
never in the repo (`.gitignore` enforces this).

## Operations

- `deploy/install_instance.py --apply` — dedicated JiuwenSwarm instance + systemd units
- `deploy/systemd/` — `llmwiki-web.service`, nightly backup / lint / dream timers
- `deploy/gbrain-dream.sh` — nightly metadata-apply + conflict reconcile (newest wins)
- `./bin/llmwiki lint` — contradictions, uncited facts, orphans, stale pricing, region drift
- `./bin/llmwiki token create <role> <name>` — RBAC tokens

## Testing

```bash
python3 -m pytest tests/ -q      # 114 tests: pipeline, grounding, change sets,
                                 # MCP client, web handlers, cascade, multi-turn, edit
```

`eval/` holds the golden gates (grounding accuracy, retrieval speedup, UI latency).

## Repository layout

```
llmwiki/          the glue (pipeline, web, store, grounding, sources, changesets, auth)
bin/llmwiki       stdlib-only CLI launcher
role/llmwiki.md   the LLM role (language work only, no tools)
seeds/            bootstrap documents
deploy/           instance installer, systemd units, nightly scripts
docs/             PRDs (V1..V12), EPICs, ADRs, acceptance evidence
tests/            unit + HTTP tests (fakes for jiuwenswarm and gbrain MCP)
eval/             golden gates and benchmarks
```

## Design decisions

- **D-5** — change sets are the only write path to L2 pages; every edit (model,
  human, dream) is recorded and auditable
- **ADR-001** — one Huawei Cloud MaaS key for everything; self-hosted e5-small
  embeddings instead of a second embedding vendor
- Full decision log: `docs/adr/`, requirements history: `docs/PRD_*.md`

## License

Internal project material. Third-party attributions (where applicable) are kept
next to the code that reuses them.
