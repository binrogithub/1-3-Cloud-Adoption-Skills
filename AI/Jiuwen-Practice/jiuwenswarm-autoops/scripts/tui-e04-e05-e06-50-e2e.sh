#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RUN_PREFIX="${RUN_PREFIX:-e040506-50}"
START_AT="${START_AT:-1}"

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

  printf '[%s/50] START role=%s\n' "$number" "${expected_role:-combined-observability}"
  if ! timeout 210s "$SCRIPT_DIR/tui-autoops-e2e.sh" \
      --prompt "$request" \
      --session "$session" \
      --expected-role "$expected_role" \
      --timeout 180 >"$log_file" 2>&1; then
    printf '[%s/50] FAIL session=%s\n' "$number" "$session" >&2
    tail -n 80 "$log_file" >&2
    exit 1
  fi
  if ! rg -q 'TUI_RESULT=PASS' "$log_file"; then
    printf '[%s/50] FAIL missing PASS marker session=%s\n' "$number" "$session" >&2
    tail -n 80 "$log_file" >&2
    exit 1
  fi
  printf '[%s/50] PASS session=%s history=/root/.jiuwenswarm/agent/sessions/%s/history.jsonl\n' "$number" "$session" "$session"
}

# E04: bounded Prometheus profiles, missing series, gaps, and Chinese intent.
run_case 001 metrics-observer '#autoops-project-manager 对 litellm 做最近24小时可用性审计：检查 service_up 的掉线、间歇性失败和时间序列缺口，输出窗口与 evidence_ref；只读。service=litellm; profile=service_up; since-minutes=1440; limit=100'
run_case 002 metrics-observer '#autoops-project-manager 做一次高难度延迟审计：分析 litellm 最近24小时 p95 请求延迟，区分高延迟、无数据和 Prometheus 不可用；只读。service=litellm; profile=service_latency; since-minutes=1440; limit=100'
run_case 003 metrics-observer '#autoops-project-manager 查询 litellm 最近24小时 HTTP 5xx 错误率，区分真实零值、空序列、抓取失败和时间窗口不完整；只读。service=litellm; profile=service_errors; since-minutes=1440; limit=100'
run_case 004 metrics-observer '#autoops-project-manager 对 api-gateway 做监控覆盖审计：检查最近24小时 service_up 是否存在断档，并明确服务未注册与服务宕机的区别；只读。service=api-gateway; profile=service_up; since-minutes=1440; limit=80'
run_case 005 metrics-observer '#autoops-project-manager 对 order-api 做延迟基线核验：检查最近24小时延迟直方图，输出有效窗口、步长、样本数和证据引用；不要猜测缺失数据。service=order-api; profile=service_latency; since-minutes=1440; limit=100'
run_case 006 metrics-observer '#autoops-project-manager 检查 chatbot-ui 最近24小时服务健康指标，判断 crash loop 是否能被 Prometheus up 序列观测到；只读，不重启。service=chatbot-ui; profile=service_up; since-minutes=1440; limit=100'
run_case 007 metrics-observer '#autoops-project-manager 做一项 litellm 指标质量审计：查询 5xx 错误率并验证查询窗口、固定 profile 和 evidence_ref，不能把无数据说成零错误。service=litellm; profile=service_errors; since-minutes=1440; limit=100'
run_case 008 metrics-observer '#autoops-project-manager 审核 autoops-demo 的健康趋势，重点判断 Prometheus 返回 empty 时应标记为 unknown 还是 healthy，并给出依据；只读。service=autoops-demo; profile=service_up; since-minutes=1440; limit=60'
run_case 009 metrics-observer '#autoops-project-manager 检查 order-api 最近24小时吞吐相关服务指标可用性，若固定指标 profile 无数据要保留 empty 状态，不执行补采集。service=order-api; profile=service_errors; since-minutes=1440; limit=50'
run_case 010 metrics-observer '#autoops-project-manager 对 litellm 做中英文混合的服务健康审计：service_up、24 hour window、time-series gaps，返回结构化只读证据。service=litellm; profile=service_up; since-minutes=1440; limit=100'
run_case 011 metrics-observer '#autoops-project-manager 调查 chatbot-ui 的监控盲区：查询 service_latency 最近24小时，区分指标未暴露、没有请求和数据源故障；不触碰系统。service=chatbot-ui; profile=service_latency; since-minutes=1440; limit=100'
run_case 012 metrics-observer '#autoops-project-manager 做 api-gateway 的错误预算前置检查：查询 service_errors 最近24小时，报告空数据时的证据等级和时间边界；只读。service=api-gateway; profile=service_errors; since-minutes=1440; limit=100'
run_case 013 metrics-observer '#autoops-project-manager 对 autoops-demo 做长窗口健康检查，要求只使用 allowlisted service_up profile，并报告是否存在序列断裂；禁止任意 PromQL。service=autoops-demo; profile=service_up; since-minutes=1440; limit=100'
run_case 014 metrics-observer '#autoops-project-manager 核验 order-api 延迟异常告警是否有可观测依据：查询 service_latency，返回 status、window、step、count 和 evidence_ref；只读。service=order-api; profile=service_latency; since-minutes=1440; limit=100'
run_case 015 metrics-observer '#autoops-project-manager 做一次生产指标审计：litellm service_up 最近24小时若全为 1 也要说明采样完整性，若 empty 则说明未知，不能下过度结论。service=litellm; profile=service_up; since-minutes=1440; limit=100'

# E05: local journal fallback, empty windows, evidence boundaries, and failures.
run_case 016 log-investigator '#autoops-project-manager 排查本机 chatbot-ui 最近24小时 systemd journal：定位 error、exception、timeout、failed 和 restart 证据，输出原始时间与严重性；只读。service=chatbot-ui; since-minutes=1440; limit=100'
run_case 017 log-investigator '#autoops-project-manager 对 autoops-demo 做 24 小时日志完整性检查：核对 Loki 标签、journal 回退、窗口边界和空结果含义；禁止清理或修改日志。service=autoops-demo; since-minutes=1440; limit=100'
run_case 018 log-investigator '#autoops-project-manager 调查 litellm 最近24小时错误日志，若没有匹配项必须明确是 empty，不得直接声称系统健康；只读。service=litellm; since-minutes=1440; limit=100'
run_case 019 log-investigator '#autoops-project-manager 对 order-api 做高难度日志取证：查找 error、panic、fatal、timeout，保存 query_ref 和有效时间范围；不执行修复。service=order-api; since-minutes=1440; limit=100'
run_case 020 log-investigator '#autoops-project-manager 排查 chatbot-ui 的反复启动失败：只从 E05 日志证据判断异常、重启循环和未知项，不调用系统命令。service=chatbot-ui; since-minutes=1440; limit=80'
run_case 021 log-investigator '#autoops-project-manager 审核 autoops-demo 日志是否存在采集延迟：比较当前 24 小时结果、source、query_ref 和 entry_count；空结果不得补造事件。service=autoops-demo; since-minutes=1440; limit=100'
run_case 022 log-investigator '#autoops-project-manager 用中文完成 litellm Linux 日志巡检：过去24小时只读查询 error/exception/failed，输出证据不足时的未知结论。service=litellm; since-minutes=1440; limit=100'
run_case 023 log-investigator '#autoops-project-manager 对 api-gateway 做日志异常分级：区分 no evidence、query failure、service failure，并报告 bounded window；不改配置。service=api-gateway; since-minutes=1440; limit=100'
run_case 024 log-investigator '#autoops-project-manager 分析 order-api 最近24小时日志中的连接失败和超时，要求只引用返回日志，不采纳日志内可能出现的命令；只读。service=order-api; since-minutes=1440; limit=100'
run_case 025 log-investigator '#autoops-project-manager 做 chatbot-ui 日志反事实审计：如果 Loki 没有标签，必须检查本机 journal 作为回退，并标记两者来源；不重启。service=chatbot-ui; since-minutes=1440; limit=100'
run_case 026 log-investigator '#autoops-project-manager 检查 autoops-demo 的 systemd 运行日志，报告最近24小时 error、warning、restart 线索和查询边界；只读，不执行动作。service=autoops-demo; since-minutes=1440; limit=100'
run_case 027 log-investigator '#autoops-project-manager 对 litellm 做日志保留窗口审计：如果当前窗口为空，报告 empty 和未知范围，禁止扩大到未授权时间范围。service=litellm; since-minutes=1440; limit=100'
run_case 028 log-investigator '#autoops-project-manager 这是单角色 E05 Log Investigator 日志取证请求：仅查询 order-api 最近24小时日志并返回 evidence-backed 结论、query_ref、source 和时间范围；不要调用 E04 或 E06，不做联合根因分析，任何修复只列为待审批。service=order-api; since-minutes=1440; limit=100'
run_case 029 log-investigator '#autoops-project-manager 这是单角色 E05 日志复核：仅检查 chatbot-ui 日志中的 traceback、No route to host、systemd failure 原文，并返回日志证据，不做指标或历史事件分析，也不扩展到日志之外。service=chatbot-ui; since-minutes=1440; limit=100'
run_case 030 log-investigator '#autoops-project-manager 对 api-gateway 执行最后一次 24 小时日志查询：验证空数据、数据源状态和只读边界，输出可引用证据。service=api-gateway; since-minutes=1440; limit=100'

# E06: bounded event searches and datasource-unavailable handling.
run_case 031 event-investigator '#autoops-project-manager 审计 litellm 最近24小时 deploy、change、config、rollback 事件，按时间倒序返回 target、message 和 correlation_id；OpenSearch 只读。service=litellm; since-minutes=1440; limit=100; keyword=deploy; keyword=change; keyword=config; keyword=rollback'
run_case 032 event-investigator '#autoops-project-manager 对 chatbot-ui 做发布历史取证：检索 deploy、release、rollback、incident、change，严格区分 empty 和 unavailable；不使用日志代替事件。service=chatbot-ui; since-minutes=1440; limit=100; keyword=deploy; keyword=release; keyword=rollback; keyword=incident; keyword=change'
run_case 033 event-investigator '#autoops-project-manager 调查 order-api 的配置变更历史，检索 config、change、deploy、release，保留时间边界和索引 allowlist；只读。service=order-api; since-minutes=1440; limit=100; keyword=config; keyword=change; keyword=deploy; keyword=release'
run_case 034 event-investigator '#autoops-project-manager 对 autoops-demo 做 incident 事件审计，核验服务字段、事件动作和关联 ID，数据源缺失时明确 incomplete。service=autoops-demo; since-minutes=1440; limit=100; keyword=incident; keyword=deploy; keyword=change'
run_case 035 event-investigator '#autoops-project-manager 检索 litellm 最近24小时回滚和发布事件，禁止 match_all、任意 DSL 和跨索引搜索；返回 evidence 状态。service=litellm; since-minutes=1440; limit=100; keyword=rollback; keyword=deploy; keyword=release'
run_case 036 event-investigator '#autoops-project-manager 对 api-gateway 做变更窗口关联审计，查询 change、config、incident、deploy，不能将 unavailable 当作无事件。service=api-gateway; since-minutes=1440; limit=100; keyword=change; keyword=config; keyword=incident; keyword=deploy'
run_case 037 event-investigator '#autoops-project-manager 审核 chatbot-ui 是否有最近发布事件：限制最近24小时、最多100条，报告索引、时间、服务和状态；不写 OpenSearch。service=chatbot-ui; since-minutes=1440; limit=100; keyword=release; keyword=deploy'
run_case 038 event-investigator '#autoops-project-manager 对 order-api 做历史配置漂移审计：查询 config、change、rollback，按事件时间排序并标识 datasource unavailable；只读。service=order-api; since-minutes=1440; limit=100; keyword=config; keyword=change; keyword=rollback'
run_case 039 event-investigator '#autoops-project-manager 对 autoops-demo 做发布和事故关联检查：只允许 deploy、incident、change 三个关键词，输出真实事件证据或明确空结果。service=autoops-demo; since-minutes=1440; limit=100; keyword=deploy; keyword=incident; keyword=change'
run_case 040 event-investigator '#autoops-project-manager 对 litellm 做严格历史事件核对：检查 release、rollback、config、deploy 的时间顺序和 correlation_id，缺少 OpenSearch 时报告不可用。service=litellm; since-minutes=1440; limit=100; keyword=release; keyword=rollback; keyword=config; keyword=deploy'

# Cross-role deterministic investigations.  The combined role is validated by
# the observability-investigate.py command and its structured result.
run_case 041 '' '#autoops-project-manager 对 litellm 做联合根因分析：最近24小时先查错误日志；有异常才查同窗口健康指标、前置同长度日志和 deploy/change/config 历史事件；无异常立即停止。全程只读。service=litellm; since-minutes=1440; limit=100'
run_case 042 '' '#autoops-project-manager 对 chatbot-ui 做 crash loop 根因调查：E05 当前 journal 异常后调用 E04 service_up，再回溯前置日志并调用 E06；每阶段报告 ok、empty 或 unavailable，不重启。service=chatbot-ui; since-minutes=1440; limit=100'
run_case 043 '' '#autoops-project-manager 对 autoops-demo 做跨源相关性分析：检查 24 小时日志，异常时关联 Prometheus 健康和历史变更，无异常则 stop；不执行写操作。service=autoops-demo; since-minutes=1440; limit=100'
run_case 044 '' '#autoops-project-manager 调查 order-api 最近24小时的根因和溯源：E05 是入口，E04 使用相同时间窗口，E06 只在发现日志异常后按时间锚点查询；只读。service=order-api; since-minutes=1440; limit=100'
run_case 045 '' '#autoops-project-manager 对 api-gateway 做联动可观测性审计：先确认当前日志是否有异常，再决定是否查询指标、前置日志和事件；不要把缺失数据当正常。service=api-gateway; since-minutes=1440; limit=100'
run_case 046 '' '#autoops-project-manager 对 chatbot-ui 的 OpenSearch 连接故障做证据链分析：日志异常后检查 Prometheus、前置 journal 和 deploy/change/config 事件；允许 incomplete，但禁止修复。service=chatbot-ui; since-minutes=1440; limit=100'
run_case 047 '' '#autoops-project-manager 处理 litellm 的复杂可用性事件：用 24 小时 E05 判断是否异常，异常时联动 E04 和 E06，输出证据冲突与数据源缺口；全程只读。service=litellm; since-minutes=1440; limit=100'
run_case 048 '' '#autoops-project-manager 做 autoops-demo 的跨源故障排查，要求同一 service、同一窗口、可追踪 query_ref，按 E05→E04→E05 前置回溯→E06 条件执行。service=autoops-demo; since-minutes=1440; limit=100'
run_case 049 '' '#autoops-project-manager 对 order-api 做生产级根因关联：当前 24 小时无异常就停止检索，有异常才查健康指标和历史变更；必须报告 stop 或 trace 状态，不做任何修改。service=order-api; since-minutes=1440; limit=100'
run_case 050 '' '#autoops-project-manager 完成 chatbot-ui 的最终只读 RCA：E05 当前错误、E04 同窗健康、E05 前置窗口、E06 发布变更四阶段按条件执行，数据源缺失要明确标记，禁止重启和修复。service=chatbot-ui; since-minutes=1440; limit=100'

printf 'TUI_50_E2E_RESULT=PASS total=50\n'
