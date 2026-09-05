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
