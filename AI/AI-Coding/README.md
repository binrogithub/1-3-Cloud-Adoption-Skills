# AI Coding

AI Coding focuses on applying AI directly to software engineering work, especially code generation, code explanation, refactoring support, debugging assistance, and productivity acceleration across the development lifecycle.

## Typical Skill Areas

- Code assistant adoption
- Code generation and completion
- Refactoring and optimization support
- Debugging and issue analysis
- Test case generation
- Developer workflow integration

## Expected Outputs

- AI coding workflow definition
- Reusable prompt and tool patterns
- Code quality and productivity baseline
- Validation report for engineering use cases

The skills are organized into two folders:

- **[Enterprise-MaaS-Foundation/](./Enterprise-MaaS-Foundation/)** — connectivity, proxy/gateway infrastructure, and tool/agent configuration that plug coding tools into Huawei Cloud MaaS.
- **[AI-Coding-Best-Practice/](./AI-Coding-Best-Practice/)** — engineering workflows, quality gates, and capability skills that consume the Foundation to do engineering work well.

## Enterprise MaaS Foundation

Connectivity and tool configuration: deploy a proxy/gateway, or point a coding tool at `glm-5.1` with an API key and base URL.

- [LiteLLM + SearXNG AI Coding Gateway (Single ECS)](./Enterprise-MaaS-Foundation/LiteLLM-SearXNG-AICoding-Gateway-Single-ECS/README.md): Deploy a single-ECS gateway that fronts Huawei Cloud MaaS through LiteLLM (FinOps, multi-user keys, caching), hosts SearXNG as a bearer-authenticated remote MCP, and wires Claude Code via `claude-code-router` (`claude-glm`) with `CLAUDE_CONFIG_DIR` isolation.
- [LiteLLM Huawei MaaS Proxy](./Enterprise-MaaS-Foundation/LiteLLM-Huawei-MaaS-Proxy/README.md): Deploy a single-host Docker Compose LiteLLM proxy for Huawei Cloud MaaS with PostgreSQL, Prometheus, Grafana, virtual key management, and custom TTFT/TPOT/ITL metrics — the observability-focused counterpart to the single-ECS gateway.
- [CSS Code Search MCP](./Enterprise-MaaS-Foundation/CSS-Code-Search-MCP/README.md): Deploy a Huawei Cloud CSS/OpenSearch code-search MCP server so `claude-glm` can search a repository's code and docs as native MCP tools.
- [maas-mcp-search-research-skill](./Enterprise-MaaS-Foundation/maas-mcp-search-research-skill/README.md): Run current web, code, vendor, and technical research for AI coding work by combining Huawei MaaS with pluggable MCP search, crawl, and deep-research tools.
- [Claude Code SDK Agent MaaS Skill](./Enterprise-MaaS-Foundation/Claude-Code-SDK-Agent-MaaS-Skill/README.md): Configure Claude Code or Claude Agent SDK through a local Anthropic Messages API compatible proxy backed by Huawei Cloud MaaS.
- [claude-code-huawei-maas](./Enterprise-MaaS-Foundation/claude-code-huawei-maas/README.md): Configure the Claude Code CLI command to use Huawei Cloud MaaS through `claude-code-router`, including `glm-5.1`, `$API_KEY` authentication, context length, wrapper setup, and verification.
- [codex-huawei-maas](./Enterprise-MaaS-Foundation/codex-huawei-maas/README.md): Configure a side-by-side `codex-glm` command that routes Codex CLI to Huawei Cloud MaaS `glm-5.1` through an isolated CCR `/v1/responses` shim, with optional LiteLLM search and vision routing.
- [openhands-huawei-maas](./Enterprise-MaaS-Foundation/openhands-huawei-maas/README.md): Configure OpenHands Web GUI or CLI to use Huawei Cloud MaaS through an OpenAI-compatible endpoint with `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, and safe MaaS connectivity validation.
- [pi-huawei-maas-cross-platform](./Enterprise-MaaS-Foundation/pi-huawei-maas-cross-platform/README.md): Configure Pi Coding Agent on Windows or Linux to use Huawei Cloud ModelArts MaaS through an OpenAI-compatible endpoint with `glm-5.1`.
- [OpenShift Huawei Cloud MaaS Skill](./Enterprise-MaaS-Foundation/OpenShift-Huawei-Cloud-MaaS-Skill/README.md): Integrate browser-based coding environments such as OpenShift Dev Spaces or Eclipse Che with Cline and Huawei Cloud MaaS through an OpenAI-compatible interface.
- [oh-my-opencode-slim-huawei-maas](./Enterprise-MaaS-Foundation/oh-my-opencode-slim-huawei-maas/README.md): Bootstrap a complete AI coding stack on a single host: deploy LiteLLM proxy, install opencode with oh-my-opencode-slim plugin, mint scoped virtual key, configure dual providers with four presets, fallback chains, and council, then validate end-to-end.

## AI Coding Best Practice

Engineering workflows and discipline that assume connectivity already exists and focus on *what good engineering looks like*.

### Engineering Capability Skills

These skills use MaaS-backed AI coding agents as enterprise engineering tools, not just personal productivity aids. Each skill enforces verification gates, anti-rationalization discipline, and cross-skill references. They drive continuous MaaS token consumption across daily engineering work.

- [maas-ai-coding-quality-skill](./AI-Coding-Best-Practice/maas-ai-coding-quality-skill/README.md): Enforce AI coding quality gates (lint, test, coverage, security) before code reaches review or production.
- [maas-code-review-and-security-skill](./AI-Coding-Best-Practice/maas-code-review-and-security-skill/README.md): Run structured code review and security audit with evidence-based findings and OWASP classification.
- [maas-spec-plan-build-test-skill](./AI-Coding-Best-Practice/maas-spec-plan-build-test-skill/README.md): Execute the Spec to Plan to Build to Test engineering workflow with gated phase transitions.
- [maas-legacy-code-migration-skill](./AI-Coding-Best-Practice/maas-legacy-code-migration-skill/README.md): Understand, refactor, and migrate legacy code (Java/COBOL/.NET) with reviewable batch transforms.
- [maas-screenshot-to-dashboard](./AI-Coding-Best-Practice/maas-screenshot-to-dashboard/README.md): End-to-end screenshot-to-dashboard pipeline using MaaS vision models for image analysis, anydesign for design token extraction, CCPM for planning, and React+Ant Design+ECharts for implementation with screenshot comparison iteration.
- [ccpm](./AI-Coding-Best-Practice/ccpm/README.md): Run spec-driven AI coding project management with PRDs, epics, GitHub Issues, worktrees, and parallel agent execution.

### Shared Resources

- [shared/](./AI-Coding-Best-Practice/shared/): Cross-cutting checklists (security, testing, performance, anti-rationalization), agent persona definitions (code-reviewer, security-auditor, test-engineer, migration-specialist), and MaaS integration patterns used by all engineering capability skills.

### Imported General Engineering Skills

These skills are selectively imported from `mattpocock/skills` and grouped into one reusable bundle because they strengthen AI coding discipline beyond vendor-specific setup.

- [Matt Pocock Engineering Skills](./AI-Coding-Best-Practice/skills/matt-pocock-engineering-skills/README.md): Curated bundle of 12 general engineering workflow skills adapted for AI coding work.
- [diagnose](./AI-Coding-Best-Practice/skills/matt-pocock-engineering-skills/diagnose/README.md): Structured debugging loop for hard bugs, flaky behavior, and performance regressions.
- [tdd](./AI-Coding-Best-Practice/skills/matt-pocock-engineering-skills/tdd/README.md): Test-driven delivery workflow with tracer bullets, red-green-refactor, and post-green cleanup.
- [triage](./AI-Coding-Best-Practice/skills/matt-pocock-engineering-skills/triage/README.md): Issue triage state machine that produces durable agent-ready briefs and explicit out-of-scope decisions.
- [to-prd](./AI-Coding-Best-Practice/skills/matt-pocock-engineering-skills/to-prd/README.md): Turn current context into a PRD suitable for downstream planning and implementation.
- [to-issues](./AI-Coding-Best-Practice/skills/matt-pocock-engineering-skills/to-issues/README.md): Break a PRD or plan into independently executable vertical-slice issues.
- [zoom-out](./AI-Coding-Best-Practice/skills/matt-pocock-engineering-skills/zoom-out/README.md): Explain a local code area in the context of the broader system.
- [improve-codebase-architecture](./AI-Coding-Best-Practice/skills/matt-pocock-engineering-skills/improve-codebase-architecture/README.md): Surface deepening opportunities to improve locality, seams, and AI navigability.
- [grill-with-docs](./AI-Coding-Best-Practice/skills/matt-pocock-engineering-skills/grill-with-docs/README.md): Stress-test a plan against the repo's domain language and ADRs while updating those docs inline.
- [grill-me](./AI-Coding-Best-Practice/skills/matt-pocock-engineering-skills/grill-me/README.md): Run a high-pressure clarification interview before implementation begins.
- [handoff](./AI-Coding-Best-Practice/skills/matt-pocock-engineering-skills/handoff/README.md): Compress current execution state into a reusable handoff artifact for another agent or engineer.
- [write-a-skill](./AI-Coding-Best-Practice/skills/matt-pocock-engineering-skills/write-a-skill/README.md): Author new reusable skills with a cleaner structure and supporting references.
- [setup-matt-pocock-skills](./AI-Coding-Best-Practice/skills/matt-pocock-engineering-skills/setup-matt-pocock-skills/README.md): Bootstrap the `docs/agents/` metadata and repo conventions consumed by the imported engineering workflow skills.

## Source Skill Repositories

The engineering capability skills are derived from patterns and practices in these open-source skill repositories. Some of the workflow skills above are directly imported and adapted from these upstream sources; others remain reference sources for future extensions.

| Repository | Key Contributions | When to Search |
|------------|-------------------|----------------|
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | Anti-rationalization tables, verification exit criteria, gated workflows (Define→Plan→Build→Verify→Review→Ship), agent personas (code-reviewer, security-auditor, test-engineer), reference checklists | Need more lifecycle skills (e.g., CI/CD, shipping, deprecation), deeper review checklists, or additional agent personas |
| [mattpocock/skills](https://github.com/mattpocock/skills) | Domain-awareness (CONTEXT.md, ADRs), vertical slicing, grilling pattern for spec validation, deep modules philosophy, TDD with tracer bullets | Need domain-model integration, spec grilling discipline, or architecture improvement patterns |
| [andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills) | Behavioral constraints: Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution | Need stronger behavioral guardrails for AI agents, or anti-patterns for over-engineering |
| [ComposioHQ/awesome-codex-skills](https://github.com/ComposioHQ/awesome-codex-skills) | Reviewable batch pattern for migrations, scripts as black boxes, 3-level progressive disclosure, degrees-of-freedom matching | Need migration patterns beyond Java/COBOL/.NET, action-execution skills (Composio CLI), or skill authoring tooling |
