#!/usr/bin/env bash
set -Eeuo pipefail

# Sequential TUI acceptance runner. It stops at the first failed scenario so
# the defect can be fixed before the next task is started.
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS="${AUTOOPS_50_RESULTS:-${ROOT}/.runtime/tui-complex-50-results.tsv}"
mkdir -p "$(dirname -- "$RESULTS")"
printf 'scenario\tgroup\tresult\tsession\thistory\n' >"$RESULTS"
export AUTOOPS_50_RESULTS="$RESULTS"

expect -c '
  log_user 0
  set timeout 5
  set result_file $env(AUTOOPS_50_RESULTS)
  set scenarios {
    {001 E05 {#autoops-project-manager complex-50-001 调查 autoops-demo 最近 15 分钟的启动、错误和重启日志；service=autoops-demo; since-minutes=15; limit=100} local-journal}
    {002 E05 {#autoops-project-manager complex-50-002 调查 chatbot-ui 最近 15 分钟的崩溃、依赖错误和 systemd 重启循环；service=chatbot-ui; since-minutes=15; limit=100} local-journal}
    {003 E05 {#autoops-project-manager complex-50-003 诊断 autoops-demo 最近 5 分钟日志并判断是否存在异常；service=autoops-demo; since-minutes=5; limit=50} local-journal}
    {004 E05 {#autoops-project-manager complex-50-004 调查 chatbot-ui 最近 10 分钟的异常退出并给出证据；service=chatbot-ui; since-minutes=10; limit=80} local-journal}
    {005 E05 {#autoops-project-manager complex-50-005 检查 autoops-demo 的服务事件、错误和重启情况；service=autoops-demo; since-minutes=20; limit=120} local-journal}
    {006 E05 {#autoops-project-manager complex-50-006 调查 chatbot-ui 的 Python 异常和崩溃模式；service=chatbot-ui; since-minutes=15; limit=100} local-journal}
    {007 E05 {#autoops-project-manager complex-50-007 对 autoops-demo 做只读故障证据收集和异常判断；service=autoops-demo; since-minutes=30; limit=150} local-journal}
    {008 E05 {#autoops-project-manager complex-50-008 对 chatbot-ui 做只读日志调查，重点检查 crash loop；service=chatbot-ui; since-minutes=30; limit=150} local-journal}
    {009 E05 {#autoops-project-manager complex-50-009 检查 autoops-demo 最近的 systemd 日志是否足以支持恢复决策；service=autoops-demo; since-minutes=10; limit=60} local-journal}
    {010 E05 {#autoops-project-manager complex-50-010 检查 chatbot-ui 的错误日志、重启计数和根因；service=chatbot-ui; since-minutes=15; limit=200} local-journal}
    {011 E01 {#autoops-project-manager complex-50-011 预览已发布 host-basic-check，只读检查 test-host-01；job=host-basic-check; target=test-host-01} PENDING_CONFIRMATION}
    {012 E01 {#autoops-project-manager complex-50-012 对 test-host-01 预览 host-basic-check，不提交执行；job=host-basic-check; target=test-host-01} PENDING_CONFIRMATION}
    {013 E01 {#autoops-project-manager complex-50-013 检查 test-host-01 的基础主机状态并返回审批预览；job=host-basic-check; target=test-host-01} PENDING_CONFIRMATION}
    {014 E01 {#autoops-project-manager complex-50-014 生成 test-host-01 主机检查 Runbook 预览；job=host-basic-check; target=test-host-01} PENDING_CONFIRMATION}
    {015 E01 {#autoops-project-manager complex-50-015 只读检查 test-host-01 的主机基线，等待确认；job=host-basic-check; target=test-host-01} PENDING_CONFIRMATION}
    {016 E01 {#autoops-project-manager complex-50-016 预览 Rundeck host-basic-check 对 test-host-01 的检查；job=host-basic-check; target=test-host-01} PENDING_CONFIRMATION}
    {017 E01 {#autoops-project-manager complex-50-017 查询 test-host-01 的已发布主机检查作业但不执行；job=host-basic-check; target=test-host-01} PENDING_CONFIRMATION}
    {018 E01 {#autoops-project-manager complex-50-018 对 test-host-01 做受控 Runbook 检查预览；job=host-basic-check; target=test-host-01} PENDING_CONFIRMATION}
    {019 E01 {#autoops-project-manager complex-50-019 生成基础主机健康检查计划，目标 test-host-01；job=host-basic-check; target=test-host-01} PENDING_CONFIRMATION}
    {020 E01 {#autoops-project-manager complex-50-020 预览 test-host-01 的 host-basic-check 并保持 dry-run；job=host-basic-check; target=test-host-01} PENDING_CONFIRMATION}
    {021 E02 {#autoops-project-manager complex-50-021 预览确保 autoops-demo 运行的受控动作，不执行；service=autoops-demo; action=ensure; target=test-host-01} PENDING_CONFIRMATION}
    {022 E02 {#autoops-project-manager complex-50-022 生成 autoops-demo 服务恢复审批预览；service=autoops-demo; action=ensure; target=test-host-01} PENDING_CONFIRMATION}
    {023 E02 {#autoops-project-manager complex-50-023 检查 test-host-01 上 autoops-demo 是否可由已发布动作恢复；service=autoops-demo; action=ensure; target=test-host-01} PENDING_CONFIRMATION}
    {024 E02 {#autoops-project-manager complex-50-024 预览 autoops-demo ensure 的 E02 到 E01 边界；service=autoops-demo; action=ensure; target=test-host-01} PENDING_CONFIRMATION}
    {025 E02 {#autoops-project-manager complex-50-025 请求 autoops-demo 受控启动预览，等待人工确认；service=autoops-demo; action=ensure; target=test-host-01} PENDING_CONFIRMATION}
    {026 E02 {#autoops-project-manager complex-50-026 只生成 test-host-01 autoops-demo 恢复动作，不提交 Job；service=autoops-demo; action=ensure; target=test-host-01} PENDING_CONFIRMATION}
    {027 E02 {#autoops-project-manager complex-50-027 预览已发布 Ansible ensure 服务动作；service=autoops-demo; action=ensure; target=test-host-01} PENDING_CONFIRMATION}
    {028 E02 {#autoops-project-manager complex-50-028 对 autoops-demo 进行恢复前动作确认预览；service=autoops-demo; action=ensure; target=test-host-01} PENDING_CONFIRMATION}
    {029 E02 {#autoops-project-manager complex-50-029 请求 test-host-01 的 autoops-demo ensure dry-run；service=autoops-demo; action=ensure; target=test-host-01} PENDING_CONFIRMATION}
    {030 E02 {#autoops-project-manager complex-50-030 生成受控服务恢复的 E02 审批信息；service=autoops-demo; action=ensure; target=test-host-01} PENDING_CONFIRMATION}
    {031 E09 {#autoops-recovery-verifier complex-50-031 独立验证 test-host-01 的 autoops-demo 服务和健康端点；task-id=complex-50-031; step-id=verify-service; target=test-host-01; service=autoops-demo} verification_status}
    {032 E09 {#autoops-recovery-verifier complex-50-032 对 autoops-demo 执行只读 systemd 与 HTTP 健康验证；task-id=complex-50-032; step-id=verify-service; target=test-host-01; service=autoops-demo} verification_status}
    {033 E09 {#autoops-recovery-verifier complex-50-033 检查恢复后的 autoops-demo 是否 active 且健康；task-id=complex-50-033; step-id=verify-service; target=test-host-01; service=autoops-demo} verification_status}
    {034 E09 {#autoops-recovery-verifier complex-50-034 独立复核 test-host-01 autoops-demo 的恢复状态；task-id=complex-50-034; step-id=verify-service; target=test-host-01; service=autoops-demo} verification_status}
    {035 E09 {#autoops-recovery-verifier complex-50-035 只读验证 autoops-demo health probe 和 systemd 状态；task-id=complex-50-035; step-id=verify-service; target=test-host-01; service=autoops-demo} verification_status}
    {036 PLAN {#autoops-project-manager complex-50-036 为 test-host-01 的 autoops-demo 生成检查、日志诊断、恢复和验证计划，模式 confirm；target=test-host-01; service=autoops-demo; mode=confirm} WAITING_APPROVAL}
    {037 PLAN {#autoops-project-manager complex-50-037 规划 autoops-demo 故障处理：先检查主机，再诊断日志，最后待批准恢复并验证；target=test-host-01; service=autoops-demo; mode=confirm} WAITING_APPROVAL}
    {038 PLAN {#autoops-project-manager complex-50-038 设计 test-host-01 autoops-demo 的完整运维闭环，禁止跳过审批；target=test-host-01; service=autoops-demo; mode=confirm} WAITING_APPROVAL}
    {039 PLAN {#autoops-project-manager complex-50-039 生成 autoops-demo 从故障调查到恢复验证的多角色计划；target=test-host-01; service=autoops-demo; mode=confirm} WAITING_APPROVAL}
    {040 PLAN {#autoops-project-manager complex-50-040 编排 E01、E05、E02、E09 完成 autoops-demo 恢复预案；target=test-host-01; service=autoops-demo; mode=confirm} WAITING_APPROVAL}
    {041 PLAN {#autoops-project-manager complex-50-041 对 test-host-01 的 autoops-demo 生成含停止条件的恢复计划；target=test-host-01; service=autoops-demo; mode=confirm} WAITING_APPROVAL}
    {042 PLAN {#autoops-project-manager complex-50-042 生成 autoops-demo 证据驱动的诊断、修复和独立验收计划；target=test-host-01; service=autoops-demo; mode=confirm} WAITING_APPROVAL}
    {043 PLAN {#autoops-project-manager complex-50-043 编排 test-host-01 服务异常的只读检查、日志诊断和待确认恢复；target=test-host-01; service=autoops-demo; mode=confirm} WAITING_APPROVAL}
    {044 PLAN {#autoops-project-manager complex-50-044 设计 autoops-demo 恢复任务的 E01 检查、E05 诊断、E02 动作和 E09 验证；target=test-host-01; service=autoops-demo; mode=confirm} WAITING_APPROVAL}
    {045 PLAN {#autoops-project-manager complex-50-045 生成可审计的 autoops-demo 多角色运维任务计划；target=test-host-01; service=autoops-demo; mode=confirm} WAITING_APPROVAL}
    {046 PLAN {#autoops-project-manager complex-50-046 为 test-host-01 autoops-demo 规划故障证据、恢复动作和回归验证；target=test-host-01; service=autoops-demo; mode=confirm} WAITING_APPROVAL}
    {047 PLAN {#autoops-project-manager complex-50-047 创建 autoops-demo 的受控恢复工作流，需先经过审批；target=test-host-01; service=autoops-demo; mode=confirm} WAITING_APPROVAL}
    {048 PLAN {#autoops-project-manager complex-50-048 生成从主机检查到健康验证的 autoops-demo 运维计划；target=test-host-01; service=autoops-demo; mode=confirm} WAITING_APPROVAL}
    {049 PLAN {#autoops-project-manager complex-50-049 编排 test-host-01 autoops-demo 的诊断、恢复和独立验证步骤；target=test-host-01; service=autoops-demo; mode=confirm} WAITING_APPROVAL}
    {050 PLAN {#autoops-project-manager complex-50-050 完成 autoops-demo 复杂运维任务分解，包含 E01、E05、E02、E09 和审批门；target=test-host-01; service=autoops-demo; mode=confirm} WAITING_APPROVAL}
  }
  set output [open $result_file a]
  foreach scenario $scenarios {
    lassign $scenario number group prompt expected
    set session "autoops-complex-50-${number}-20260912-r2"
    set history_file "/root/.jiuwenswarm/agent/sessions/${session}/history.jsonl"
    spawn -noecho jiuwenswarm-tui --persist-session --session $session
    set deadline [expr {[clock seconds] + 180}]
    set next_send [expr {[clock seconds] + 12}]
    set sent 0
    set matched 0
    while {[clock seconds] < $deadline} {
      expect -timeout 0 { -re {.+} {} timeout {} }
      if {[clock seconds] >= $next_send && !$matched && !$sent} {
        send -- "$prompt\r"
        set sent 1
      }
      if {[file exists $history_file]} {
        set f [open $history_file r]
        set h [read $f]
        close $f
        set marker "complex-50-${number}"
        set marker_pos [string first $marker $h]
        if {$marker_pos >= 0} {
          set tail [string range $h $marker_pos end]
          set expected_found [expr {[string first $expected $tail] >= 0}]
          if {$group eq "E09"} {
            set expected_found [expr {$expected_found && [string first "PASS" $tail] >= 0}]
          }
          if {$expected_found && [string first "chat.tool_result" $tail] >= 0} {
            set matched 1
            break
          }
        }
      }
      after 1000
    }
    if {$matched} {
      puts $output "$number\t$group\tPASS\t$session\t$history_file"
      puts "SCENARIO_${number}=PASS"
    } else {
      puts $output "$number\t$group\tFAIL\t$session\t$history_file"
      close $output
      puts stderr "SCENARIO_${number}=FAIL session=$session history=$history_file"
      send -- "/exit\r"
      after 1000
      catch {close}
      catch {wait}
      exit 1
    }
    send -- "/exit\r"
    after 1000
    catch {close}
    catch {wait}
  }
  close $output
  puts "COMPLEX_50=PASS"
  exit 0
'
