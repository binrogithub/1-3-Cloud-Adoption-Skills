# >>> forky-claude-routing >>>
# Route the plain `claude` command through forky (local proxy on :3458).
# Plan-mode + image turns → Claude Opus (OAuth); execution turns → GLM-5.2 (LiteLLM → Huawei MaaS).
# Managed by the Opus-advisor-MaaS-executor skill — edit via scripts/configure-forky.sh, not by hand.
export ANTHROPIC_BASE_URL="http://127.0.0.1:3458"
export ANTHROPIC_MODEL="claude-sonnet-4-6"
export ANTHROPIC_AUTH_TOKEN="forky-local"   # dummy; forky injects real OAuth (Opus) or EXEC_API_KEY (GLM)
# MaaS glm-5.2 硬输入上限 ~196608; Claude Code 默认按 200K 算 → 提前压缩,留出 8K 输出 + 一轮 tool result 空间
export CLAUDE_CODE_AUTO_COMPACT_WINDOW=180000
case ",${NO_PROXY:-}," in *,127.0.0.1,*) ;; *) export NO_PROXY="${NO_PROXY:+$NO_PROXY,}127.0.0.1,localhost" ;; esac
# <<< forky-claude-routing <<<
