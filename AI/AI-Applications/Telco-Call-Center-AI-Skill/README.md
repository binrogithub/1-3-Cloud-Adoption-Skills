# Telco Call Center AI

## Skill Level

Level 2 — Execute (battle-tested on a real LATAM telecom POC engagement)

## Applicable Scenario

Telecom operator needs to demonstrate AI-powered customer intelligence to executive leadership. The goal is winning a 30-day Proof of Concept (POC) by showing live demos that connect AI capabilities to measurable business outcomes: churn reduction, engineering velocity, and competitive advantage.

## Business Problem Addressed

- **Churn blindness:** Operators lose 2-5% of subscribers monthly without understanding why. Call center interactions contain rich signal but go unanalyzed.
- **Engineering inertia:** Legacy systems and manual processes slow feature delivery to 6-12 month cycles. Competitors using AI-assisted development ship in weeks.
- **Executive skepticism:** C-level leaders have seen AI slideware before. They need to see working software, not promises.
- **Data sovereignty risk:** Regulated markets (Mexico LFPDPPP) require customer call data to stay on-premises, ruling out pure-cloud AI solutions.

## Required Cloud and Domain Knowledge

- Huawei Cloud ECS GPU (Pi2 family, T4 16GB)
- Huawei Cloud MaaS (Model as a Service) for LLM API access
- Docker and Docker Compose for application packaging
- Qwen3-ASR for speech-to-text (local deployment)
- GLM-5.1 or alternative LLM for natural language analysis
- FastAPI + Next.js for demo application stack
- WebSocket for real-time dashboard updates
- Telecom domain: churn analysis, call center operations, NPS, customer lifecycle
- Mexico regulatory: LFPDPPP, data sovereignty, PROFECO

## Required AI, Tools, and Platforms

- **ASR:** Qwen3-ASR 0.6B (local, GPU-accelerated)
- **LLM:** GLM-5.1 via Huawei Cloud MaaS (or DeepSeek-V3, Qwen3.6)
- **Embeddings:** BGE-M3 or sentence-transformers (optional, for vector search)
- **Infrastructure:** Huawei Cloud ECS + Terraform
- **Application:** Python FastAPI + TypeScript Next.js + Docker Compose
- **Database:** PostgreSQL (local), GaussDB Vector (optional, for production)
- **Monitoring:** curl-based smoke tests, WebSocket liveness probes

## Workflow / Method

1. **Infrastructure provisioning** — Terraform for ECS GPU + security groups. Bootstrap Docker manually (cloud-init unreliable on Huawei Cloud DNS).
2. **Demo 1 deployment** — ASR + backend + dashboard. Configure deterministic fallback mode. Pre-load Redis/database with sample queries.
3. **Demo 2 deployment** — Agentic engineering backend with 3 precomputed scenarios. No GPU required.
4. **Narrative design** — Two-act structure: Demo 1 = symptom (churn blindness), Demo 2 = cure (engineering velocity).
5. **Dry run** — Full run-through with backup video recording. Test deterministic fallback. Test mobile hotspot connectivity.
6. **Executive presentation** — Open with live demo in first 60 seconds. Backup slides only if demos fail. Close with clear POC proposal.

## Expected Outputs

- Working AI demos on Huawei Cloud accessible via public IP
- Deterministic fallback mode that never shows errors during live presentations
- Pre-recorded backup video of full demo flow
- POC proposal: 30-day scope, go/no-go criteria, cost estimate
- Executive narrative: two-act story connecting AI to business outcomes

## Validation Method

- `curl` health checks on all API endpoints (must return 200 + valid JSON)
- WebSocket connectivity test (dashboard must show live events)
- Scenario execution test (all demo scenarios must complete within timeout)
- Deterministic fallback test (demos must work with `DEMO_MODE=deterministic`, no models loaded)
- Backup video playback test (video must play without errors)

## Reusable Assets

- Terraform templates for ECS GPU provisioning
- Docker Compose files for single-command deployment
- Demo scenario scripts (telco call analytics, churn scoring)
- Executive presentation narrative template
- POC proposal template with go/no-go criteria
- Smoke test script for health verification

## KPIs / Evaluation Metrics

- **Demo success rate:** Percentage of live demos that complete without switching to fallback/backup
- **POC conversion:** Percentage of demo presentations that result in signed POC
- **Deployment time:** Time from zero to working demo (target: <4 hours for experienced operator)
- **Fallback resilience:** Time to switch from failed live demo to backup video (target: <5 seconds)

## Common Risks and Troubleshooting

- **Risk:** ASR model latency kills demo pacing → **Mitigation:** Pre-record audio, use deterministic fallback if latency >2s
- **Risk:** Network failure at venue → **Mitigation:** Mobile hotspot + pre-recorded backup video + Redis pre-load
- **Risk:** Dashboard shows errors due to stale NEXT_PUBLIC_ vars → **Mitigation:** Always rebuild with `--build`, never just restart
- **Risk:** SSH access blocked at venue → **Mitigation:** Test SSH from mobile hotspot during dry run, have console access backup
- **Risk:** LLM API rate limit or outage → **Mitigation:** Deterministic fallback bypasses all model APIs
