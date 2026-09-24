# Design: EPIC implementation pass — deltas against the PRD architecture

## Product surface
CLI (`bin/llmwiki`), web UI/API (:20080), systemd units + timers, eval gates. The
PRD's component view (§6.1) is unchanged; this pass fills it in.

## Information architecture
Wiki namespaces per wiki/SCHEMA.md; `_meta/` is the only glue-written namespace.
L1 sources immutable and content-addressed; seeds are labelled bootstrap digests.

## Visual direction
Single dark administrative theme delivered inline in llmwiki/web.py (no build
step, no CDN — stdlib constraint GL-O7). Ask / Browse / Review pages.

## Components
- grounding: claim kinds extended (units, currency fold, dates, word numbers);
  whitespace-normalised document-side matching.
- store: gbrain CLI templates verified against 0.53 (put needs --force to replace);
  slugs = mirror ∪ `gbrain list`; env plumbing for GBRAIN_HOME.
- pages: frontmatter parser reads gbrain's normalised YAML (block lists, folded scalars).
- pipeline: cached term/confidential index; confidential filtered before the pack;
  audit log; fileback; auto-approve policy; contradictions; reverify; lint page.
- web: SSE ask stream, token-gated mutations, /health with git SHA, /metrics.
- auth: hashed token store, four roles, action permission map.

## Acceptance
PRD §11 gates run live (ag0/ag2/ag3/ag5/ag6/ag8 PASS; ag1 on the starter golden
set; ag7 logged per-ask, full rehearsal deferred to the SA-written set). Plus the
unit suite (68) with a reverse case for every fix.
