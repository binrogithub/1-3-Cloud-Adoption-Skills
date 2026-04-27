# POC Strategy — Telco Call Center AI

## The POC Is the Product

For telecom operators, AI is a trust exercise. They've been pitched AI slideware for years. A well-structured POC is the only credible path to commercial conversion.

The POC must be:
- **Short** (30 days max — urgency drives decisions)
- **Scoped** (one use case, one team, clear boundaries)
- **Measurable** (go/no-go criteria agreed before day 1)
- **Low-risk** (fixed price, operator provides data only)
- **Replicable** (POC architecture = production architecture, scaled down)

## 30-Day POC Template

### Week 1: Foundation
- Provision Huawei Cloud environment (ECS GPU, MaaS, networking)
- Deploy ASR model (local, GPU-accelerated)
- Ingest operator's sample call recordings (<1,000 calls)
- Configure dashboard with operator's branding

### Week 2: Calibration
- Run ASR + LLM pipeline on real call data
- Operator SMEs review output: "Would you act on this?"
- Tune prompts, thresholds, risk categories
- Iterate daily with operator's call center team

### Week 3: Validation
- Run 1,000 calls through calibrated pipeline
- Compare AI churn predictions against actual outcomes (30-day lookback)
- Measure accuracy, precision, recall
- Document edge cases and failure modes

### Week 4: Decision
- Present results: accuracy metrics, cost analysis, ROI projection
- Demo the calibrated dashboard with operator's own data
- Deliver POC report with go/no-go recommendation
- If go: propose pilot scope (3 months, live call center integration)
- If no-go: document gaps and propose remediation timeline

## Go/No-Go Criteria

All criteria must be agreed and signed before POC starts.

| Criterion | Go Threshold | Measurement Method |
|-----------|-------------|-------------------|
| Churn prediction accuracy | >80% | Compare AI predictions vs 30-day actual churn |
| False positive rate | <25% | Flagged-but-retained / total flagged |
| ASR transcription accuracy (Spanish) | WER <8% | Manual transcription comparison (100 calls) |
| Processing latency | <5s per call | End-to-end: audio ingest → dashboard update |
| System uptime | >99% | Monitoring dashboard |
| Operator SME satisfaction | >4/5 | Weekly survey |

## Pricing Patterns

### Fixed-Price POC (Recommended for First Engagement)
- **Scope:** 1 use case, 30 days, <2,000 calls
- **Price range:** $40K-$80K USD
- **Includes:** Infrastructure, deployment, calibration, validation, final report
- **Excludes:** Production deployment, ongoing support, model fine-tuning
- **Rationale:** Removes budget uncertainty. Operator pays for outcome, not hours.

### Consumption-Based Pilot (For Follow-On)
- **Scope:** 1-3 use cases, 90 days, live call center integration
- **Price:** Base fee + per-call processing fee
- **Base fee:** $15K-$25K/month (infrastructure + support)
- **Per-call:** $0.02-$0.05/call analyzed
- **Rationale:** Aligns cost with value. Scales with adoption.

## POC Proposal Structure (1-Pager)

```
TO: <Operator Executive Sponsor>
FROM: <Huawei Cloud Team>
SUBJECT: AI Customer Intelligence POC Proposal

PROBLEM: <1 sentence — e.g., "$2.4M/month revenue at risk from undetected churn">

SOLUTION: AI-powered call center intelligence on Huawei Cloud
  - Real-time Spanish ASR (local, data sovereignty compliant)
  - Churn risk detection from call transcripts
  - Agentic engineering for faster feature delivery

SCOPE: 30-day POC
  - <N> calls analyzed
  - 1 use case (churn detection)
  - Operator provides: call recordings + SME time (4h/week)
  - Huawei provides: infrastructure, AI pipeline, dashboard, calibration

COST: $<X>K USD (fixed price)

TIMELINE: <Start Date> → <End Date>

GO/NO-GO CRITERIA:
  1. Churn prediction accuracy >80%
  2. ASR WER <8% (Spanish)
  3. Processing <5s per call
  4. SME satisfaction >4/5

NEXT STEP: Sign by <date>. Kickoff <date + 3 days>.

CONTACT: <name>, <title>, <phone>, <email>
```

## What NOT to Propose in a First POC

- Multi-cloud or hybrid architecture
- Custom model training or fine-tuning
- Integration with production call center systems (IVR, CRM)
- Real-time streaming (batch processing is sufficient)
- More than 2 use cases
- Fixed ongoing pricing (propose POC first, negotiate pilot separately)

## From POC to Production

The POC is the door opener. The real revenue is in the pilot and production phases:

| Phase | Duration | Scope | Typical Value |
|-------|----------|-------|---------------|
| **POC** | 30 days | 1 use case, offline data | $40K-$80K |
| **Pilot** | 90 days | 2-3 use cases, live integration | $150K-$300K |
| **Production** | Annual | Full platform, all call centers | $500K-$2M+/year |

The POC must prove technical feasibility. The pilot proves business value at scale. Production is where the recurring revenue lives.

## Competitive Positioning

| Competitor | Their Pitch | Counter |
|------------|------------|---------|
| AWS (Amazon Connect + Transcribe + Bedrock) | "Full AWS ecosystem" | Data leaves Mexico. No Spanish ASR fine-tuning. Higher per-call cost. |
| Azure (Speech Services + OpenAI) | "Enterprise AI" | OpenAI API has data retention concerns for regulated industries. |
| Google (CCAI + Gemini) | "Best AI models" | No Mexico region. Data sovereignty non-compliant. |
| Huawei Cloud | "Local ASR + sovereign AI" | ASR runs in Mexico. LLM via encrypted API. 10x cost advantage. |

The Huawei differentiator for LATAM telecom: **data sovereignty + cost**. Lead with that.
