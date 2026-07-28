---
name: glm-test-batch
description: MaaS-twin batch test generator on the GLM-5.1 execution pool. Use for generating unit tests across multiple modules and test data fixtures. Delegates bounded test-generation briefs to ds-executor on Huawei MaaS GLM-5.1.
---

# GLM Test Batch — MaaS Execution Pool Test Generator

Trigger this skill when the user needs tests generated for multiple modules.

## Process

1. Analyze the modules under test
2. Group bounded modules by existing test framework and conventions
3. For each group, delegate to `ds-executor` via Task tool with:
   - Source files to cover
   - Test framework and conventions
   - Existing test patterns to follow
   - Acceptance: test suite passes
4. After all groups complete, run the full test suite to verify no regressions
5. Report results: files changed, coverage improvement, pass/fail
