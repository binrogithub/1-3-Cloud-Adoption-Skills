# ADR-002 — Dedicated MaaS key for the LLMWiki instance

| Field | Value |
|---|---|
| Status | **Superseded — single-key decision** (Robin, 2026-09-24) |
| Context | PRD OQ-3, D-1: the dedicated JiuwenSwarm instance should carry its own ModelArts
  MaaS key so LLMWiki token spend is attributable, and the blast radius of a rotated or
  revoked key is one project. |
| Decision | Provision a **dedicated** MaaS key (same `glm-5.2` / ap-southeast-1 endpoint)
  for the dedicated instance's `runtime/jiuwen/config/.env` (mode 0600, written only by
  `deploy/install_instance.py`). |

## Current state (honest interim)

- The dedicated instance currently **reuses the shared key**: the installer copies
  `~/.jiuwenswarm/config/.env` into the isolated data dir (E1-S5 restore path). This is a
  documented deviation, not the target state: cost attribution is impossible and a key
  rotation for the shared instance would also take LLMWiki down.
- Migrating is a two-step operator action, no code change:
  1. Platform admin issues a new MaaS key for project "LLMWiki"
     (`MODEL_NAME=glm-5.2`, `API_BASE=https://api-ap-southeast-1.modelarts-maas.com/v1`,
     `MODEL_PROVIDER=OpenAI`).
  2. Write it to `runtime/jiuwen/config/.env` (0600) and
     `systemctl restart llmwiki-jiuwen-agentserver llmwiki-jiuwen-gateway`.

## Guardrails

- Keys live only in 0600 `.env` files under `runtime/` (gitignored). No key material in
  the repository, the wiki, the mirror, or any change set (checked by review).
- `doctor` reports the presence (never the content) of the instance `.env`.
- The ask log records token counts per request (NFR-6), which becomes per-project cost
  reporting once the key is dedicated.

## Postscript — 2026-09-24 model switch (operator action)

The dedicated instance's model was switched to **`deepseek-v4.1-flash`** at
`API_BASE=https://api-ap-southeast-1.modelarts-maas.com/openai/v1` (PRD primary model
was glm-5.2). The key supplied with the switch was verified byte-identical to the
shared key — so this postscript does NOT execute the decision above; the dedicated-key
action is still pending with the platform admin.

Verified after the switch: `doctor` green; live ask grounded and cited (TTFT ~3.1 s,
elapsed ~37 s vs 57–75 s on glm-5.2); AG-0 canary re-run PASS (positive dispatched+cited,
agent-mode reverse fails closed). One deepseek-specific behaviour surfaced and was fixed
in the glue prompt: the role read the "delegate to the sub-agent" wrapper literally and
prefixed "I don't have a sub-agent…" — `llmwiki/pipeline.py` now appends a note telling
the addressee to perform the task directly (commit on task/epic-impl-v1).


## Decision update — 2026-09-24 (Robin): ONE key, no dedicated key

Robin decided the platform runs with the single shared MaaS key; the dedicated-key
action above is cancelled. Consequences accepted: cost attribution stays coarse
(token counts remain per-request in ask.jsonl, but they are not separable by key),
and a rotation of the shared key takes LLMWiki down with everything else using it
(mitigation documented in the runbook: rewrite runtime/jiuwen/config/.env and
restart the two dedicated units). The key also now serves deepseek-v4.1-flash at
apiBase /openai/v1 for both the dedicated instance and the AI-DLC plane
(~/.openjiuwen/settings.json, which is plane-local and never touches the shared
instance's config).
