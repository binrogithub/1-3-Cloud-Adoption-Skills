# PRD：auto_continue 对"静默被杀"会话的探测盲区 v1

> 状态：Ready for approval
> 涉及组件：`claude-maas-delegate` skill（`scripts/auto_continue.py`、`scripts/delegate`）
> 固定模型：`glm-5.2`（通过 Anthropic-compatible MaaS 端点）
> 文档日期：2026-09-04
> 优先级：P1
> 性质：诊断准确性缺口——不改变重试策略，只改变"失败原因"的报告是否诚实

## 0. 结论

`maas-delegate run` 在长任务（约 6–11 分钟、10 万+ token）上出现过两次
`needs_escalation`，摘要都是同一行看似吓人的文本：

```
[claude-code:unrecognized_model] {"model":"glm-5.2","query_source":"generate_session_title"}
```

复盘先后走了两条路，第一条被证伪，第二条是真正的病因：

1. **最初怀疑**：这条诊断本身导致会话失败。**已用隔离实验证伪**——同样的
   环境变量注入方式（`ANTHROPIC_MODEL=glm-5.2` 直塞四个模型环境变量）跑一次
   一句话任务，stderr 照样打印这行诊断，但 `stdout` 的终态帧是
   `"subtype":"success","is_error":false`，`claude-maas-delegate` 自己的
   `_parse_stream_json` 判定逻辑会正常判成功。这条诊断是 Claude Code CLI
   2.1.259 版本新增的、写到 stderr 的**纯信息性**提示（二进制里能直接读到
   官方 changelog 原文："a `[claude-code:unrecognized_model]` line is
   written to stderr when a request goes out for a model ID Claude Code
   doesn't recognize; map it with `modelOverrides` to silence"）——不是错误，
   不影响本轮请求成功与否。
2. **真正病因**：两次真实失败会话的 `.jsonl` 记录文件还在磁盘上，直接读到了
   死亡瞬间——最后几行是模型正常执行 `pytest`、`git diff --stat`、
   `git status --short` 的完整工具调用序列，然后紧跟两条无内容的
   `attachment` / `last-prompt` 记录，**文件到此戛然而止**：没有
   assistant 的错误回复，没有 `isApiErrorMessage` 标记，没有任何堆栈或
   报错文本。这是"进程被外部信号杀死"的典型签名（很可能是资源限制或
   某层外部超时），不是"模型报了个 API 错误"。

`scripts/auto_continue.py` 的 `detect_stream_protocol_error` 只认一种
模式——最后一条 assistant 记录 `isApiErrorMessage===true` 且文本以
`"API Error: stream protocol error"` 开头——这两次真实失败完全不匹配这个
模式（根本没有 assistant 错误记录），所以自动续跑从未触发，`delegate`
脚本转而把本轮唯一一次调用的 stderr 原样当 `summary` 抛出——而 stderr
里唯一的内容，恰好是前面提到的、跟死因无关的诊断行。**调用方看到的
"失败摘要"因此系统性地指向错误的原因。**

## 1. 证据

会话文件（本次复盘期间产生，路径脱敏）：
`<claude-config-dir>/projects/<project>/6e613189-babc-4b40-ab98-f5d5159f5794.jsonl`，
183 行，倒数几条记录类型序列：

```
assistant (tool_use: Bash "pytest ...")
user      (tool_result: "...................................... [36 passed]")
assistant (text: "All 36 existing tests pass. Let me review the final state...")
assistant (tool_use: Bash "git diff --stat")
user      (tool_result: " bin/plan.py | 39 ++...")
assistant (tool_use: Bash "git status --short")
user      (tool_result: " M bin/plan.py\n?? bin/initiative.py\n?? docs/...")
attachment   ← 无 content
last-prompt  ← 无 content
[EOF]
```

对照隔离实验：同样的模型注入方式（`ANTHROPIC_MODEL`/
`ANTHROPIC_DEFAULT_*_MODEL` 全部塞 `glm-5.2`，不经 `modelOverrides`）跑
一句话任务，`exit code 0`，`stdout` 终态帧
`{"subtype":"success","is_error":false,...}`，stderr 只有那行诊断——
`claude-maas-delegate` 判为成功。两相对照，确认诊断本身不是致命因素。

## 2. 目标与非目标

**目标**

- `auto_continue.py` 除了现有的 "stream protocol error" 探测，新增一种
  探测：**会话最后一条记录不是 assistant/result 终态，且找不到任何
  错误标记**——即"进程疑似被外部杀死，而不是 API 报了错"。命名为
  `silent_kill`，与 `stream_protocol_error` 并列，是独立的 `outcome`
  分类，不是同一个桶。
- `delegate` 脚本在构造最终 `summary` 时，如果分类是 `silent_kill`，
  **不要**把不相关的 stderr 内容当摘要——应该明确说"会话在没有产出终态
  结果的情况下结束，最后一条记录是 <type>，找不到错误标记"，把这行
  诊断（如果碰巧也在 stderr 里）跟死因剥离开，避免继续误导下一个读
  这份摘要的人（无论是人还是另一个 agent）。
- 不改变现有 "stream protocol error" 的重试语义（PRD
  `PRD_MAAS_STREAM_WAIT_RELIABILITY_V1`/`_V2` 已经定义好的行为不动）。

**非目标**

- 不解决"进程为什么被杀"这件事本身——那大概率是资源限制或外层超时，
  属于这台/这类宿主机的运维问题，不是这个 skill 的代码能管的范围。
- 不新增对 `silent_kill` 的自动重试——**现在没有证据支持"重试能解决它"**；
  如果死因是资源耗尽，立刻重试大概率重蹈覆辙。这次只做诚实分类和诚实
  报告，重试策略留给看到准确分类之后的人决定。
- 不改动 `modelOverrides` 相关的模型注入方式——那是本轮复盘中发现的另一
  个独立、真实但与本次 `silent_kill` 无关的问题，留给单独的 change。

## 3. 方案

### 3.1 探测函数

`scripts/auto_continue.py` 新增：

```python
def detect_silent_kill(session_jsonl: Path) -> dict | None:
    """None when the session ended normally (an assistant/result terminal
    record, or a stream-protocol-error record already handled by
    detect_stream_protocol_error). Otherwise a dict describing the last
    record type found, for an honest failure summary."""
```

判定顺序（在 `run_with_auto_continue` 里，紧接现有的
`detect_stream_protocol_error` 检查之后）：

1. 若 `detect_stream_protocol_error` 为真 → 现有逻辑不变（可重试）。
2. 否则，读会话 jsonl 最后一条记录：
   - 若其 `type` 是 `assistant` 且携带正常文本/tool_use，或 `type` 是
     `result`（stream-json 场景），判定为**正常结束**，走现有的
     `outcome = "completed" if last_rc == 0 else "failed"`。
   - 若最后一条记录的 `type` 不在 `{assistant, result, user}` 这个"正常
     轮次"集合里（比如 `attachment`、`last-prompt`，或压根没有任何记录），
     判定 `outcome = "silent_kill"`，并记录最后一条记录的 `type`、
     `last_returncode`、已完成的轮次数，供审计。

### 3.2 摘要构建

`scripts/delegate` 的结果组装处（`outcome != "success"` 分支）：当
`auto_continue` 返回 `outcome == "silent_kill"` 时，`summary` 改为结构化
文本，例如：

```
session ended without a terminal result (last record type: "last-prompt",
no API error recorded) — likely killed externally (resource limit or an
outer timeout), not an application-level failure; unrelated stderr
(if any) is attached separately, not folded into this summary
```

stderr 原文仍然保留在结果字典的 `stderr` 字段里（供人深挖），但不再冒充
`summary`。

### 3.3 审计记录

`_write_audit` 增加 `outcome: "silent_kill"` 这一枚举值（现有的
`"succeeded"`/`"abandoned"` 之外），不新增字段，兼容现有审计消费方。

## 4. 反向门（不该做的事）

- 不得把 `silent_kill` 并入现有 `stream_protocol_error` 的重试预算——
  两者是不同性质的失败，混在一起会让重试次数的语义失真。
- 不得在没有证据的情况下，把这条新分类跟具体的宿主机资源限制原因绑死
  写死在文案里——探测函数只负责"诚实说不知道死因，但确定不是 API 报错"，
  不负责猜测底层原因。
- 不得删除或弱化对现有 `stream_protocol_error` 标记的探测——两者并列，
  不是替代关系。

## 5. 验收

- 单元测试：构造一个以 `attachment`/`last-prompt` 结尾、无 assistant
  错误记录的 fixture jsonl，`detect_silent_kill` 应返回非 None；构造一个
  正常以 assistant 文本结尾的 fixture，应返回 None。
- 回归：现有 `stream_protocol_error` 相关测试（如果仓库里有）必须全绿，
  证明新分类没有吃掉旧分类的判定路径。
- 端到端可选：用本 PRD §1 里描述的真实 fixture（已脱敏）跑一遍
  `run_with_auto_continue`，确认返回 `outcome == "silent_kill"` 而不是
  `"failed"`。

## 6. 回滚

纯新增一个探测函数 + 一个 outcome 分支 + 摘要文案分支，不改变现有
`stream_protocol_error` 路径的判定条件。删除新增的这几处即可完全回退。
