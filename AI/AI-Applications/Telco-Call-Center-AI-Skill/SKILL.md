---
name: telco-call-center-ai
description: Use this skill when building or pitching an AI-powered customer intelligence platform for telecom operators on Huawei Cloud. TRIGGER when the user needs — AI contact center (AICC) demo architecture, telco churn prediction pipeline, ASR + LLM deployment for call analytics, executive POC strategy for telecom, data sovereignty compliance (Mexico LFPDPPP), demo design with deterministic fallback, or Huawei Cloud ECS GPU deployment for AI workloads. Also use when preparing telco executive presentations that combine live demos with strategic narrative.
---

# Telco Call Center AI

## Overview

This skill provides a complete, battle-tested pattern for deploying AI-powered customer intelligence demonstrations on Huawei Cloud for telecom operators. It covers the full lifecycle: architecture design, ECS GPU provisioning, ASR + LLM pipeline deployment, dashboard setup, demo narrative design, and executive POC strategy.

The skill is based on a real Huawei Cloud engagement with a major Latin American telecom operator. It captures what worked in production, not what works in documentation.

Two demos are covered:
- **Demo 1 — Customer Intelligence:** ASR transcription → LLM analysis → churn risk scoring → real-time dashboard. Proves the operator can detect at-risk subscribers from call center interactions.
- **Demo 2 — Agentic Engineering:** AI-powered code modernization with legacy analysis, code generation, and test generation pipelines. Proves AI can accelerate software delivery velocity.

Narrative arc: Demo 1 shows the symptom (churn detection gap). Demo 2 shows the permanent cure (engineering velocity to outrun competitors).

## Quick Start

Follow this sequence for a new telco engagement:

1. **Provision infrastructure** — ECS GPU (Pi2.2xlarge.4, T4 16GB) with Docker, security groups for ports 8000/3000
2. **Deploy Demo 1** — ASR + backend + dashboard with deterministic fallback mode
3. **Deploy Demo 2** — Agentic engineering backend + dashboard with precomputed scenarios
4. **Design the narrative** — Two-act structure: symptom → cure
5. **Prepare fallbacks** — Pre-recorded video, Redis pre-loaded keys, mobile hotspot
6. **Execute the pitch** — Open with live demo in first 60 seconds. Slides are backup only.

## Workflow Decision Tree

| Task shape | Route |
|---|---|
| **New telco POC engagement** | Read [references/poc-strategy.md](references/poc-strategy.md) for go-to-market, then follow full deploy workflow |
| **Deploy Demo 1 (Customer Intelligence)** | Read [references/architecture.md](references/architecture.md), run `scripts/deploy_ecs_demo.sh --demo=1` |
| **Deploy Demo 2 (Agentic Engineering)** | Read [references/architecture.md](references/architecture.md), run `scripts/deploy_ecs_demo.sh --demo=2` |
| **Prepare executive presentation** | Read [references/demo-design-patterns.md](references/demo-design-patterns.md) for narrative structure and fallback strategy |
| **Mexico regulatory compliance** | Read [references/telco-regulatory-mexico.md](references/telco-regulatory-mexico.md) for LFPDPPP, data sovereignty, PROFECO |
| **Troubleshoot deployment** | Run `scripts/smoke_check.sh` for health verification, check common pitfalls below |
| **Terraform infrastructure** | Use `terraform_ecs_gpu/` for repeatable ECS + security group provisioning |

## Core Rules

### R1: ASR Must Run Locally for Data Sovereignty

Telecom call recordings contain PII. In regulated markets (Mexico LFPDPPP), the ASR model must run on local infrastructure, not via cloud API. Deploy Qwen3-ASR on the ECS GPU instance itself. Only the LLM inference may call external APIs (MaaS) if properly secured.

### R2: Deterministic Fallback Is Mandatory

Live demos fail. Always implement `DEMO_MODE=deterministic` that returns precomputed, realistic results without any model dependency. The dashboard must never show an error state during a live presentation.

### R3: Two-Act Narrative, Not Feature List

Structure executive demos as a story:
- Act 1 (Demo 1): "Here's your symptom — you're losing subscribers and can't see why."
- Act 2 (Demo 2): "Here's the cure — AI-powered engineering that lets you outrun competitors."

Never present demos as feature showcases. Every feature ties back to a business pain point.

### R4: Open with Demo, Close with POC Proposal

First 60 seconds: live demo running. Last 60 seconds: clear, low-risk POC proposal with explicit go/no-go criteria. Slides exist only as backup if demos fail.

### R5: Pre-Recorded Backup Video

Record each demo at full quality before the presentation. If network, hardware, or model latency kills the live demo, switch to video within 5 seconds. The audience should not know the difference.

### R6: Never Hardcode Customer Data

All scripts and examples must use placeholders: `<ecs-ip>`, `<region>`, `<project-id>`, `<bucket>`. Never include real IPs, passwords, tokens, access keys, or customer names in checked-in files.

### R7: Huawei Cloud ECS SSH Is Root, Not Ubuntu

Huawei Cloud Ubuntu images default to `root` user for SSH keypair auth. The `ubuntu` user does not work. Always use `ssh -i <key> root@<ip>`.

### R8: NEXT_PUBLIC_ Env Vars Are Build-Time

In Next.js, any `NEXT_PUBLIC_*` environment variable is baked into the JavaScript bundle at build time. Changing `.env` requires `docker compose up -d --build --no-deps dashboard`. A simple restart is NOT enough.

### R9: API URL Must Not Include /api Suffix

The dashboard code appends `/api/tasks`, `/api/scenarios`, `/health` to the base URL. Setting `NEXT_PUBLIC_API_URL=http://<ip>:8000/api` causes double-prefix `/api/api/tasks` (404).

## Default Deliverables

When using this skill, produce:

1. **Infrastructure** — ECS GPU instance with Docker, security groups, and DNS configured
2. **Demo 1 backend** — FastAPI with ASR integration, churn analysis scenarios, WebSocket real-time events
3. **Demo 1 dashboard** — Next.js with scenario selection, live transcript view, churn risk visualization
4. **Demo 2 backend** — FastAPI with 3 precomputed scenarios (legacy analysis, code generation, test generation)
5. **Demo 2 dashboard** — Next.js with pipeline visualization, code diff panel, test results panel
6. **Smoke test report** — Health checks for all services, WebSocket connectivity, API endpoint validation
7. **Executive narrative** — Two-act story tying demos to business outcomes
8. **POC proposal** — 30-day scope, clear criteria, cost estimate, go/no-go gates

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                 ECS GPU (Pi2.2xlarge.4, T4 16GB)    │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Qwen3-ASR │  │ Backend  │  │   Dashboard      │  │
│  │  (local)  │  │ FastAPI  │  │   Next.js        │  │
│  │  :8001    │  │ :8000    │  │   :3000           │  │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
│       │             │                  │            │
│       │    REST     │    WebSocket     │            │
│       └────────────►◄──────────────────┘            │
│                     │                               │
│               ┌─────▼──────┐                        │
│               │ PostgreSQL  │                        │
│               │ (local)     │                        │
│               └────────────┘                        │
└─────────────────────┬───────────────────────────────┘
                      │
                      │ HTTPS (MaaS API)
                      ▼
┌─────────────────────────────────────────────────────┐
│              Huawei Cloud MaaS                       │
│              GLM-5.1 / alternative LLM              │
│              (Hong Kong region)                      │
└─────────────────────────────────────────────────────┘
```

For Demo 1: ASR transcribes audio locally → Backend sends transcript to LLM via MaaS → LLM returns churn analysis → Dashboard displays in real-time via WebSocket.

For Demo 2: No GPU required. Backend serves 3 precomputed scenarios directly. Dashboard renders pipeline steps with animated progress.

Both demos support `DEMO_MODE=deterministic` fallback that bypasses all model dependencies.

For detailed architecture, read [references/architecture.md](references/architecture.md).

## Common Pitfalls

### ECS Deployment
- **SSH user is `root`, not `ubuntu`** — Huawei Cloud Ubuntu images use root by default
- **DNS slow on Huawei Cloud internal resolvers** — Set `8.8.8.8` as primary nameserver in `/etc/resolv.conf` before Docker install
- **Cloud-init unreliable** — DNS may be unreachable during provisioning. Bootstrap manually after SSH.

### Docker
- **Backend Dockerfile on non-GPU instances** — Exclude `sentence-transformers` and `torch` from requirements (adds ~1.5GB, requires GPU). App handles ImportError gracefully.
- **NEXT_PUBLIC_API_URL is build-time** — Rebuild with `--build`, not just restart

### Dashboard
- **`l.filter is not a function` in console** — Backend returned error (not array) on `/api/tasks`. Fix backend endpoint.
- **WebSocket not connecting** — Check `NEXT_PUBLIC_WS_URL` uses `ws://` not `http://`
- **Stale URLs after IP change** — Rebuild dashboard image, simple restart won't update baked-in URLs

### Demo Reliability
- **Never rely on live models** — Always implement deterministic fallback
- **Always pre-record backup video** — Network/hardware/latency can fail
- **Pre-load Redis/Database** — If demo shows query results, pre-populate so it works offline

## Script Use

| Script | Purpose | Usage |
|--------|---------|-------|
| `deploy_ecs_demo.sh` | Full ECS bootstrap + Docker + app deploy | `bash scripts/deploy_ecs_demo.sh --demo=1\|2 --ip=<ecs-ip> --key=<ssh-key-path>` |
| `smoke_check.sh` | Health verification for all services | `bash scripts/smoke_check.sh --ip=<ecs-ip>` |
| `terraform_ecs_gpu/` | Terraform for Pi2 ECS + security groups | `cd terraform_ecs_gpu && terraform apply -var="region=<region>"` |

## Reference Use

Pull in only when the task demands:

- [references/architecture.md](references/architecture.md) — Detailed architecture, component interactions, data flow, model choices
- [references/demo-design-patterns.md](references/demo-design-patterns.md) — Demo narrative design, fallback strategies, dry-run checklist, video backup
- [references/poc-strategy.md](references/poc-strategy.md) — POC scoping, 30-day plan, go/no-go criteria, pricing patterns, executive communication
- [references/telco-regulatory-mexico.md](references/telco-regulatory-mexico.md) — LFPDPPP compliance, data sovereignty, ASR local deployment rationale, PROFECO considerations

## Validation Gates

| Gate | Check | Pass Criteria |
|------|-------|---------------|
| G1 | ECS reachable via SSH | `ssh root@<ecs-ip>` succeeds |
| G2 | Docker running | `docker ps` shows no errors |
| G3 | Backend healthy | `curl http://<ecs-ip>:8000/health` returns 200 with `demo_mode` |
| G4 | Dashboard serving | `curl -o /dev/null -w '%{http_code}' http://<ecs-ip>:3000/` returns 200 |
| G5 | API tasks endpoint | `curl http://<ecs-ip>:8000/api/tasks` returns JSON array |
| G6 | WebSocket connected | Dashboard console shows WebSocket open, no errors |
| G7 | Demo scenario runs | `curl -X POST http://<ecs-ip>:8000/api/tasks -H 'Content-Type: application/json' -d '{"type":"<scenario>"}'` returns task with segments |
| G8 | Deterministic fallback works | Set `DEMO_MODE=deterministic` and verify scenario runs without models |
| G9 | Backup video recorded | MP4 file exists and plays correctly |

## Sanitization Rules

- Never output real ECS IPs, passwords, SSH keys, or project IDs in deliverables
- Replace all identifiers with `<ecs-ip>`, `<region>`, `<project-id>`, `<bucket>`, `<ssh-key-path>`
- Strip customer names, account numbers, or internal hostnames from all examples
- All scripts must read credentials from environment variables or command-line flags only
- Demo scenarios may use synthetic data but must be labeled as such in presentations
- When referencing competitor names (e.g., AWS, Azure), use generic terms in checked-in files

## When Not to Overcomplicate

- For internal demos (not executive-facing), skip the two-act narrative and video backup
- For single-demo presentations, use Demo 1 alone (Customer Intelligence has strongest business impact)
- If the operator already has ASR infrastructure, skip local Qwen3-ASR deployment
- For non-regulated markets, MaaS-based ASR (no local deployment) is acceptable
- If the operator has no engineering team, skip Demo 2 entirely — focus on Demo 1
- Do not propose multi-region, Kubernetes, or microservices for a first demo — single ECS is sufficient
