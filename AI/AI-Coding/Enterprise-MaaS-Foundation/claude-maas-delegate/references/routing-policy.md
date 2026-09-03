# Delegation Routing Policy

Classify before constructing a brief. Ambiguous requests stay with the host agent.

Delegate only bounded, approved execution: implementation, testing, bug fix, mechanical refactor, CI repair, or documentation changes with an explicit scope and acceptance check.

Keep these tasks local:

- architecture, requirements, API or module-boundary decisions;
- security, credentials, access control, privacy, or key rotation;
- payment, billing, entitlement, or account actions;
- production incident response, outage triage, and operational mitigation;
- complex diagnosis or open-ended investigation;
- review that decides security or architecture policy;
- work that has failed twice, until the host agent has diagnosed and changed the plan.

Do not delegate classification itself. A request that combines design or diagnosis with implementation remains local until the host isolates a safe execution slice. Refactoring is delegated only when it is mechanical and does not redesign boundaries.

The host provider remains unchanged. This policy never directs changes to Codex, Copilot, Cursor, or OpenCode model, authentication, or provider configuration.

