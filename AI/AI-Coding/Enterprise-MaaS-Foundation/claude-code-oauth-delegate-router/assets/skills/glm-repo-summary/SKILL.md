---
name: glm-repo-summary
description: Repo-wide summarization/documentation on the GLM execution pool. Use for "summarize this repo/module", "write docs for X" over many files.
---
# GLM Repo Summary (execution pool)

1. Plan disjoint scopes: top-level dirs or modules (ls + git ls-files), ~1 scope per item.
2. Manifest: brief_template task_type `documentation`, goal "read ${scope} and write a concise summary (purpose, key files, public interfaces, dependencies) to ${out_file}", acceptance "test -s ${out_file}".
3. `workflow '<manifest>'`, concurrency 3.
4. In-session: read the per-scope summaries and synthesize the final document yourself.
