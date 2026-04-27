# Demo Design Patterns — Telco Call Center AI

## The Two-Act Narrative Structure

Executive demos are not feature showcases. They are stories that create urgency and show a path forward.

### Act 1: The Symptom (Demo 1 — Customer Intelligence)

**Opening (60 seconds):** Live demo running immediately. No title slide. No agenda. No introductions.

Show the operator's own simulated call center data flowing through the dashboard. A customer is calling to cancel. The AI detects churn risk in real-time.

**The pain:** "You're losing <X> subscribers per month. Your call center agents handle <Y> calls daily. Each call contains a cancellation signal, but you're blind to it. This customer just told your agent they're switching to <competitor> because of price. Your agent noted 'customer satisfied' and moved to the next call."

**The cost:** Frame churn in revenue terms. A 2% monthly churn on a 4M subscriber base = 80K subscribers/month × $30 ARPU = $2.4M/month revenue at risk.

**The demo shows:** Real-time transcription → churn risk detection → recommended retention action. All from a single call recording.

### Act 2: The Cure (Demo 2 — Agentic Engineering)

**Transition:** "Demo 1 told you what's happening. But knowing isn't enough. You need to act faster than your competitors."

**The insight:** The operator who ships features in weeks beats the operator who ships in months. AI-assisted development is the velocity lever.

**The demo shows:** Legacy code analysis (instant tech debt report) → AI-generated modernization code → AI-generated test suite. Three pipelines that compress months of engineering work into minutes.

**The close:** "Demo 1 was the symptom. Demo 2 is the cure. You detect churn with AI. You outrun competitors with AI-assisted development. Same platform. Same investment. Two outcomes."

## Demo Fallback Strategy

Live demos fail. The goal is graceful degradation that the audience never notices.

| Failure Mode | Fallback | Switch Time |
|---|---|---|
| GPU / ASR crash | Deterministic mode (precomputed transcripts) | Instant (env var) |
| LLM API timeout | Deterministic mode (precomputed analysis) | Instant (env var) |
| Network down | Pre-recorded video | <5 seconds |
| Dashboard 500 error | Pre-recorded video | <5 seconds |
| Docker service crash | Pre-recorded video + restart in background | <5 seconds |
| Venue wifi dead | Mobile hotspot (pre-configured) | <30 seconds |

### Fallback Setup Checklist

- [ ] `DEMO_MODE=deterministic` configured and tested
- [ ] Pre-recorded video of full demo flow recorded at 1080p
- [ ] Video loaded on presentation laptop (local file, not streaming)
- [ ] Mobile hotspot configured with same SSID as venue wifi (for seamless switch)
- [ ] Redis/database pre-populated with all demo queries (works offline)
- [ ] Browser tabs pre-loaded: Dashboard, Backup Video, Health Check terminal
- [ ] `Alt+Tab` from Dashboard to Backup Video is one keystroke (no mouse needed)

## Presentation Venue Dry-Run Checklist

Execute this at the venue 12-24 hours before the presentation:

```
[ ] SSH to ECS from venue wifi — latency <200ms
[ ] SSH to ECS from mobile hotspot — latency <500ms
[ ] curl http://<ecs-ip>:8000/health from venue wifi — <1s response
[ ] curl http://<ecs-ip>:3000 from venue wifi — page loads <3s
[ ] Run full demo scenario — all segments complete <30s
[ ] Test deterministic fallback — switch mode and verify
[ ] Play backup video — verify audio/video sync
[ ] Test Alt+Tab from live demo to backup video — <2s
[ ] Verify projector resolution — dashboard text readable at 1080p
[ ] Verify audio — demo audio (if any) audible in room
```

## Executive Communication Rules

1. **Never apologize for the demo.** If something breaks, switch to backup without comment. "Let me show you another view" → Alt+Tab to video.
2. **Never explain technology unless asked.** The CEO doesn't care about WebSocket vs REST. They care about churn reduction.
3. **Always connect features to money.** Every AI capability must map to revenue protected, cost reduced, or speed gained.
4. **Use the competitor's name.** "Claro Chile already does this. They have 12 months of lead." Fear is a stronger motivator than opportunity.
5. **The ask must be concrete.** "30 days. $X budget. <N> calls analyzed. Go/No-Go decision on day 30." Vague POC proposals don't close.
6. **Be the last speaker if possible.** The last presentation before a vote/decision has disproportionate influence.

## Demo Pacing Guidelines

| Section | Duration | Notes |
|---------|----------|-------|
| Opening (live demo) | 60s | No slides. Dashboard already running. |
| Act 1 (Customer Intelligence) | 3-4 min | Show 2-3 call scenarios. Highlight churn risk scores. |
| Bridge | 30s | "That's the symptom. Here's the cure." |
| Act 2 (Agentic Engineering) | 3-4 min | Show all 3 pipeline types. Highlight speed difference. |
| Business case | 2 min | Churn cost + engineering acceleration = ROI. |
| POC proposal | 60s | Clear ask. Clear timeline. Clear criteria. |
| Q&A | 5 min | Pre-prepared answers only. No ad-lib technical deep dives. |

Total: 15-17 minutes, leaving 3-5 min buffer.

## What NOT to Do

- Do not show a terminal or code editor during the demo unless it's part of the narrative
- Do not explain error messages or loading states — they shouldn't exist in deterministic mode
- Do not demo features the customer didn't ask about (stick to churn + velocity)
- Do not mention competitors by name in checked-in materials (use generic references)
- Do not promise production timelines during the demo — that's for the POC phase
- Do not let the demo run longer than 8 minutes total — attention spans are short
