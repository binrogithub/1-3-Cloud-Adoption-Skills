---
name: glm-repo-summary
description: MaaS-twin repo summarization on the GLM-5.1 execution pool. Use for generating repo-wide README updates, architecture docs, module overviews, and changelog summaries. Delegates to ds-executor on Huawei MaaS GLM-5.1.
---

# GLM Repo Summary — MaaS Execution Pool Summarization

Trigger this skill when the user needs a repo-wide summary, documentation update, or changelog.

## Process

1. Scope the summary (entire repo, specific module, recent changes)
2. Delegate to `ds-executor` subagent via Task tool with:
   - Scope definition
   - Output format (README, ARCHITECTURE.md, CHANGELOG.md)
   - Style guide / existing doc references
3. Review the output and integrate after verification
