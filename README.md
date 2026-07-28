# Huawei Cloud Adoption Skills

This repository defines a practical skill framework for Huawei Cloud adoption work. It is designed to help AI coding agents, delivery engineers, architects, and solution teams reuse Huawei Cloud best practices through scenario-based skill packages.

An AI skill in this repository is not just a prompt. It is a reusable capability unit built around a cloud scenario, where AI helps with understanding, design, migration, operations, development, analysis, or optimization.

Recent updates added the OpenCode MaaS Delegate Router for GLM-5.2/GLM-5.1 task-level routing, the Cursor MaaS Delegate Router for USER-GLOBAL Cursor task offload, the Copilot Huawei MaaS skill for VS Code GitHub Copilot Chat through OAI Compatible Copilot, the CodeArts Huawei MaaS skill for a `codearts-litellm` wrapper, the codex-huawei-maas skill for a side-by-side `codex-glm` command through an isolated CCR `/v1/responses` shim, the Codex MaaS Hybrid Router skill for `codex-forky` split routing, and the LiteLLM Huawei MaaS Proxy skill with an optional self-hosted SearXNG search MCP profile.

Each skill should include:

- Scenario: what business problem or cloud scenario it addresses
- Knowledge: what cloud products, architecture, and domain logic are required
- Tools: what AI models, APIs, scripts, platforms, or workflows are used
- Method: how AI is embedded into the delivery process
- Output and validation: what is produced and how the result is verified

## Agent Skill Index

Use this index when Codex, Claude Code, or another AI agent needs to locate the right reusable skill quickly. Start from the business scenario, then open the linked skill folder. The child skill `README.md` gives the repository-facing summary, while `SKILL.md` contains the agent-facing workflow and trigger rules when present.

For the latest additions, check the `AI / AI-Coding`, `Big Data`, and `Cloud Foundation` entries near the end of the index, including OpenCode MaaS Delegate Router, Cursor MaaS Delegate Router, Copilot Huawei MaaS, CodeArts Huawei MaaS, codex-huawei-maas, Codex MaaS Hybrid Router, LiteLLM Huawei MaaS Proxy, SEC EDGAR monitoring, and HTTP proxy SSH skills.

| # | Domain | Use Case | Skill | Use When |
| --- | --- | --- | --- | --- |
| 1 | Cloud Foundation | Security Foundation | [CFW Finance Skill](./Cloud-Foundation/Security-Foundation/CFW-Finance-Skill/README.md) | Configure Huawei Cloud Firewall for finance, banking, PCI DSS, IPS, ACL, logging, alarm, or compliance-oriented security baselines. |
| 2 | Cloud Foundation | Operations AIOps and Tool Interconnection | [AIOps Agent Skill](./Cloud-Foundation/Operations-AIOps-and-Tool-Interconnection/AIOps-Agent-Skill/README.md) | Build intelligent O&M agents that replace Splunk with CSS/OpenSearch, automate anomaly detection and remediation with LangGraph state machine, enforce L0-L3 action levels, and integrate LTS/CTS/AOM/CES for cross-service log correlation and runbook-driven auto-remediation on Huawei Cloud. |
| 3 | Application Modernization | Application Migration | [Kafka GaussDB Trading Skill](./Application-Modernization/Application-Migration/Kafka-GaussDB-Trading-Skill/README.md) | Design or migrate high-frequency transaction systems using DMS for Kafka plus GaussDB, Java consumers, idempotency, partitioning, retry, and DLQ patterns. |
| 4 | Application Modernization | Database Migration | [GaussDB Adaptation Skill](./Application-Modernization/Database-Migration/GaussDB-Adaptation-Skill/README.md) | Port SQL Server or PostgreSQL code to Huawei GaussDB or openGauss-compatible environments, including SQL dialect, driver, auth, and bulk-load adaptation. |
| 5 | Application Modernization | Database Migration | [SQLServer PostgreSQL Babelfish Finance Demo](./Application-Modernization/Database-Migration/SQLServer-postgreSQL-babelfish-finance-demo/Readme.md) | Run a finance-focused SQL Server to PostgreSQL migration demo through Babelfish, covering banking customers, accounts, payments, risk alerts, views, stored procedures, and parity validation. |
| 6 | Application Modernization | DevOps and PaaS | [Karmada K8s Switch Skill](./Application-Modernization/DevOps-and-PaaS/karmada-k8s-switch-skill/README.md) | Prepare a Karmada lab, install and verify Karmada, deploy multi-cluster failover PoCs, switch traffic, or validate cutover behavior. |
| 7 | Application Modernization | Mainframe Modernization | [Cobol2Java](./Application-Modernization/Mainframe%20Modernization/mainframe%20modernization%20-%20Cobol2Java/SKILL.md) | Migrate COBOL batch programs to Java, including CICS translation, JCL conversion, data structure mapping, and parity validation. |
| 8 | Big Data | Databricks Migration | [Databricks to Huawei Cloud Skill](./Big-Data/Databricks-to-Huawei-Cloud-Skill/README.md) | Migrate Databricks tables, notebooks, SQL warehouse flows, or Spark pipelines to OBS, MRS Spark, Hive, and curated Parquet patterns. |
| 9 | Big Data | Data Warehouse Migration | [Teradata to Huawei DWS Skill](./Big-Data/Data-Warehouse-Migration/Teradata-to-Huawei-DWS-Skill/README.md) | Build, migrate, validate, and optimize a Teradata-to-Huawei-Cloud-DWS finance warehouse demo with SQL compatibility scans, OBS load templates, report parity checks, and migration reports. |
| 10 | Big Data | Big Data Platform Migration and Upgrade | [MRS DWS Finance Skill](./Big-Data/Big-Data-Platform-Migration-and-Upgrade/MRS-DWS-Finance-Skill/README.md) | Build financial risk-control pipelines with OBS, MRS, and DWS for risk scoring, AML/KYC, anomaly detection, compliance, and reporting. |
| 11 | Big Data | Big Data Platform Migration and Upgrade | [Cloudera to Huawei Cloud MRS Migration Skill](./Big-Data/Big-Data-Platform-Migration-and-Upgrade/Cloudera-to-Huawei-MRS-Skill/README.md) | Migrate CDH or HDP Hadoop, Hive, Spark, and Impala workloads to Huawei Cloud MRS with OBS data landing, Hive external table migration, Spark SQL conversion, and parity validation. |
| 12 | Big Data | ChatBI and Intelligent Analytics | [Simple ChatBI Skill](./Big-Data/ChatBI-and-Intelligent-Analytics/Simple-ChatBI-Skill/README.md) | Build a conversational BI demo with natural language to SQL translation, metric question answering, and automated analysis on Huawei Cloud DWS. |
| 13 | Big Data | AI Knowledge Base | [CSS Autoscaling Benchmark Skill](./Big-Data/AI-Knowledge-Base/CSS-Autoscaling-Benchmark-Skill/README.md) | Benchmark and autoscaling test harness for Huawei Cloud CSS (OpenSearch): ingestion throughput, query latency, vector search quality, data-node horizontal autoscaling, and consolidated reports. |
| 14 | Big Data | End-to-End Process Monitoring | [Huawei Cloud SEC EDGAR Big Data POC](./Big-Data/Huawei%20Bigdata%20Real%20E2E%20Process%20monitoring/README.md) | Reproduce and operate a full Huawei Cloud SEC EDGAR monitoring PoC across OBS ingestion, MRS Spark processing, DWS loading, Superset dashboards, and a public lifecycle-monitoring website. |
| 15 | AI | AI Applications | [Telco Call Center AI Skill](./AI/AI-Applications/Telco-Call-Center-AI-Skill/README.md) | Build or pitch AI-powered telecom customer intelligence, AICC demos, call analytics, churn prediction, or executive POCs on Huawei Cloud. |
| 16 | AI | AI Applications | [Enterprise RAG Agent](./AI/AI-Applications/enterprise-rag-agent/SKILL.md) | Build enterprise RAG agents for regulated document search with RAGFlow parsing, LlamaIndex retrieval workflows, Huawei Cloud MaaS inference, OBS/CSS/ECS demo provisioning, and upload/search portal assets. |
| 17 | AI | AI Applications | [RAGFlow Huawei MaaS](./AI/AI-Applications/ragflow-huawei-maas/SKILL.md) | Deploy RAGFlow with Docker Compose, connect it to Huawei Cloud MaaS through the OpenAI-compatible provider, register `glm-5.1`, and validate UI/API/LLM calls without exposing keys. |
| 18 | AI | AI Applications | [CSS Log Query Assistant](./AI/AI-Applications/css-log-assistant/README.md) | Build a natural language log query assistant on Huawei Cloud CSS (Elasticsearch) + MaaS GLM 5.1 with Terraform infrastructure, synthetic logs, and Streamlit UI. |
| 19 | AI | AI Applications | [Contract Risk Analysis AI Skill](./AI/AI-Applications/Contract-Risk-Analysis-AI-Skill/README.md) | End-to-end OCR + LLM pipeline for document risk scoring with serverless architecture on Huawei Cloud. |
| 20 | AI | AI Applications | [Dify NL2SQL Docker](./AI/AI-Applications/dify-nl2sql-docker/README.md) | Build and operate a local Dify Workflow that converts natural language into safe read-only SQL through Docker Compose, LiteLLM/OpenAI-compatible models, and a PostgreSQL query gateway. |
| 21 | AI | Specialized Migration Operations | [MGC Cross-Region Migration](./AI/host_migration/README.md) | Execute and troubleshoot Huawei Cloud cross-region server migration with MGC/SMS and Terraform, including SMS-first execution, rsync fallback for `SMS.6504`, task cleanup, quota checks, and reusable postmortem assets. |
| 22 | AI | AI Coding | [CSS Code Search MCP](./AI/AI-Coding/Enterprise-MaaS-Foundation/CSS-Code-Search-MCP/README.md) | Provision a Huawei Cloud CSS cluster, index a code repository into CSS/OpenSearch, and expose it as a searchable MCP tool for claude-glm with search_code, list_skills, and get_file tools. |
| 23 | AI | AI Coding | [Claude Code MaaS Direct Router](./AI/AI-Coding/Enterprise-MaaS-Foundation/claude-code-maas-direct-router/README.md) | Configure the MaaS-only `claude-glm` command through claude-code-router and LiteLLM so Claude Code traffic routes directly to Huawei Cloud MaaS, with optional search and Claude Agent SDK proxy paths. |
| 24 | AI | Agent Platform | [Enterprise Agent Memory](./AI/Agent-Platform/enterprise-agent-memory-skill/README.md) | Build cross-session persistent memory for enterprise agents with hook-based capture, AI compression, tiered retrieval, privacy controls, and audit trails. |
| 25 | AI | Agent Platform | [Agent Context Compression and Retrieval](./AI/Agent-Platform/agent-context-compression-and-retrieval-skill/README.md) | Build automatic context compression and tiered recall for enterprise agents with recall probes, artifact probes, and token cost visibility. |
| 26 | AI | Agent Platform | [Project Memory RAG](./AI/Agent-Platform/project-memory-rag-skill/README.md) | Build project-level knowledge persistence that combines learned memory, document RAG, GraphRAG, MCP access, and skill-based procedural memory. |
| 27 | AI | Agent Platform | [HuaweiClaw](./AI/Agent-Platform/huaweiclaw/README.md) | Deploy a personal multi-agent Huawei Cloud operations and coding system with orchestration, memory, MCP tool routing, web cockpit, and chat interfaces. |
| 28 | AI | Responsible AI and Governance | [Langfuse LLM Observability](./AI/Responsible-AI-and-Governance/langfuse-llm-observability/SKILL.md) | Deploy or integrate Langfuse for LLM tracing, generations, usage, latency, cost, errors, evaluations, prompt management, and observability workflows. |
| 29 | AI | Responsible AI and Governance | [OpenLLMetry Huawei MaaS Agent](./AI/Responsible-AI-and-Governance/openllmetry-huawei-maas-agent/SKILL.md) | Instrument Huawei MaaS-backed agents with OpenLLMetry, Traceloop, and OpenTelemetry while preventing API keys and prompt content from leaking into telemetry. |
| 30 | AI | AI Infrastructure | [detectron2 Ascend NPU Demo](./AI/AI-Infrastructure/detectron2-ascend-demo.md) | Deploy and test detectron2 on Huawei Ascend 910B3 NPU (ModelArts) with COCO val2017 and OGNet oil/gas refinery inference demos, NPU compatibility patches, result packaging, and test report generation. |
| 31 | Cloud Foundation | Cross-Cloud and Hybrid Network | [Huawei ECS HTTP Proxy SSH Skill](./Cloud-Foundation/Cross-Cloud-and-Hybrid-Network/Huawei-ECS-HTTP-Proxy-SSH-Skill/README.md) | Run SSH commands on Huawei Cloud ECS through a corporate HTTP or HTTPS proxy when direct SSH is blocked, while avoiding persisted SSH passphrases, proxy passwords, private keys, and tokens. |
| 32 | AI | AI Coding | [LiteLLM Huawei MaaS Proxy](./AI/AI-Coding/Enterprise-MaaS-Foundation/LiteLLM-Huawei-MaaS-Proxy/README.md) | Deploy a single-host Docker Compose LiteLLM proxy for Huawei Cloud MaaS with PostgreSQL persistence, Prometheus metrics, Grafana dashboards, virtual key management, and custom TTFT/TPOT/ITL observability. Optional `search` profile adds a self-hosted SearXNG search MCP (`web_search`/`fetch_url`) and a claude-glm (claude-code-router) client wiring. |
| 33 | AI | AI Coding | [codex-huawei-maas](./AI/AI-Coding/Enterprise-MaaS-Foundation/codex-huawei-maas/README.md) | Configure a side-by-side `codex-glm` command that routes Codex CLI to Huawei Cloud MaaS `glm-5.1` through an isolated CCR `/v1/responses` shim, with optional LiteLLM search and vision routing. |
| 34 | AI | AI Coding | [codearts-huawei-maas](./AI/AI-Coding/Enterprise-MaaS-Foundation/codearts-huawei-maas/README.md) | Deploy the Huawei CodeArts CLI on macOS arm64 and add a `codearts-litellm` wrapper that routes CodeArts through an OpenAI-compatible LiteLLM gateway. |
| 35 | AI | AI Coding | [Copilot Huawei MaaS](./AI/AI-Coding/Enterprise-MaaS-Foundation/copilot-huawei-maas/SKILL.md) | Install, verify, diagnose, and harden GitHub Copilot Chat in VS Code when Huawei Cloud MaaS GLM or another Huawei MaaS OpenAI-compatible model is used through OAI Compatible Copilot. |
| 36 | AI | AI Coding | [Claude Code MaaS Hybrid Router](./AI/AI-Coding/Enterprise-MaaS-Foundation/claude-code-maas-hybrid-router/SKILL.md) | Configure `claude-forky` so Claude Code planning, image, and classifier traffic stays on Claude OAuth while tool/code execution routes to Huawei MaaS GLM through forky and LiteLLM. |
| 37 | AI | AI Coding | [Codex MaaS Hybrid Router](./AI/AI-Coding/Enterprise-MaaS-Foundation/codex-maas-hybrid-router/README.md) | Configure `codex-forky` so Codex CLI tool/code-execution turns route through forky to Huawei MaaS GLM while non-tool and image turns stay on Codex ChatGPT/OAuth. |
| 38 | AI | AI Coding | [Cursor MaaS Delegate Router](./AI/AI-Coding/Enterprise-MaaS-Foundation/cursor-maas-delegate-router/README.md) | Install USER-GLOBAL Cursor Rules, memory, hooks, and delegate/workflow runners so Cursor Agent stays as orchestrator while execution-class coding work routes to Huawei MaaS GLM. |
| 39 | AI | AI Coding | [OpenCode MaaS Delegate Router](./AI/AI-Coding/Enterprise-MaaS-Foundation/opencode-maas-delegate-router/README.md) | Configure OpenCode global provider, instructions, skills, and named subagents so GLM-5.2 handles premium orchestration while execution-class work routes to GLM-5.1 on the same Huawei MaaS provider. |

## How To Navigate This Repository

1. Identify the business scenario, not the model technique.
2. Choose the Level 1 domain: Cloud Foundation, Application Modernization, Big Data, or AI.
3. Choose the Level 2 use case folder that matches the delivery scenario.
4. Open the child skill folder when a concrete reusable package exists.
5. Read `README.md` for the human-readable overview and `SKILL.md` for the agent-facing workflow.
6. Use bundled `references/`, `scripts/`, `assets/`, or `examples/` only when the skill package provides them.

## Agent Runtime Support

The skill packages are written so they can be used by multiple AI coding agents.

- **Codex**: use `SKILL.md` as the agent-facing workflow, then load `references/` or run bundled scripts only when needed.
- **Claude Code**: use the same `SKILL.md` and reusable assets as task context. For Huawei Cloud MaaS-backed Claude Code setup, start from the Claude Code SDK Agent MaaS skill or the Claude Code MaaS Direct Router skill in the AI Coding domain.
- **Other coding agents**: use the repository index to locate the scenario package, then treat `README.md` or `Readme.md` as the human overview and `SKILL.md` as the operational instruction set.

## Level 1 Domains

The repository follows the `1+3` Huawei Cloud adoption domain structure:

- [Cloud Foundation](./Cloud-Foundation/README.md): baseline cloud governance, landing zones, networking, resilience, security, and operations.
- [Application Modernization](./Application-Modernization/README.md): migration, refactoring, platform modernization, DevOps, workspace, and database modernization.
- [Big Data](./Big-Data/README.md): data warehouse migration, big data platform transformation, governance, analytics, and AI knowledge base foundations.
- [AI](./AI/README.md): model consumption, AI infrastructure, development productivity, agent platforms, data engineering, governance, and AI applications.

## Level 2 Use Cases

Each Level 1 domain contains Level 2 use case directories. This layer groups skills by delivery scenarios such as landing zones, migration, data governance, agent platforms, AI coding, or AI knowledge base foundations.

Use the Level 2 folders as stable places to add future child skill packages. A child skill package should usually contain a short `README.md`, an optional `SKILL.md`, and reusable assets such as references, scripts, templates, or examples.

## Design Principles

This framework follows five principles:

1. Start from cloud scenarios, then map AI capabilities.
2. Every skill must connect to a real use case.
3. Every skill must become a reusable asset.
4. Every skill must have a maturity level.
5. Every skill must be measurable against business outcomes.

The goal is to organize skills by business value, cloud scenario, and delivery action instead of organizing them only by model techniques such as prompting, RAG, agents, or fine-tuning.

## General Skills

General Skills are the common foundation required across all Huawei Cloud adoption work. They are not limited to one cloud service, one project type, or one delivery team.

### G1. Scenario Understanding and Requirement Abstraction

Translate customer requirements into a structured view of the current system, process pain points, possible AI intervention points, and the expected pull on cloud resource consumption.

### G2. AI Interaction and Prompt Design

Use AI effectively through structured questioning, output control, multi-turn clarification, role setting, constraint injection, and result verification.

### G3. Cloud Knowledge Retrieval and Knowledge Injection

Improve AI usefulness by connecting it with product documents, architecture knowledge, solution materials, FAQs, SOPs, and project experience through retrieval and knowledge update mechanisms.

### G4. API / SDK / CLI / IaC Automation

Move beyond answers into actions by using APIs, SDKs, CLI tools, Terraform, IaC patterns, and AI-assisted script generation and correction.

### G5. Security and Governance

Keep skill execution safe and controllable through identity and permission management, sensitive data protection, auditability, output control, model usage boundaries, and compliance awareness.

### G6. Observability, Evaluation, and Optimization

Measure and improve skills through accuracy, success rate, latency, cost, token consumption, task completion rate, and human replacement efficiency.

### G7. Integration and Workflow Orchestration

Embed AI into delivery workflows by connecting it with IDEs, DevOps pipelines, ticketing systems, monitoring systems, data platforms, and agent or workflow orchestration patterns.

### G8. Assetization and Replication

Turn every skill into repeatable assets such as Skill Cards, demo scripts, SOPs, training content, PoC templates, and replication templates.

## Skill Levels

Each skill should have a clear maturity level:

- Level 1. Understand: explain the scenario, required knowledge, and expected outputs
- Level 2. Execute: apply the skill in a real delivery task with repeatable steps
- Level 3. Replicate: package the skill into reusable assets that can be copied across projects

The level should reflect delivery capability, not just awareness or training attendance.

## Required Skill Assets

Each skill should eventually be documented and packaged into reusable outputs:

- Solution material
- Demo
- Scripts
- Best practices
- Test report
- FAQ and troubleshooting
- Reusable template

## Business Value Alignment

The framework is intended to support:

- Top project breakthrough
- PoC success
- Commercial replication
- Revenue growth
- Asset accumulation

This repository starts with a general framework and grows through domain-specific, use-case-specific Huawei Cloud Adoption Skills.
