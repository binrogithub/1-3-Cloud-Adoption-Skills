# Upstream issue draft — JiuwenSwarm 0.2.3, R-6

**Title:** Custom `.md` roles crash on dispatch in `--mode agent` ('str' object has no attribute 'name')

**Environment:** JiuwenSwarm 0.2.3 (uv tool), Ubuntu 24.04, reproduced on host 247
with a dedicated instance (own JIUWENSWARM_DATA_DIR), 2026-09-23.

**Steps:**
1. Install a custom role `<data>/agents/foo.md` (frontmatter: name/description/
   when_to_use/tools/max_iterations) and enable it via `react.subagents.foo.enabled: true`.
2. Run `jiuwenswarm chat --mode agent --jsonl "..."` with a prompt that triggers the role.

**Observed:** log line `[TaskTool] Subagent creation failed: type=foo,
error='str' object has no attribute 'name'`; the sub-agent result is `""`; the main
agent then answers by itself, uncited, with no indication of the failure in the final
output. Exit code 0.

**Root cause (source reading):** `_agent_def_to_subagent_config` passes tool-name
strings into `SubAgentConfig.tools`, which expects ToolCard objects.

**Expected:** either custom roles work in agent mode, or dispatch fails loudly with a
non-zero exit / error event. Silent main-agent substitution is the dangerous part.

**Workaround used by LLMWiki:** `--mode code` (CodeAgentRail/AgentTool filters real
ToolCards) + fail-closed event parsing (no successful Agent tool result with the role's
agent_id → serve nothing). Raw event streams attached in docs/evidence/smoke-2026-09-23/.
