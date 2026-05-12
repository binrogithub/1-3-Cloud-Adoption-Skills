# Huawei Cloud Adoption Skills

This repository defines a practical skill framework for Huawei Cloud adoption work. It is designed to help AI coding agents, delivery engineers, architects, and solution teams reuse Huawei Cloud best practices through scenario-based skill packages.

An AI skill in this repository is not just a prompt. It is a reusable capability unit built around a cloud scenario, where AI helps with understanding, design, migration, operations, development, analysis, or optimization.

Each skill should include:

- Scenario: what business problem or cloud scenario it addresses
- Knowledge: what cloud products, architecture, and domain logic are required
- Tools: what AI models, APIs, scripts, platforms, or workflows are used
- Method: how AI is embedded into the delivery process
- Output and validation: what is produced and how the result is verified

## Agent Skill Index

Use this index when Codex, Claude Code, or another AI agent needs to locate the right reusable skill quickly. Start from the business scenario, then open the linked skill folder. The child skill `README.md` gives the repository-facing summary, while `SKILL.md` contains the agent-facing workflow and trigger rules when present.

| # | Domain | Use Case | Skill | Use When |
| --- | --- | --- | --- | --- |
| 1 | Cloud Foundation | Security Foundation | [CFW Finance Skill](./Cloud-Foundation/Security-Foundation/CFW-Finance-Skill/README.md) | Configure Huawei Cloud Firewall for finance, banking, PCI DSS, IPS, ACL, logging, alarm, or compliance-oriented security baselines. |
| 2 | Cloud Foundation | Operations AIOps and Tool Interconnection | [AIOps Agent Skill](./Cloud-Foundation/Operations-AIOps-and-Tool-Interconnection/AIOps-Agent-Skill/README.md) | Build intelligent O&M agents that replace Splunk with CSS/OpenSearch, automate anomaly detection and remediation with LangGraph state machine, enforce L0-L3 action levels, and integrate LTS/CTS/AOM/CES for cross-service log correlation and runbook-driven auto-remediation on Huawei Cloud. |
| 3 | Application Modernization | Application Migration | [Kafka GaussDB Trading Skill](./Application-Modernization/Application-Migration/Kafka-GaussDB-Trading-Skill/README.md) | Design or migrate high-frequency transaction systems using DMS for Kafka plus GaussDB, Java consumers, idempotency, partitioning, retry, and DLQ patterns. |
| 4 | Application Modernization | Database Migration | [GaussDB Adaptation Skill](./Application-Modernization/Database-Migration/GaussDB-Adaptation-Skill/README.md) | Port SQL Server or PostgreSQL code to Huawei GaussDB or openGauss-compatible environments, including SQL dialect, driver, auth, and bulk-load adaptation. |
| 5 | Application Modernization | Database Migration | [SQLServer PostgreSQL Babelfish Finance Demo](./Application-Modernization/Database-Migration/SQLServer-postgreSQL-babelfish-finance-demo/Readme.md) | Run a finance-focused SQL Server to PostgreSQL migration demo through Babelfish, covering banking customers, accounts, payments, risk alerts, views, stored procedures, and parity validation. |
| 6 | Application Modernization | DevOps and PaaS | [Karmada K8s Switch Skill](./Application-Modernization/DevOps-and-PaaS/karmada-k8s-switch-skill/README.md) | Prepare a Karmada lab, install and verify Karmada, deploy multi-cluster failover PoCs, switch traffic, or validate cutover behavior. |
| 7 | Application Modernization | Mainframe Modernization | [Cobol2Java](./Application-Modernization/Mainfame%20Modernization/mainframe%20modernization%20-%20Cobol2Java/SKILL.md) | Migrate COBOL batch programs to Java, including CICS translation, JCL conversion, data structure mapping, and parity validation. |
| 8 | Big Data | Databricks Migration | [Databricks to Huawei Cloud Skill](./Big-Data/Databricks-to-Huawei-Cloud-Skill/README.md) | Migrate Databricks tables, notebooks, SQL warehouse flows, or Spark pipelines to OBS, MRS Spark, Hive, and curated Parquet patterns. |
| 9 | Big Data | Data Warehouse Migration | [Teradata to Huawei DWS Skill](./Big-Data/Data-Warehouse-Migration/Teradata-to-Huawei-DWS-Skill/README.md) | Build, migrate, validate, and optimize a Teradata-to-Huawei-Cloud-DWS finance warehouse demo with SQL compatibility scans, OBS load templates, report parity checks, and migration reports. |
| 10 | Big Data | Big Data Platform Migration and Upgrade | [MRS DWS Finance Skill](./Big-Data/Big-Data-Platform-Migration-and-Upgrade/MRS-DWS-Finance-Skill/README.md) | Build financial risk-control pipelines with OBS, MRS, and DWS for risk scoring, AML/KYC, anomaly detection, compliance, and reporting. |
| 11 | Big Data | Big Data Platform Migration and Upgrade | [Cloudera to Huawei Cloud MRS Migration Skill](./Big-Data/Big-Data-Platform-Migration-and-Upgrade/Cloudera-to-Huawei-MRS-Skill/README.md) | Migrate CDH or HDP Hadoop, Hive, Spark, and Impala workloads to Huawei Cloud MRS with OBS data landing, Hive external table migration, Spark SQL conversion, and parity validation. |
| 12 | Big Data | ChatBI and Intelligent Analytics | [Simple ChatBI Skill](./Big-Data/ChatBI-and-Intelligent-Analytics/Simple-ChatBI-Skill/README.md) | Build a conversational BI demo with natural language to SQL translation, metric question answering, and automated analysis on Huawei Cloud DWS. |
| 13 | Big Data | AI Knowledge Base | [CSS Autoscaling Benchmark Skill](./Big-Data/AI-Knowledge-Base/CSS-Autoscaling-Benchmark-Skill/README.md) | Benchmark and autoscaling test harness for Huawei Cloud CSS (OpenSearch): ingestion throughput, query latency, vector search quality, data-node horizontal autoscaling, and consolidated reports. |
| 14 | AI | AI Applications | [Telco Call Center AI Skill](./AI/AI-Applications/Telco-Call-Center-AI-Skill/README.md) | Build or pitch AI-powered telecom customer intelligence, AICC demos, call analytics, churn prediction, or executive POCs on Huawei Cloud. |
| 15 | AI | AI Applications | [Enterprise RAG Agent](./AI/AI-Applications/enterprise-rag-agent/SKILL.md) | Build enterprise RAG agents for regulated document search with RAGFlow parsing, LlamaIndex retrieval workflows, Huawei Cloud MaaS inference, OBS/CSS/ECS demo provisioning, and upload/search portal assets. |
| 16 | AI | AI Applications | [RAGFlow Huawei MaaS](./AI/AI-Applications/ragflow-huawei-maas/SKILL.md) | Deploy RAGFlow with Docker Compose, connect it to Huawei Cloud MaaS through the OpenAI-compatible provider, register `glm-5.1`, and validate UI/API/LLM calls without exposing keys. |
| 17 | AI | AI Applications | [CSS Log Query Assistant](./AI/AI-Applications/css-log-assistant/README.md) | Build a natural language log query assistant on Huawei Cloud CSS (Elasticsearch) + MaaS GLM 5.1 with Terraform infrastructure, synthetic logs, and Streamlit UI. |
| 18 | AI | AI Applications | [Contract Risk Analysis AI Skill](./AI/AI-Applications/Contract-Risk-Analysis-AI-Skill/README.md) | End-to-end OCR + LLM pipeline for document risk scoring with serverless architecture on Huawei Cloud. |
| 19 | AI | AI Applications | [Dify NL2SQL Docker](./AI/AI-Applications/dify-nl2sql-docker/README.md) | Build and operate a local Dify Workflow that converts natural language into safe read-only SQL through Docker Compose, LiteLLM/OpenAI-compatible models, and a PostgreSQL query gateway. |
| 20 | AI | Specialized Migration Operations | [MGC Cross-Region Migration](./AI/host_migration/README.md) | Execute and troubleshoot Huawei Cloud cross-region server migration with MGC/SMS and Terraform, including SMS-first execution, rsync fallback for `SMS.6504`, task cleanup, quota checks, and reusable postmortem assets. |
| 21 | AI | AI Coding | [CSS Code Search MCP](./AI/AI-Coding/CSS-Code-Search-MCP/README.md) | Provision a Huawei Cloud CSS cluster, index a code repository into CSS/OpenSearch, and expose it as a searchable MCP tool for claude-glm with search_code, list_skills, and get_file tools. |
| 22 | AI | AI Coding | [Claude Code SDK Agent MaaS Skill](./AI/AI-Coding/Claude-Code-SDK-Agent-MaaS-Skill/README.md) | Configure Claude Code or Claude Agent SDK through a local Anthropic Messages API compatible proxy backed by Huawei Cloud MaaS. |
| 23 | AI | AI Coding | [Claude Code Huawei MaaS](./AI/AI-Coding/claude-code-huawei-maas/README.md) | Route Claude Code through claude-code-router to Huawei Cloud MaaS, configure `glm-5.1`, tune context/output limits, and optionally add Z.ai web-search-prime MCP search. |
| 24 | AI | AI Coding | [OpenHands Huawei MaaS](./AI/AI-Coding/openhands-huawei-maas/README.md) | Configure OpenHands Web GUI or CLI to use Huawei Cloud MaaS through an OpenAI-compatible endpoint with safe API key handling, local Docker startup, CLI setup, and MaaS connectivity verification. |
| 25 | AI | AI Coding | [OpenShift Huawei Cloud MaaS Skill](./AI/AI-Coding/OpenShift-Huawei-Cloud-MaaS-Skill/README.md) | Connect OpenShift Dev Spaces or Eclipse Che browser-based VS Code with Cline and Huawei Cloud MaaS through an OpenAI-compatible endpoint. |
| 26 | AI | AI Coding | [Pi Huawei MaaS Cross Platform](./AI/AI-Coding/pi-huawei-maas-cross-platform/README.md) | Configure Pi Coding Agent on Windows or Linux to use Huawei Cloud ModelArts MaaS through an OpenAI-compatible endpoint, preserving platform-specific config paths and model registry casing. |
| 27 | AI | AI Coding | [LiteLLM SearXNG AICoding Gateway Single ECS](./AI/AI-Coding/LiteLLM-SearXNG-AICoding-Gateway-Single-ECS/README.md) | Deploy a single Huawei Cloud ECS that fronts MaaS through LiteLLM, provides FinOps and multi-user controls, includes MaaS-only validation utilities, and exposes SearXNG as a bearer-auth remote MCP for Claude Code via claude-code-router. |
| 28 | AI | Responsible AI and Governance | [Langfuse LLM Observability](./AI/Responsible-AI-and-Governance/langfuse-llm-observability/SKILL.md) | Deploy or integrate Langfuse for LLM tracing, generations, usage, latency, cost, errors, evaluations, prompt management, and observability workflows. |
| 29 | AI | Responsible AI and Governance | [OpenLLMetry Huawei MaaS Agent](./AI/Responsible-AI-and-Governance/openllmetry-huawei-maas-agent/SKILL.md) | Instrument Huawei MaaS-backed agents with OpenLLMetry, Traceloop, and OpenTelemetry while preventing API keys and prompt content from leaking into telemetry. |
| 30 | AI | AI Infrastructure | [detectron2 Ascend NPU Demo](./AI/AI-Infrastructure/detectron2-ascend-demo.md) | Deploy and test detectron2 on Huawei Ascend 910B3 NPU (ModelArts) with COCO val2017 and OGNet oil/gas refinery inference demos, NPU compatibility patches, result packaging, and test report generation. |
| 31 | AI | AI Coding | [MaaS AI Coding Quality Skill](./AI/AI-Coding/maas-ai-coding-quality-skill/README.md) | Enforce AI coding quality gates (lint, test, coverage, security) with evidence-based exit criteria before code reaches review or production. |
| 32 | AI | AI Coding | [MaaS Code Review and Security Skill](./AI/AI-Coding/maas-code-review-and-security-skill/README.md) | Run structured code review and security audit with OWASP classification, secret detection, dependency audit, and evidence-based findings for compliance. |
| 33 | AI | AI Coding | [MaaS Spec-Plan-Build-Test Skill](./AI/AI-Coding/maas-spec-plan-build-test-skill/README.md) | Execute the Spec→Plan→Build→Test engineering workflow with gated phase transitions, human review between Plan and Build, and vertical slicing. |
| 34 | AI | AI Coding | [MaaS Legacy Code Migration Skill](./AI/AI-Coding/maas-legacy-code-migration-skill/README.md) | Understand, refactor, and migrate legacy code (Java/COBOL/.NET) with reviewable batch transforms, characterization tests, and behavior preservation. |

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
- **Claude Code**: use the same `SKILL.md` and reusable assets as task context. For Huawei Cloud MaaS-backed Claude Code setup, start from the Claude Code SDK Agent MaaS skill or the Claude Code Huawei MaaS router skill in the AI Coding domain.
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
