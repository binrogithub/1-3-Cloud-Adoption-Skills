# AI

AI covers model consumption, AI infrastructure, development productivity, agent platforms, data engineering for AI, model adaptation, governance, and AI applications. It provides the domain structure for turning AI capabilities into reusable cloud adoption skills and delivery assets.

This domain contains Level 2 use cases for AI-oriented Huawei Cloud adoption skills:

- [MaaS and Token Services](./MaaS-and-Token-Services/README.md): Consume model APIs and token-based AI services with attention to model choice, cost, and latency.
- [AI Infrastructure](./AI-Infrastructure/README.md): Build the compute, platform, and environment foundation for training and inference workloads.
- [AI Coding](./AI-Coding/README.md): Apply AI to software delivery through coding assistance, code generation, refactoring support, and engineering productivity improvement.
- [AI Development](./AI-Development/README.md): Improve engineering productivity through code assistants, AI coding, test generation, and development Q and A.
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
- [Claude Code SDK Agent MaaS Skill](./AI-Coding/Claude-Code-SDK-Agent-MaaS-Skill/README.md) — Adapt Claude Code or Claude Agent SDK to Huawei Cloud MaaS through a local compatible proxy.
- [Claude Code Huawei MaaS](./AI-Coding/claude-code-huawei-maas/README.md) — Route Claude Code through `claude-code-router` to Huawei Cloud MaaS with `glm-5.1`.
- [OpenHands Huawei MaaS](./AI-Coding/openhands-huawei-maas/README.md) — Configure OpenHands Web GUI or CLI to use Huawei Cloud MaaS through an OpenAI-compatible endpoint.
- [OpenShift Huawei Cloud MaaS Skill](./AI-Coding/OpenShift-Huawei-Cloud-MaaS-Skill/README.md) — Connect browser-based coding environments such as OpenShift Dev Spaces or Eclipse Che to Huawei Cloud MaaS.
- [Pi Huawei MaaS Cross Platform](./AI-Coding/pi-huawei-maas-cross-platform/README.md) — Configure Pi Coding Agent on Windows or Linux to use Huawei Cloud ModelArts MaaS.
- [LiteLLM SearXNG AICoding Gateway Single ECS](./AI-Development/LiteLLM-SearXNG-AICoding-Gateway-Single-ECS/README.md) — Single-host LiteLLM + SearXNG MCP gateway on Huawei Cloud ECS, wired into Claude Code via claude-code-router with `CLAUDE_CONFIG_DIR` isolation.
- [Langfuse LLM Observability](./Responsible-AI-and-Governance/langfuse-llm-observability/SKILL.md) — Add LLM tracing, prompt management, evaluations, and usage observability to MaaS-backed systems.
- [OpenLLMetry Huawei MaaS Agent](./Responsible-AI-and-Governance/openllmetry-huawei-maas-agent/SKILL.md) — Instrument MaaS-backed agents with OpenLLMetry and OpenTelemetry while protecting prompts and secrets.
- [MGC Cross-Region Migration](./host_migration/README.md) — Reuse an AI-guided migration workflow for Huawei Cloud host migration with SMS-first execution, rsync fallback, and packaged field evidence.
