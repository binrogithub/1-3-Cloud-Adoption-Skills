# Epics: MaaS AI Coding Smart Router

## P0: Commercial MVP

| Epic | Scope | Evidence |
| --- | --- | --- |
| SR-01 Virtual models | Support `meli-coding-fast`, `auto`, `deep`, `review`, `vision` | `tests/test_smart_routing.py` |
| SR-02 Task classifier | Metadata-first classification with prompt rule fallback | audit `task_type` |
| SR-03 Risk engine | `repo_risk`, `repo_tags`, repo/path keyword detection | audit `repo_risk`, `repo_tags` |
| SR-04 Context policy | 160K direct, 196K max, over-limit premium/RAG signal | audit `context_policy` |
| SR-05 Routing policy | GLM execution pool, premium reasoning pool, vision pool | audit `route_reason`, `internal_route_model` |
| SR-06 Fallback policy | retry/test/latency/error/queue signals upgrade to premium | audit `fallback_triggered`, `fallback_reason` |
| SR-07 Budget policy | near-limit execution workload prefers GLM | audit `budget_state` |
| SR-08 Telemetry | Namespaced metadata for dashboards and commercial reporting | `metadata.cc_glm52_guard` |

## P1: 60-90 Day Expansion

| Epic | Scope |
| --- | --- |
| SR-09 Capacity controller | Reserved GLM TPM, priority queues, queue-delay fallback |
| SR-10 Budget engine | Team/project budget state from LiteLLM spend controls |
| SR-11 Prompt packs | Unit test, docs, CI fix, refactor, repo summary templates |
| SR-12 Repo memory | RAG/file selection for >196K tasks |
| SR-13 Effectiveness loop | Cost per accepted task from CI result and developer acceptance |
| SR-14 Dashboards | GLM coverage, premium ratio, fallback, latency, TPM, cost |

## Current Implementation Notes

The current plugin implements P0 as a pre-call hook. It does not require a client router, fork, local proxy, or shadow traffic. The first release expects external systems to pass capacity and budget state through request metadata; later releases can source those signals directly from LiteLLM key/team budgets and router health.
