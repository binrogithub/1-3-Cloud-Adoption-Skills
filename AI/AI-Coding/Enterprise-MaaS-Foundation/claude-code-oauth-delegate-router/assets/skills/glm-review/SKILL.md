---
name: glm-review
description: Repo/PR review on the GLM execution pool (low/medium-risk only). Use instead of built-in review commands when the diff does not touch payment/auth/pci/infra/migrations. High-risk review stays in-session per hybrid policy.
---
# GLM Review (execution pool)

1. Collect the diff scope: `git diff --stat <base>...HEAD` (or the PR file list). If any path matches payment/auth/pci/infra/migration or CODEOWNERS-protected paths — STOP, do the review in-session (premium).
2. Split files into disjoint groups (~5 files each). Build a `workflow` manifest:
   - brief_template task_type `pr_review`, goal "review ${scope} for correctness bugs, missing error handling, test gaps; report findings as a list with file:line", acceptance empty.
   - concurrency 3.
3. Run `workflow '<manifest>'` via Bash. Read items.jsonl from the run_dir.
4. Synthesize in-session: dedupe findings, rank by severity, verify the top findings yourself by reading the cited code before presenting.
