---
name: glm-test-batch
description: Batch unit-test generation on the GLM execution pool (W2 fan-out). Use for "add tests for these N modules/files".
---
# GLM Test Batch (execution pool)

1. List target modules; verify scopes are disjoint; ensure the test runner works (`pytest --collect-only` or equivalent).
2. Manifest: brief_template task_type `unit_test_generation`, goal "write unit tests for ${scope} into the test dir, match existing test style", acceptance "<runner> ${scope_tests}" per item; top-level verify_cmd runs the whole suite.
3. `workflow '<manifest>'`, concurrency per key rpm (default 3).
4. In-session: review the aggregate report; finish premium remainder yourself; run the full suite once more before declaring done.
