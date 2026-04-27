# Telco Regulatory Compliance — Mexico

## Why Data Sovereignty Matters for Telco AI

Mexican telecom operators handle call recordings that contain:
- Personally identifiable information (PII): names, phone numbers, addresses
- Financial data: payment methods, account numbers, billing disputes
- Sensitive personal data: health information, family details, political opinions

Under Mexican law, this data cannot freely leave the country.

## Key Regulations

### LFPDPPP (Ley Federal de Protección de Datos Personales en Posesión de los Particulares)

Mexico's primary data protection law. Key articles for AI systems:

| Article | Requirement | Implementation |
|---------|------------|----------------|
| Art. 6 | Data subject consent | Call recordings require explicit consent. "This call may be recorded for quality purposes" is sufficient for analysis. |
| Art. 13 | Privacy notice | Operator must inform subscribers their data may be analyzed by automated systems. |
| Art. 36 | Cross-border transfers | Data may only leave Mexico if: (a) the recipient country has adequate protection, (b) the operator has standard contractual clauses, or (c) explicit consent is obtained. |
| Art. 48 | Security measures | Operators must implement administrative, technical, and physical safeguards. |

**The ASR Must Run Locally.** Call recordings contain PII that cannot leave Mexico without complex legal arrangements. By running Qwen3-ASR on local GPU infrastructure, the raw audio never crosses the border. Only the transcript (text) is sent to the LLM API — and even that should be evaluated case-by-case.

### PROFECO (Procuraduría Federal del Consumidor)

Consumer protection agency. Relevant for AI analysis:

- AI-generated retention offers must not be misleading
- Customers must be informed if AI was used to make decisions about their account
- Call center agents using AI recommendations retain final decision authority

### IFT (Instituto Federal de Telecomunicaciones)

Telecom regulator. Relevant for call recording:

- Operators must retain call recordings for minimum periods (varies by service type)
- Call metadata (timestamps, durations, ANI/DNIS) has separate retention requirements
- AI analysis of call recordings does not replace regulatory retention obligations

## Architecture for Compliance

```
┌─────────────────────────────────────────────┐
│           MEXICO (na-south-1 / la-north-2)   │
│                                             │
│  Call Recording ──→ Qwen3-ASR (local GPU)   │
│                         │                   │
│                         │ Transcript (text)  │
│                         ▼                   │
│                    Backend API               │
│                         │                   │
│                         │ HTTPS (TLS 1.3)    │
└─────────────────────────┼───────────────────┘
                          │
                ┌─────────▼──────────┐
                │  MaaS API (HK/SG)   │
                │  LLM Inference      │
                │  GLM-5.1            │
                │                     │
                │  Data retention:     │
                │  Zero (API config)   │
                └────────────────────┘
```

**Key compliance properties:**

1. **Raw audio never leaves Mexico** — ASR processes locally
2. **Transcript is text, not audio** — Lower PII density, but still sensitive
3. **LLM API has zero data retention** — Configured in MaaS dashboard
4. **TLS 1.3 in transit** — All API calls encrypted
5. **No customer data stored in LLM provider logs** — Zero retention setting verified

## Data Classification for AI Processing

| Data Type | Classification | Can Leave Mexico? | Processing Location |
|-----------|---------------|-------------------|-------------------|
| Raw call audio | PII (sensitive) | No | Mexico (local GPU) |
| Transcript text | PII (moderate) | Case-by-case | Mexico → HK (if zero-retention API) |
| Churn risk score | Non-PII | Yes | Anywhere |
| Sentiment score | Non-PII | Yes | Anywhere |
| Call metadata (timestamp, duration) | Non-PII | Yes | Anywhere |
| Agent performance metrics | Non-PII | Yes | Anywhere |

## Data Minimization Principles

Apply these principles to reduce regulatory risk:

1. **Transcribe, don't store.** Process audio through ASR. Discard audio after transcription unless regulatory retention requires otherwise.
2. **Extract, don't transfer.** Send only the features needed for analysis (transcript text, not full customer profile).
3. **Aggregate, don't expose.** Dashboard shows aggregate metrics (churn rate, sentiment trends), never individual customer records.
4. **Purpose limitation.** POC data used only for calibration and validation. Not for training, not for resale.

## ASR Model: Why Local Deployment

| Option | Latency | Data Sovereignty | Cost | Accuracy (Spanish) |
|--------|---------|-----------------|------|-------------------|
| Qwen3-ASR (local GPU) | ~200ms | Yes | $0 (own infra) | Good (multilingual) |
| Huawei MaaS ASR API | ~500ms | No (leaves MX) | Per-call | Unknown |
| OpenAI Whisper API | ~1s | No (US servers) | $0.006/min | Good |
| Azure Speech Services | ~500ms | No (US/EU) | $1/hr | Good |

Local Qwen3-ASR is the only option that satisfies LFPDPPP data sovereignty for raw audio. The accuracy gap with commercial APIs is closing rapidly and can be addressed with fine-tuning on Mexican Spanish call center data (post-POC).

## Audit Trail Requirements

For POC and pilot phases, maintain:

- **Access logs:** Who accessed the dashboard, when, from what IP
- **Processing logs:** Which calls were analyzed, timestamps, model versions
- **Model versioning:** Which ASR model version, which LLM model version, which prompt template
- **Consent records:** Proof that analyzed calls had proper consent ("this call is recorded")

These logs are critical for PROFECO/LFPDPPP audits and for the operator's own compliance team.

## Common Regulatory Pitfalls

1. **Assuming "cloud" = "non-compliant."** Many operators believe any cloud AI violates data sovereignty. Educate that local compute + zero-retention API is compliant.
2. **Overlooking consent.** Call recordings from before AI implementation may not have consent for automated analysis. Work with operator's legal team on retroactive consent or data filtering.
3. **Storing transcripts outside Mexico.** Even text transcripts contain PII. Use local PostgreSQL. Only send to LLM API with zero-retention configured.
4. **Not documenting model decisions.** If AI recommends retention offers, document the logic. PROFECO can request this.
5. **Ignoring IFT retention.** AI analysis pipeline must not delete recordings that IFT requires retained.
