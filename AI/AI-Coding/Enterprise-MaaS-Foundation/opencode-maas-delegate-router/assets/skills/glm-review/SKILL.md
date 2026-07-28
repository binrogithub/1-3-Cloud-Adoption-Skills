---
name: glm-review
description: MaaS-twin reviewer on the GLM-5.1 execution pool. Use for low/medium-risk PR review, repo-wide review passes, and code quality checks. Delegates to the ds-reviewer subagent on Huawei MaaS GLM-5.1. NOT for high-risk paths (payment, auth, pci, infra, migrations) which must stay in-session premium.
---

# GLM Review — MaaS Execution Pool Reviewer

Trigger this skill when the user requests a code review that is low/medium risk.

## Process

1. Analyze the scope (files, diff, PR description)
2. If the scope touches payment/auth/pci/infra/migrations or CODEOWNERS-protected paths → **refuse** and escalate to premium in-session
3. Otherwise, delegate to `ds-reviewer` subagent via Task tool with:
   - Diff or file list
   - Review focus areas
   - Acceptance criteria

## Return

- Summary of findings
- Severity breakdown (critical/major/minor/nit)
- Specific file-level comments
- Overall recommendation (approve/needs-changes/block)
