# Anti-Rationalization Table

Agents skip verification steps by rationalizing. Each excuse below is rebutted with a mandatory action. This table is referenced by all four MaaS AI Coding engineering capability skills.

## Universal Anti-Rationalizations

| Excuse | Rebuttal |
|--------|----------|
| "The code looks correct" | Run the test suite. Looking is not verification. |
| "This change is too small to break anything" | Small changes cause large failures. Run targeted tests. |
| "I already verified this in my head" | Heads are not CI. Execute the verification step. |
| "The existing tests cover this" | Prove it: run the specific test and paste the passing output. |
| "Adding a test would be over-engineering" | If the code matters enough to write, it matters enough to test. |
| "The security risk is theoretical" | All production vulnerabilities were once theoretical. Run the scan. |
| "This matches the existing style" | Run the linter. Style conformance is mechanical, not subjective. |
| "I'll add tests later" | Later never comes. Tests are a gate, not a follow-up. |
| "The refactor is safe because it preserves behavior" | Prove behavior preservation: run before/after comparison tests. |
| "This is a temporary workaround" | Temporary code lives forever. Document the tech debt and add a tracking issue. |

## How to Use This Table

1. When you catch yourself thinking any excuse in the left column, read the rebuttal.
2. Execute the rebuttal action. No exceptions.
3. If a team member uses an excuse, point them to this table.
4. Add project-specific rationalizations to the skill's SKILL.md, not here.

## Red Flags

Observable behavioral patterns indicating rationalization is occurring:

- Skipping a verification step without producing evidence
- Saying "looks good" without running a command
- Committing code without running the quality gate
- Marking a review as approved without reading the diff
- Closing a security finding as "accepted risk" without documenting the decision
- Writing implementation before specification
- Running a command that already succeeded without code changes since (wastes tokens; re-run only when code has changed)
