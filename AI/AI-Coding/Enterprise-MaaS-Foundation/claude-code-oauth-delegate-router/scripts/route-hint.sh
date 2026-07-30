#!/usr/bin/env bash
# oauth-delegate-router C4: UserPromptSubmit hook — deterministic advisory.
# Reads hook JSON on stdin, prints a one-line route hint (added as context).
# Advisory only (Phase 1); never blocks.
PROMPT=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('prompt',''))" 2>/dev/null)
[ -z "$PROMPT" ] && exit 0
PREM='architect|架构|security|安全审查|incident|事故|生产事故|race condition|竞态条件|payment|支付|auth|认证|鉴权|pci|codeowners|protected path|受保护路径|infrastructure migration|基础设施迁移|screenshot|截图|image|图片'
EXEC='unit test|单测|测试生成|documentation|文档|repo summary|摘要|ci fix|refactor|重构|batch|批量|migrate|迁移|generate tests|review'
p=$(printf '%s' "$PROMPT" | grep -icE "$PREM" || true)
e=$(printf '%s' "$PROMPT" | grep -icE "$EXEC" || true)
if [ "$p" -gt 0 ]; then
  echo "[route-hint] premium-class signals present — handle in-session per hybrid policy."
elif [ "$e" -gt 0 ]; then
  echo "[route-hint] execution-class signals — delegate via \`delegate\`/\`workflow\` per hybrid policy unless premium signals emerge."
fi
exit 0
