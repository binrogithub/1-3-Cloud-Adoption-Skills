# Architecture — Telco Call Center AI

## System Overview

The demo runs on a single Huawei Cloud ECS GPU instance (Pi2.2xlarge.4, 16 vCPUs, 32GB RAM, NVIDIA T4 16GB). All services are containerized with Docker Compose. The architecture is intentionally single-node for demo simplicity — production would distribute across CCE clusters.

## Component Diagram

```
┌──────────────────────────────────────────────────────────┐
│  ECS GPU: Pi2.2xlarge.4  (la-north-2 / la-north-2a)     │
│  OS: Ubuntu 22.04                                        │
│                                                          │
│  ┌────────────────────┐                                  │
│  │  Qwen3-ASR 0.6B    │  ← GPU-accelerated (T4)         │
│  │  Port: 8001 (VPC)  │    Transcribes Spanish audio    │
│  │  REST API internal │    Output: JSON segments         │
│  └────────┬───────────┘                                  │
│           │ POST /transcribe                             │
│           ▼                                              │
│  ┌────────────────────────────────────┐                  │
│  │  Backend (FastAPI)                 │                  │
│  │  Port: 8000 (public)               │                  │
│  │                                    │                  │
│  │  Endpoints:                        │                  │
│  │  GET  /health                      │                  │
│  │  GET  /api/tasks                   │                  │
│  │  POST /api/tasks                   │                  │
│  │  GET  /api/dashboard/kpis          │                  │
│  │  WS   /ws                          │                  │
│  │                                    │                  │
│  │  Modes:                            │                  │
│  │  - live (ASR + LLM)               │                  │
│  │  - deterministic (precomputed)     │                  │
│  └──┬──────────────┬─────────────────┘                  │
│     │              │                                     │
│     │ REST         │ WebSocket                           │
│     ▼              ▼                                     │
│  ┌──────────┐  ┌──────────────────────────┐              │
│  │PostgreSQL│  │  Dashboard (Next.js 15)   │              │
│  │Port: 5432│  │  Port: 3000 (public)      │              │
│  │(local)   │  │                           │              │
│  └──────────┘  │  Pages:                   │              │
│                │  - Scenario selection     │              │
│                │  - Live transcript view   │              │
│                │  - Churn risk dashboard   │              │
│                │  - Code pipeline view     │              │
│                │  - KPI summary            │              │
│                └───────────────────────────┘              │
└──────────────────────┬───────────────────────────────────┘
                       │ HTTPS (TLS 1.3)
                       ▼
┌──────────────────────────────────────────────────────────┐
│  Huawei Cloud MaaS (Hong Kong)                            │
│                                                          │
│  Model: GLM-5.1 (754B MoE) or alternative                │
│  API:  /v1/chat/completions (OpenAI-compatible)           │
│                                                          │
│  Used for:                                               │
│  - Churn risk analysis from transcript                   │
│  - Emotion/sentiment detection                           │
│  - Agentic code generation (Demo 2)                      │
└──────────────────────────────────────────────────────────┘
```

## Data Flow — Demo 1 (Customer Intelligence)

```
1. Audio file (Spanish call recording) → Qwen3-ASR (local)
2. Qwen3-ASR → transcript JSON (segments with timestamps)
3. Backend → sends transcript + system prompt → MaaS API (GLM-5.1)
4. MaaS API → returns churn analysis JSON:
   {
     "churn_risk": "high|medium|low",
     "risk_factors": ["price_complaint", "service_issue", ...],
     "sentiment": "negative",
     "recommended_action": "retention_offer_premium",
     "confidence": 0.87
   }
5. Backend → broadcasts via WebSocket: task.started, call.segment.N, task.completed
6. Dashboard → renders transcript in real-time, updates churn risk indicator
```

## Data Flow — Demo 2 (Agentic Engineering)

```
1. User selects scenario: legacy_analysis | code_generation | test_generation
2. Backend → returns precomputed result (no LLM call in deterministic mode)
3. WebSocket: task.started → (4s simulated work) → task.completed
4. Dashboard:
   - Pipeline steps animate (Analyze → Generate → Test)
   - CodePanel renders result by type:
     - legacy_analysis: tech debt items, security issues, modernization plan
     - code_generation: diff view of generated code
     - test_generation: pass/fail table with coverage metrics
```

## Model Choices and Rationale

| Component | Choice | Rationale |
|-----------|--------|-----------|
| ASR | Qwen3-ASR 0.6B | Runs on single T4 (2.2GB VRAM). Good Spanish accuracy. Apache 2.0 license. Local deployment satisfies data sovereignty. |
| LLM | GLM-5.1 (MaaS) | 754B MoE, 200K context. Strong Spanish performance. SWE-Bench Pro 58.4. Zero data retention (API). |
| Embeddings | BGE-M3 (optional) | Multilingual. 1024-dim. Good Spanish retrieval. Only needed if adding vector search to demo. |
| Database | PostgreSQL 14 (local) | Zero latency for demo. GaussDB Vector for production if customer requires Huawei ecosystem. |

## Security Group Rules

| Direction | Port | Source | Purpose |
|-----------|------|--------|---------|
| Inbound | 22 | <admin-ip>/32 | SSH admin access |
| Inbound | 3000 | 0.0.0.0/0 | Dashboard (public demo) |
| Inbound | 8000 | 0.0.0.0/0 | Backend API (public demo) |
| Inbound | 8001 | 10.0.0.0/8 | ASR internal (VPC only) |
| Outbound | 443 | 0.0.0.0/0 | MaaS API calls |

## Environment Variables

```
# Backend (.env)
DEMO_MODE=deterministic          # live|deterministic
MAAS_API_KEY=<maas-api-key>
MAAS_API_URL=https://<maas-endpoint>/v1/chat/completions
MAAS_MODEL=glm-5.1
DB_HOST=localhost
DB_PORT=5432
DB_USER=<db-user>
DB_PASSWORD=<db-password>
DB_NAME=<db-name>

# Dashboard (docker-compose.yml)
NEXT_PUBLIC_API_URL=http://<ecs-ip>:8000        # NO /api suffix
NEXT_PUBLIC_WS_URL=ws://<ecs-ip>:8000/ws        # ws:// not http://
```

## Deterministic Fallback Mode

When `DEMO_MODE=deterministic`, the backend:

1. Returns precomputed transcripts (no ASR call)
2. Returns precomputed churn analysis (no LLM call)
3. Simulates processing delay (2s per segment for visual pacing)
4. Broadcasts the same WebSocket events as live mode

This ensures the demo never fails due to model API issues, network latency, or GPU memory exhaustion.

## Docker Compose Configuration

```yaml
# Demo 1 (with GPU)
version: '3.8'
services:
  qwen-asr:
    build: ./services/qwen-asr
    ports:
      - "127.0.0.1:8001:8001"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  backend:
    build: ./demo1/backend
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - qwen-asr

  dashboard:
    build:
      context: ./demo1/dashboard
      args:
        - NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
        - NEXT_PUBLIC_WS_URL=${NEXT_PUBLIC_WS_URL}
    ports:
      - "3000:3000"
    depends_on:
      - backend
```

```yaml
# Demo 2 (no GPU)
version: '3.8'
services:
  backend:
    build: ./services/backend
    ports:
      - "8000:8000"

  dashboard:
    build:
      context: ./services/dashboard
      args:
        - NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
    ports:
      - "3000:3000"
    depends_on:
      - backend
```

## Production Considerations (Beyond Demo)

For production POC or pilot, consider:

- **CCE (Cloud Container Engine)** instead of raw ECS for orchestration
- **GaussDB** instead of PostgreSQL for Huawei ecosystem integration
- **DMS for Kafka** for event streaming between ASR, analysis, and alerting services
- **OBS** for audio file storage and archival
- **Cloud Eye** for monitoring and alerting
- **WAF + CFW** for perimeter security
- **Separate GPU pool** for ASR inference at scale (multiple T4 or A100)
