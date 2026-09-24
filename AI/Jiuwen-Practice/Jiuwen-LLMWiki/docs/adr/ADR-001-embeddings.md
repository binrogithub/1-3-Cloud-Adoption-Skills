# ADR-001 — Embedding endpoint for LLMWiki (resolves blocker B-1)

| Field | Value |
|---|---|
| Status | **Accepted** (2026-09-24, host 247) |
| Context | PRD §5.2 B-1: GBrain vector search needs an embedding model; none existed on 247 |
| Decision | Self-hosted multilingual model in Docker on 247 (PRD option 2) |

## Options examined (PRD order of preference)

1. **MaaS-hosted embedding model — rejected.** Verified live against the account's
   model list (`GET /v1/models` on `api-ap-southeast-1.modelarts-maas.com`, 2026-09-24):
   exactly 6 models, all chat (`glm-5.1/5.2/5.3`, `deepseek-v4-flash/pro`, `qwen3-32b`).
   No embedding or rerank model is offered. The LiteLLM gateway on :4000 likewise
   exposes no embedding model (28 chat entries, PRD §5.1).
2. **Self-hosted multilingual model in Docker — chosen.** See below.
3. **External API for public sources only — fallback.** Not needed; option 2 works.
   Keep as the fallback if 247's RAM budget tightens (NFR-4).

## What was deployed (evidence, all on 2026-09-24)

- `llmwiki_embed` container: `ghcr.io/huggingface/text-embeddings-inference:cpu-latest`,
  model `intfloat/multilingual-e5-small` (384 dims), `--auto-truncate`, port
  `127.0.0.1:20081`, docker network `llmwiki_net`, HF cache volume `llmwiki_hfcache`,
  memory cap 2 GiB, `--restart unless-stopped`. Serves the OpenAI-compatible route
  `/v1/embeddings`.
- GBrain wired through its `litellm` provider recipe (OpenAI-compatible, trusts custom
  dimensions): `LITELLM_BASE_URL=http://127.0.0.1:20081/v1`,
  `--embedding-model litellm:intfloat/multilingual-e5-small --embedding-dimensions 384`.
  `content_chunks.embedding` migrated `vector(1024) → vector(384)` with gbrain's own
  destructive-migration recipe (the brain held 1 test page).
- Verified end to end: `gbrain embed --all` embeds; `gbrain query "tamanho máximo objeto
  OBS"` returns the English `services/obs` page with score 0.9589 through hybrid search
  (no more "vector search unavailable" warning).

## CPU throughput measurement (4 vCPU host, TEI CPU image, 2026-09-24)

| Measurement | Value |
|---|---|
| Single ~512-char document, cold | 61 ms |
| Single ~512-char document, warm | 40 ms |
| Batch of 32 × 512-char documents | 1.18 s → **27.1 docs/s** |
| Full re-embed of the current brain | < 1 s per page |

Sizing: a 5,000-page wiki (NFR-3) re-embeds in ~3 minutes; per-ask query embedding adds
~40 ms — negligible against the ~7 s model TTFT floor (PRD §5.4).

## Cross-language quality probe (the actual reason embeddings are needed, G3/AG-3)

Cosine similarity against an English wiki page, same endpoint, no prefixes:

| Query | cos |
|---|---|
| "maximum object size OBS" (EN) | 0.897 |
| "tamanho máximo objeto OBS" (PT) | 0.864 |
| "tamaño máximo de objeto OBS" (ES) | 0.861 |
| "GaussDB backup policy retention window" (unrelated) | 0.783 |

Cross-language scores sit within 0.04 of the same-language score, while unrelated
content separates by ~0.08 — enough for hybrid RRF ranking, which also fuses keyword
scores. e5 prefix asymmetry ("query:"/"passage:") is NOT applied because gbrain uses one
symmetric endpoint for both sides; this costs some separation. **Watch AG-3 results; if
cross-language consistency misses the 98% bar, re-evaluate the model.**

## Rejected first attempt (recorded so it is not retried blind)

`BAAI/bge-m3` (1024 dims, symmetric, stronger multilingual) crashes the TEI **CPU**
backend in a restart loop: it downloads the ONNX weights, dies silently during warm-up
(no error line, `OOMKilled=false`), at both 3 GiB and 5 GiB caps (69+ restarts
observed). If bge-m3 quality is ever required, serve it through a different runtime
(e.g. infinity or Xinference), not the TEI cpu image.

## Consequences

- Data residency (NFR-7): all embedding computation stays on 247; no external API is
  called; confidential sources never leave the host.
- Resource budget (NFR-4): embedding server capped at 2 GiB of the ≤ 4 GiB LLMWiki
  envelope; pgvector container capped at 512 MiB.
- gbrain's optional reranker stays disabled (would need a Voyage key — external US API,
  out of policy for this content).
