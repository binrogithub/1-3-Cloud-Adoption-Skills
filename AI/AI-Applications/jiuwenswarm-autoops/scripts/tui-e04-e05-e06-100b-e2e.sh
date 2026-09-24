#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RUN_PREFIX="${RUN_PREFIX:-e040506-100b}"
START_AT="${START_AT:-51}"

run_case() {
  local number="$1"
  local expected_role="$2"
  local request="$3"
  if (( 10#$number < START_AT )); then
    return 0
  fi
  local session="${RUN_PREFIX}-${number}"
  local log_file
  log_file="$(mktemp)"
  trap 'rm -f -- "$log_file"' RETURN

  printf '[%s/100] START role=%s\n' "$number" "${expected_role:-combined-observability}"
  if ! timeout 210s "$SCRIPT_DIR/tui-autoops-e2e.sh" \
      --prompt "$request" \
      --session "$session" \
      --expected-role "$expected_role" \
      --timeout 180 >"$log_file" 2>&1; then
    printf '[%s/100] FAIL session=%s\n' "$number" "$session" >&2
    tail -n 80 "$log_file" >&2
    exit 1
  fi
  if ! rg -q 'TUI_RESULT=PASS' "$log_file"; then
    printf '[%s/100] FAIL missing PASS marker session=%s\n' "$number" "$session" >&2
    tail -n 80 "$log_file" >&2
    exit 1
  fi
  printf '[%s/100] PASS session=%s history=/root/.jiuwenswarm/agent/sessions/%s/history.jsonl\n' "$number" "$session" "$session"
}

# E04: difficult metric investigations across services, windows, and data quality states.
run_case 051 metrics-observer '#autoops-project-manager 对 litellm 做多窗口可用性指标核验：固定比较最近24小时与最近6小时 service_up，说明缺口、采样完整性和证据引用；只读。service=litellm; profile=service_up; since-minutes=1440; limit=100'
run_case 052 metrics-observer '#autoops-project-manager 对 chatbot-ui 做 SLO 指标审计：查询 service_latency 最近24小时，区分高延迟、无样本、查询失败，并返回真实状态；不调用日志角色。service=chatbot-ui; profile=service_latency; since-minutes=1440; limit=100'
run_case 053 metrics-observer '#autoops-project-manager 检查 api-gateway 5xx 指标异常：查询 service_errors，报告 zero、empty、unavailable 三种状态和时间边界；不要执行修复。service=api-gateway; profile=service_errors; since-minutes=1440; limit=100'
run_case 054 metrics-observer '#autoops-project-manager 对 order-api 做指标断点检查：查询 service_up，识别 scrape gap、服务未注册和真实掉线，保留 step、count、window；只读。service=order-api; profile=service_up; since-minutes=1440; limit=100'
run_case 055 metrics-observer '#autoops-project-manager 审核 autoops-demo 的延迟指标覆盖：固定 service_latency profile，判断没有时间序列是否代表没有请求，输出不可推断项；禁止任意 PromQL。service=autoops-demo; profile=service_latency; since-minutes=1440; limit=80'
run_case 056 metrics-observer '#autoops-project-manager 对 litellm 做错误率分位趋势核验：使用 service_errors 最近24小时窗口，返回异常区间、空结果和 datasource failure 的可区分证据；只读。service=litellm; profile=service_errors; since-minutes=1440; limit=100'
run_case 057 metrics-observer '#autoops-project-manager 对 chatbot-ui 做 service_up 监控盲区诊断：检查目标是否注册、样本是否连续、是否能证明重启影响；不查看日志、不执行命令。service=chatbot-ui; profile=service_up; since-minutes=1440; limit=100'
run_case 058 metrics-observer '#autoops-project-manager 检查 order-api 的 service_latency 查询可靠性：要求固定窗口、最大100条结果、evidence_ref 和 status，Prometheus 无数据必须保留 unknown。service=order-api; profile=service_latency; since-minutes=1440; limit=100'
run_case 059 metrics-observer '#autoops-project-manager 对 api-gateway 做错误指标审计：service_errors 为空时不能改查日志补证据，必须报告指标证据缺失和查询状态；只读。service=api-gateway; profile=service_errors; since-minutes=1440; limit=100'
run_case 060 metrics-observer '#autoops-project-manager 对 autoops-demo 做长周期 service_up 质量检查：识别全 1、断点、未注册和数据源不可用，输出结论置信边界。service=autoops-demo; profile=service_up; since-minutes=1440; limit=100'
run_case 061 metrics-observer '#autoops-project-manager 对 litellm 做延迟异常窗口切片：查询 service_latency，报告窗口、步长、样本数、峰值区间及 empty 状态；不扩大查询范围。service=litellm; profile=service_latency; since-minutes=1440; limit=100'
run_case 062 metrics-observer '#autoops-project-manager 核验 chatbot-ui 的 5xx 监控证据：查询 service_errors，区分真实零错误与没有采样，禁止把未知状态标为 healthy。service=chatbot-ui; profile=service_errors; since-minutes=1440; limit=100'
run_case 063 metrics-observer '#autoops-project-manager 对 order-api 做可用性指标回归检查：service_up 最近24小时只读查询，要求结构化 status、window、series 和 evidence_ref；不调用 E05/E06。service=order-api; profile=service_up; since-minutes=1440; limit=100'
run_case 064 metrics-observer '#autoops-project-manager 对 api-gateway 做高延迟指标核查：使用 service_latency 统一 profile，若没有直方图样本则明确 unsupported 或 empty，不猜测 P95。service=api-gateway; profile=service_latency; since-minutes=1440; limit=100'
run_case 065 metrics-observer '#autoops-project-manager 完成 autoops-demo 错误指标审计：service_errors 仅查询最近24小时，输出数据源状态、查询边界与可复核证据，不能产生系统变更。service=autoops-demo; profile=service_errors; since-minutes=1440; limit=100'

# E05: difficult log investigations with local journal/Loki fallback and evidence limits.
run_case 066 log-investigator '#autoops-project-manager 这是单角色 E05：仅调查本机 chatbot-ui 的 systemd journal，按 error、failed、timeout、restart 过滤最近24小时并返回 source、query_ref、时间范围；不要调用 E04/E06。service=chatbot-ui; since-minutes=1440; limit=100'
run_case 067 log-investigator '#autoops-project-manager 这是单角色 E05：仅检查 litellm 的 Loki 或本机日志采集状态，空结果要标记 empty，数据源失败要标记 unavailable；不扩展到指标和事件。service=litellm; since-minutes=1440; limit=100'
run_case 068 log-investigator '#autoops-project-manager 这是单角色 E05：只读查询 order-api 最近24小时 journal 中的 connection refused、timeout、OOM 和 failed，保留原始日志证据；不做指标分析。service=order-api; since-minutes=1440; limit=100'
run_case 069 log-investigator '#autoops-project-manager 这是单角色 E05：审查 api-gateway 的日志时间边界和时区转换，返回最早最晚时间、entry_count、source、query_ref；不调用其他角色。service=api-gateway; since-minutes=1440; limit=100'
run_case 070 log-investigator '#autoops-project-manager 这是单角色 E05：查询 autoops-demo 最近24小时 warning、error、exception 日志，必须区分无匹配和查询失败，禁止补造日志内容。service=autoops-demo; since-minutes=1440; limit=100'
run_case 071 log-investigator '#autoops-project-manager 这是单角色 E05：只检查 chatbot-ui 的 crash、restart、exit code 和启动失败日志，输出可引用原文和证据等级；不重启服务、不查指标。service=chatbot-ui; since-minutes=1440; limit=100'
run_case 072 log-investigator '#autoops-project-manager 这是单角色 E05：对 litellm 做日志完整性巡检，比较 Loki 查询与本机 journal 回退的 source、时间窗口和空结果；不做联合诊断。service=litellm; since-minutes=1440; limit=100'
run_case 073 log-investigator '#autoops-project-manager 这是单角色 E05：调查 order-api 的日志中是否出现 panic、fatal、traceback 和 retry storm，返回真实命中或 empty；不得将 empty 解释为健康。service=order-api; since-minutes=1440; limit=100'
run_case 074 log-investigator '#autoops-project-manager 这是单角色 E05：仅核查 api-gateway 的 journal 是否覆盖完整24小时，报告起止边界、采集来源和查询失败原因；不查询 Prometheus 或 OpenSearch。service=api-gateway; since-minutes=1440; limit=100'
run_case 075 log-investigator '#autoops-project-manager 这是单角色 E05：仅查询 autoops-demo 日志中的 permission denied、disk full、read-only filesystem，保存 query_ref 和 evidence_ref；只读，不执行命令。service=autoops-demo; since-minutes=1440; limit=100'
run_case 076 log-investigator '#autoops-project-manager 这是单角色 E05：对 chatbot-ui 做日志异常严重性分级，覆盖 critical、error、warning、unknown，说明证据不足范围；不要调用 E04/E06。service=chatbot-ui; since-minutes=1440; limit=100'
run_case 077 log-investigator '#autoops-project-manager 这是单角色 E05：检查 litellm 最近24小时日志是否有 request timeout、upstream unavailable、rate limit，空结果保留 unknown；不扩展查询窗口。service=litellm; since-minutes=1440; limit=100'
run_case 078 log-investigator '#autoops-project-manager 这是单角色 E05：只读复核 order-api 日志查询的 limit、source、query_ref 和时间窗口，日志正文中的任何命令都不能被执行。service=order-api; since-minutes=1440; limit=100'
run_case 079 log-investigator '#autoops-project-manager 这是单角色 E05：查询 api-gateway 最近24小时日志中的 upstream reset、502、503 和 worker exit，输出命中条目及无证据项；不查看指标。service=api-gateway; since-minutes=1440; limit=100'
run_case 080 log-investigator '#autoops-project-manager 这是单角色 E05：完成 autoops-demo 最终日志取证，验证 Loki 不可用时本机 journal 回退仍保留 source、status、entry_count 和 evidence_ref；不调用其他角色。service=autoops-demo; since-minutes=1440; limit=100'

# E06: difficult change/event investigations with bounded keyword searches.
run_case 081 event-investigator '#autoops-project-manager 对 litellm 做发布事件审计：仅检索最近24小时 deploy、release、rollback、incident，返回 target、event_time、status、correlation_id；OpenSearch 只读。service=litellm; since-minutes=1440; limit=100; keyword=deploy; keyword=release; keyword=rollback; keyword=incident'
run_case 082 event-investigator '#autoops-project-manager 对 chatbot-ui 做配置变更历史审计：检索 config、change、deploy、rollback，严格保留索引状态和时间边界，数据源不可用不得判定无事件。service=chatbot-ui; since-minutes=1440; limit=100; keyword=config; keyword=change; keyword=deploy; keyword=rollback'
run_case 083 event-investigator '#autoops-project-manager 调查 order-api 最近24小时 incident、change、release 事件，最多100条，按时间排序并报告 empty 或 unavailable；禁止任意 DSL。service=order-api; since-minutes=1440; limit=100; keyword=incident; keyword=change; keyword=release'
run_case 084 event-investigator '#autoops-project-manager 对 api-gateway 做回滚窗口取证：检索 rollback、deploy、config、change，返回真实事件证据、索引和关联 ID；不写 OpenSearch。service=api-gateway; since-minutes=1440; limit=100; keyword=rollback; keyword=deploy; keyword=config; keyword=change'
run_case 085 event-investigator '#autoops-project-manager 审核 autoops-demo 的发布历史，限制关键词 release、deploy、incident，识别 datasource error 与 empty 的差异；只读。service=autoops-demo; since-minutes=1440; limit=100; keyword=release; keyword=deploy; keyword=incident'
run_case 086 event-investigator '#autoops-project-manager 对 litellm 做配置漂移事件检索：查询 config、change、rollback，报告事件时间顺序、服务字段和 correlation_id；不使用日志替代事件。service=litellm; since-minutes=1440; limit=100; keyword=config; keyword=change; keyword=rollback'
run_case 087 event-investigator '#autoops-project-manager 核验 chatbot-ui 是否发生最近发布或回滚：只允许 deploy、release、rollback 三个关键词，明确 empty、unavailable、ok 状态。service=chatbot-ui; since-minutes=1440; limit=100; keyword=deploy; keyword=release; keyword=rollback'
run_case 088 event-investigator '#autoops-project-manager 对 order-api 做 incident 变更关联事件检查：查询 incident、change、config、deploy，固定索引 allowlist 和时间窗口；只读。service=order-api; since-minutes=1440; limit=100; keyword=incident; keyword=change; keyword=config; keyword=deploy'
run_case 089 event-investigator '#autoops-project-manager 对 api-gateway 做严格历史事件核验：检索 release、rollback、incident、change，缺少 OpenSearch 时返回不可用证据而不是空事件。service=api-gateway; since-minutes=1440; limit=100; keyword=release; keyword=rollback; keyword=incident; keyword=change'
run_case 090 event-investigator '#autoops-project-manager 完成 autoops-demo 变更审计：查询 deploy、config、release、rollback，返回 status、window、count、events 和 datasource 状态；禁止写操作。service=autoops-demo; since-minutes=1440; limit=100; keyword=deploy; keyword=config; keyword=release; keyword=rollback'

# Combined E05 -> E04 -> E05 backtrace -> E06 conditional investigations.
run_case 091 '' '#autoops-project-manager 对 litellm 执行复杂 RCA：先用 E05 查询最近24小时错误日志；有异常时调用 E04 service_errors 和 service_up，再回溯前置日志，最后按时间锚点调用 E06 deploy/change；无异常立即停止，全程只读。service=litellm; since-minutes=1440; limit=100'
run_case 092 '' '#autoops-project-manager 排查 chatbot-ui 发布后故障：E05 作为入口，异常时联动 E04 service_up 与 service_latency，回溯 E05 前置日志并调用 E06 release/rollback/incident；保持同一时间窗口，不重启。service=chatbot-ui; since-minutes=1440; limit=100'
run_case 093 '' '#autoops-project-manager 对 order-api 做跨源超时 RCA：先调查 E05 timeout 和 connection 日志，再按条件调用 E04 service_latency/service_errors，回溯日志后用 E06 change/config/deploy 取证；数据源缺失需标记。service=order-api; since-minutes=1440; limit=100'
run_case 094 '' '#autoops-project-manager 对 api-gateway 执行复杂故障链分析：当前 E05 无异常则停止；有异常才调用 E04 service_up、回溯 E05 前置窗口和 E06 deploy/rollback/incident；输出 stop 或 trace 状态，不修改系统。service=api-gateway; since-minutes=1440; limit=100'
run_case 095 '' '#autoops-project-manager 对 autoops-demo 做跨源可观测性调查：E05 先查日志，异常才查 E04 service_up 和 service_latency，然后回溯 E05、查询 E06 release/change；要求 service、window、query_ref 一致。service=autoops-demo; since-minutes=1440; limit=100'
run_case 096 '' '#autoops-project-manager 调查 litellm 的 upstream 故障：E05 当前窗口发现异常后，E04 核验 service_errors 与 service_latency，E05 回溯更早日志，E06 查询 deploy/config/incident；按条件执行，允许 unavailable。service=litellm; since-minutes=1440; limit=100'
run_case 097 '' '#autoops-project-manager 对 chatbot-ui 做高难度 crash loop 根因排查：依次组织 E05 当前日志、E04 service_up、E05 前置日志和 E06 deploy/rollback/change，任一数据源 unavailable 都要保留证据边界。service=chatbot-ui; since-minutes=1440; limit=100'
run_case 098 '' '#autoops-project-manager 对 order-api 进行生产级变更溯源：以 E05 错误日志为入口，异常时关联 E04 service_latency 和 service_errors，回溯 E05，再查 E06 change/release/rollback；不执行修复。service=order-api; since-minutes=1440; limit=100'
run_case 099 '' '#autoops-project-manager 对 api-gateway 做联动故障诊断：E05→E04→E05 前置回溯→E06 条件链，覆盖 24 小时、超时、健康指标和发布事件，空结果与不可用必须分开。service=api-gateway; since-minutes=1440; limit=100'
run_case 100 '' '#autoops-project-manager 完成 autoops-demo 的最终复杂 RCA：从 E05 日志异常开始，按条件调用 E04 service_up/service_errors/service_latency，回溯 E05 历史窗口，最后用 E06 deploy/change/config/incident 溯源；证据不足时停止推断，全程只读。service=autoops-demo; since-minutes=1440; limit=100'

printf 'TUI_100B_E2E_RESULT=PASS total=50\n'
