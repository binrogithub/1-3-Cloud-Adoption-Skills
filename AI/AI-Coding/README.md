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

- [LiteLLM Huawei MaaS Proxy](./Enterprise-MaaS-Foundation/LiteLLM-Huawei-MaaS-Proxy/README.md): Deploy a single-host Docker Compose LiteLLM proxy for Huawei Cloud MaaS with PostgreSQL, Prometheus, Grafana, virtual key management, and custom TTFT/TPOT/ITL metrics. Includes an optional `search` profile that adds a self-hosted SearXNG search MCP (`web_search`/`fetch_url`) and a `claude-glm` (claude-code-router) client wiring with `CLAUDE_CONFIG_DIR` isolation.
- [CSS Code Search MCP](./Enterprise-MaaS-Foundation/CSS-Code-Search-MCP/README.md): Deploy a Huawei Cloud CSS/OpenSearch code-search MCP server so `claude-glm` can search a repository's code and docs as native MCP tools.
- [claude-code-huawei-maas](./Enterprise-MaaS-Foundation/claude-code-huawei-maas/README.md): Configure the Claude Code CLI command to use Huawei Cloud MaaS through `claude-code-router`, including `glm-5.1`, `$API_KEY` authentication, context length, wrapper setup, and verification. Also covers an optional Claude Agent SDK / standalone Anthropic Messages API proxy path backed directly by the MaaS OpenAI-compatible endpoint.
- [codex-huawei-maas](./Enterprise-MaaS-Foundation/codex-huawei-maas/README.md): Configure a side-by-side `codex-glm` command that routes Codex CLI to Huawei Cloud MaaS `glm-5.1` through an isolated CCR `/v1/responses` shim, with optional LiteLLM search and vision routing.
- [enterprise-context-engineering](./Enterprise-MaaS-Foundation/enterprise-context-engineering/README.md): Deploy a self-hosted context-engineering memory service so MaaS-backed coding agents (`claude-glm` / `codex-glm` / `opencode` / MiMo) remember, compact, and never lose context across sessions inside the `glm-5.1` window — Mem0 backbone, layered CLAUDE.md/AGENTS.md, proactive compaction, and a `claude-glm-recover` → episodic-memory bridge.

## AI Coding Best Practice

Engineering workflows and discipline that assume connectivity already exists and focus on *what good engineering looks like*.

> The earlier MaaS engineering-capability skills (`maas-ai-coding-quality-skill`,
> `maas-code-review-and-security-skill`, `maas-spec-plan-build-test-skill`,
> `maas-legacy-code-migration-skill`) and their `shared/` resources have been removed:
> their LLM orchestration was a thin per-file curl wrapper superseded by native
> multi-agent review/workflow tooling, and the durable engineering discipline they
> documented is better expressed as deterministic CI gates rather than prose skills.
