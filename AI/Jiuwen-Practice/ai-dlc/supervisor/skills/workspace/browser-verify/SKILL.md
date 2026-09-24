---
name: browser-verify
description: Page-verification conduit — a dispatched role drives the pinned Playwright MCP server to verify a list of pages render and their assertions hold, rather than hand-rolling a DOM check. Called by plan.py browser-verify.
---

# browser-verify — page verification conduit

## What you are

You are the role verifying **the list of pages your dispatch prompt names**
against their stated assertions. The pages and the pinned Playwright MCP
root path are in your dispatch prompt; this skill is only the conduit for
how to drive the tool, not the list itself.

## What to run

Drive the pinned Playwright MCP server (the path your dispatch prompt
gives, under `<pin_root>/node_modules/@playwright/mcp`) against each named
page:

- navigate to the page,
- take an accessibility snapshot,
- check the HTTP status, the document title, and any selector-presence or
  text-content assertions your prompt names.

Write your findings to `browser-verify/report.md` in the repo root: one
row per page — pass or fail, with the failure reason when a page fails
(status, missing selector, missing text, unreachable). Do not improvise a
`curl`/`requests`/`html.parser` substitute — the whole point is the
accessibility-tree check Playwright MCP gives.

## If it fails

If the Playwright MCP server is unavailable or a page is unreachable, do
not improvise, do not guess, do not write a "looks correct" result. Follow
the stop protocol your dispatch prompt already gives you — this file does
not repeat it. Stop and report exactly what happened.


## Persist what you checked (P1-7 — exploration vs verification)

This skill is the *exploration* half: you drive MCP because you have
never seen this page. Verification is the other discipline. After a
page passes, write `browser-verify/spec.json` in the repo root — one
entry per page:

```json
{"pages": [{"path": "index.html", "title": "the exact title",
            "selectors": ["nav", "h1"], "texts": ["Coffee Guide"]}]}
```

Every later verification then replays deterministically, without a
model and without MCP:

```bash
python3 bin/plan.py browser-verify --repo <repo> --change <id>   --run-spec browser-verify/spec.json
```

Two attempts per page classify the verdict: pass (first attempt),
flake (fail-then-pass — suspicious, named, never silent), fail (both
attempts — the trace lands in the task record). One isolated browser
profile per attempt: session state never leaks.
