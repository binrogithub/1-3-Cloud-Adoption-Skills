# AI

AI covers model consumption, AI infrastructure, development productivity, agent platforms, data engineering for AI, model adaptation, governance, and AI applications. It provides the domain structure for turning AI capabilities into reusable cloud adoption skills and delivery assets.

This domain contains Level 2 use cases for AI-oriented Huawei Cloud adoption skills:

- [MaaS and Token Services](./MaaS-and-Token-Services/README.md): Consume model APIs and token-based AI services with attention to model choice, cost, and latency.
- [AI Infrastructure](./AI-Infrastructure/README.md): Build the compute, platform, and environment foundation for training and inference workloads.
- [AI Coding](./AI-Coding/README.md): Apply AI to software delivery through coding assistance, code generation, refactoring support, and engineering productivity improvement.
- [Agent Platform](./Agent-Platform/README.md): Orchestrate multi-agent workflows, tool calls, and automation patterns for business tasks.
- [Data Engineering for AI](./Data-Engineering-for-AI/README.md): Prepare prompts, knowledge bases, retrieval flows, and data pipelines that support AI applications.
- [Fine-Tuning and Model Adaptation](./Fine-Tuning-and-Model-Adaptation/README.md): Adapt models to domain requirements through data preparation, tuning, and evaluation.
- [Responsible AI and Governance](./Responsible-AI-and-Governance/README.md): Control model outputs, permissions, auditability, security, and compliance boundaries.
- [AI Applications](./AI-Applications/README.md): Build AI-powered business applications such as chatbots, assistants, AICC, and fraud-related solutions.

### Implemented Skills

- [Telco Call Center AI](./AI-Applications/Telco-Call-Center-AI-Skill/README.md) — Battle-tested pattern for telecom AI demos: customer intelligence + agentic engineering on Huawei Cloud ECS GPU. Includes executive POC strategy, deterministic fallback design, and Mexico regulatory compliance.
- [RAGFlow Huawei MaaS](./AI-Applications/ragflow-huawei-maas/SKILL.md) — Deploy RAGFlow with Huawei Cloud MaaS through the OpenAI-compatible provider and validate UI, API, and LLM integration safely.
- [CSS Log Query Assistant](./AI-Applications/css-log-assistant/README.md) — Build a natural language log query assistant on Huawei Cloud CSS and MaaS for Latin American delivery operations.
- [Dify NL2SQL Docker](./AI-Applications/dify-nl2sql-docker/README.md) — Build and operate a local Dify workflow that converts natural language into safe read-only SQL through Docker Compose, LiteLLM or another OpenAI-compatible model endpoint, and a PostgreSQL query gateway.
- [Claude Code MaaS Direct Router](./AI-Coding/Enterprise-MaaS-Foundation/claude-code-maas-direct-router/README.md) — Configure the MaaS-only `claude-glm` command through `claude-code-router` and LiteLLM so Claude Code traffic routes directly to Huawei Cloud MaaS, with optional search and Claude Agent SDK proxy paths.
- [Codex MaaS Hybrid Router](./AI-Coding/Enterprise-MaaS-Foundation/codex-maas-hybrid-router/README.md) — Configure `codex-forky` so Codex CLI tool/code-execution turns route through forky to Huawei MaaS GLM while non-tool and image turns stay on Codex ChatGPT/OAuth.
- [Cursor MaaS Delegate Router](./AI-Coding/Enterprise-MaaS-Foundation/cursor-maas-delegate-router/README.md) — Install USER-GLOBAL Cursor Rules, memory, hooks, and delegate/workflow runners so Cursor Agent stays as orchestrator while execution-class coding work routes to Huawei MaaS GLM.
- [OpenCode MaaS Delegate Router](./AI-Coding/Enterprise-MaaS-Foundation/opencode-maas-delegate-router/README.md) — Configure OpenCode global provider, instructions, skills, and named subagents so GLM-5.2 handles premium orchestration while execution-class work routes to GLM-5.1 on the same Huawei MaaS provider.
- [LiteLLM Huawei MaaS Proxy](./AI-Coding/Enterprise-MaaS-Foundation/LiteLLM-Huawei-MaaS-Proxy/README.md) — Docker Compose LiteLLM proxy for Huawei Cloud MaaS with PostgreSQL, Prometheus, and Grafana, plus an optional self-hosted SearXNG search MCP and claude-glm (claude-code-router) client wiring.
- [Langfuse LLM Observability](./Responsible-AI-and-Governance/langfuse-llm-observability/SKILL.md) — Add LLM tracing, prompt management, evaluations, and usage observability to MaaS-backed systems.
- [OpenLLMetry Huawei MaaS Agent](./Responsible-AI-and-Governance/openllmetry-huawei-maas-agent/SKILL.md) — Instrument MaaS-backed agents with OpenLLMetry and OpenTelemetry while protecting prompts and secrets.
- [MGC Cross-Region Migration](./host_migration/README.md) — Reuse an AI-guided migration workflow for Huawei Cloud host migration with SMS-first execution, rsync fallback, and packaged field evidence.
