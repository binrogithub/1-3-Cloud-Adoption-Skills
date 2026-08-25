# PRD — Agent Loop Continuity V1

状态: 已实施（L1-A + L1-B + L2 + L3 + L4，G1–G6 全绿）
作者: Claude (独立复核)
日期: 2026-08-23
实施日期: 2026-08-24
适用构建: 7edc1ae091d6a3fbb0c5f051c8f64b93c8f05d39cfb0162d2a23e475feac52d5
前序: PRD_RELEASE_V7 §X1(安全降级) / V8 §D2(判读表) / V11

---

## 0. 范围声明

本 PRD **不新增功能**。它修正 V7 §X1 已上线行为的一个副作用。
用户在 V6 轮次给过 `不需要再新增功能` 的约束,本文件全部条目均为对既有行为的
更正与可观测性补齐,不引入新特性。

---

## 1. 问题陈述

Claude Code 在任务未完成时静默停止,用户需要手动输入 `continue` 才能继续。

根因不在客户端,也不在上游挂死,而在适配器 `adapter/server.js:1015`:

```js
emitSafeDegradation(toolIndex, call.name);   // 用一段文本替换工具调用
ctrl.finishReason = "end_turn";              // <-- 这一行结束了 agent loop
```

当 GLM 产出的 tool-call JSON 三道闸门全部拒绝时,适配器把工具调用替换成一段
中文文本,并把 `stop_reason` 置为 `end_turn`。从 Claude Code 的视角看,这是一次
**完全正常的、说完话就结束的回合**:没有错误、没有重试信号、没有未完成标记。
agent loop 依据协议正确地退出了。

X1 的设计意图是"把硬失败变成可解释的软失败"。实际效果是把一个
**32% 能自愈**的失败,换成了一个 **0% 能自愈**的失败。

---

## 2. 证据

### 2.1 服务端(enforce 窗口,2026-08-23 01:50:47 起)

```
window request_end        = 559
tool_args_degraded        = 6            (1.07%)
outcome: completed        = 555
outcome: client_aborted   = 3
outcome: idle_timeout     = 1
MAAS_STREAM_PROTOCOL      = 0
```

6 次降级的 `request_end` 中,4 条 `client_bytes` 分别为 891 / 890 / 891 / 2520。
891 字节 ≈ **只有那一句降级文本**。整个回合模型什么活都没干。

### 2.2 客户端(/root/.claude-maas/projects/ 全量 JSONL)

9 个 assistant 回合正文含降级文本,其中 6 个:

```
stop_reason = end_turn
content     = [text]        <-- 只有一个 text block,无 tool_use
```

紧随其后的记录:

| 后继 | 次数 |
|---|---|
| 会话到此结束(EOF) | 3 |
| 人类输入 `continue` | 1 |
| 人类追问 `任务都完成了吗？` | 1 |
| 人类切换话题 | 1 |
| **自动继续** | **0** |

### 2.3 与旧的硬失败对照(n=25,`API Error: stream protocol error`)

| 后继 | 次数 | 占比 |
|---|---|---|
| **自动恢复**(下一条是 tool_result) | 8 | 32% |
| 人类介入(9 次 `continue` + 3 次其它) | 12 | 48% |
| 会话结束 | 5 | 20% |

**硬失败 32% 自愈,静默降级 0% 自愈。**

### 2.4 全量 stop_reason 分布

```
tool_use      6109
end_turn       171
stop_sequence   38   <-- 全部为 Claude Code 渲染 API Error 的回合
None            83   <-- 多为 thinking block 独立成条,非缺陷
isApiErrorMessage 32  <-- 最新一条 2026-08-22T14:24:46Z,窗口内 0 条
```

窗口内 `isApiErrorMessage = 0`,V11 §3.10 在窗口口径下成立;上述 32 条全部早于
窗口开始(2026-08-22T17:50:47Z)。

### 2.5 sibling 项目同样有此缺陷

`litellm-auto-plugin/litellm_plugins/tool_argument_guard/callback.py` 的策略原文:
`replace the tool call with a safe text result and terminate the assistant turn
without tool execution`。**同一缺陷。** 不能把"litellm 也这么做"当作本设计的验证。

---

## 3. 缺陷清单

### L1 (P0) — 降级不得静默结束回合

`server.js:1016` 与 `:1039` 的 `ctrl.finishReason = "end_turn"` 使 agent loop
正常退出,任务中断且不可自愈。

**修复方向(按优先级组合实施)**

- **L1-A 上游重试(唯一可能真正完成任务的路径)**
  闸门拒绝时,若本次响应**尚未向客户端提交任何可见字节**
  (`textStarted === false` 且 `thinkingStarted === false`),对上游重发一次同样的
  请求。tool-call JSON 畸形是随机的,重试有实际成功率。
  硬约束:已流出文本时**禁止**重试,否则客户端会看到重复正文。
  重试上限 1 次,计入 `/status.tool_args_retry{attempted,succeeded}`。

- **L1-B 重试不可用或再次失败时,以错误终止而非 `end_turn`**
  走 `ctrl._setProtocolError("tool_args_malformed")`,恢复 ≥32% 的自愈路径。
  X1 的"绝不执行该工具"保证、X2 分类、X3 归一化诊断**全部保留**,
  只改变终止方式。

- **L1-C 降级文本的去留**
  若采纳 L1-B,`SAFE_DEGRADATION_TEXT` 不再作为回合的唯一正文。
  是否在 error 之前保留该文本块由实施方决定,但**不得**出现
  `stop_reason=end_turn` 且正文只有该文本的回合(见 G5)。

### L2 (P1) — 一次降级会吞掉同回合其余工具调用

`for (const call of toolCalls.values())` 中降级分支执行 `break`(`:1024`、`:1043`),
同一回合内后续**合法**的工具调用被静默丢弃。模型一次发 3 个调用、第 1 个畸形时,
另外 2 个从未到达客户端。

修复:降级分支改为 `continue`;仅当至少发出一个真实 `tool_use` 时
才保留 `stop_reason: tool_use`。

### L3 (P1) — 最有诊断价值的样本没有诊断数据

6 次降级中 2 次 `request_end` 的 `"repair": null`。`normalize_failed` 分支
(`:1035`)未写 `lastRepairInfo`,而这正是 X3 归一化把合法输入改坏的分支。

修复:该分支填充 `repairInfo`(含 `reject_class`、`args_len`、`first_char_code`、
`char_class_counts`、`mode`),字段口径与既有分支一致。
安全约束不变:**不得写入 `err.message` 原文,不得写入 `call.arguments` 任何片段。**

### L4 (P1) — 没有任何指标能发现"任务被中断"

`request_end` 不含 `stop_reason`,`/status` 不含 stop_reason 分布。
6 次降级在服务端全部记为 `outcome: completed`,监控面板上是满绿。
**这正是"任务没完成就停了"能在 V7→V11 五轮验收里一路不被发现的原因。**

修复:
- `request_end` 增加 `stop_reason` 字段
- `/status` 增加 `stop_reasons` 计数器
- 区分 `degraded`(发生降级)与 `degraded_no_tool_emitted`(该回合一个工具都没发出)

### L5 (P2) — idle 截断(仅记录,本轮不修)

窗口内 1 次 `MAAS_IDLE_TIMEOUT`,历史 6 条
`API Error: The response stopped arriving`。`IDLE_TIMEOUT = 150000`。
该路径至少对客户端可见且会触发重试,优先级低于 L1–L4。

---

## 4. 验收门禁

门禁必须有鉴别力:**每一条都要求先证明它在修复被回退后 FAIL。**
未附反向失败证据的门禁不计入验收。

| 门 | 断言 | 反向用例 |
|---|---|---|
| G1 | 注入畸形 args → 客户端收到 SSE `error` 事件,或重试后收到真实 `tool_use`;断言不存在 `stop_reason=end_turn` 且正文仅为降级文本的回合 | 回退 L1 后必须 FAIL |
| G2 | 上游发 2 个 tool_call,第 1 个畸形 → 断言第 2 个仍被发出 | 回退 L2 后必须 FAIL |
| G3 | 上游第 1 次畸形、第 2 次合法 → 断言客户端只收到 **1 个** `message_start` 且最终为真实 `tool_use`;另一用例:已流出文本时畸形 → 断言**未**重试、正文无重复 | 去掉重试上限或去掉 textStarted 守卫后必须 FAIL |
| G4 | `normalize_failed` 路径的 `request_end.repair !== null` 且含全部约定字段 | 回退 L3 后必须 FAIL |
| G5 | 全量 JSONL 扫描:`stop_reason=end_turn` 且 content 仅有一个 text block、内容等于 `SAFE_DEGRADATION_TEXT` 的回合数 = 0 | 当前代码下该数为 6,故此门当前 FAIL —— 已具备鉴别力 |
| G6 | `/status.stop_reasons` 存在且各计数之和等于 `request_end` 总数 | 回退 L4 后必须 FAIL |

G5 的当前值为 6,不是 0。**该门在修复前即为红,无需再造反向用例。**

---

## 5. 与 v1.1 发布的关系

本缺陷**不阻塞** v1.1 打标,但必须在 Known limitations 中写明,理由:

1. v1.0 的行为是硬失败(32% 自愈),v1.1 的降级是 0% 自愈——
   在"任务完成率"这一维度上 **v1.1 相对 v1.0 是回归**。
2. V8 §D2 的判读表只度量了"失败是否受控可解释",**从未度量任务是否继续**。
   所以 §3 可以全绿而产品体验变差。

这是门禁失去鉴别力的**第六种形态**,应补入项目的门禁反模式清单:

> **验收口径与产品目标不同轴** —— 指标衡量的是"错误是否消失",
> 而用户关心的是"活是否干完"。把失败改成静默成功,前者变好、后者变差,
> 全部门禁仍然全绿。

若决定 v1.1 带此缺陷发布,Known limitations 必须写明:
`工具参数畸形时(观测率 1.07%),当前回合会以 end_turn 结束且不自动继续,
需人工输入 continue。`

---

## 6. 建议

按 L1-A + L1-B + L2 + L3 + L4 实施,G1–G6 全绿后合入。
L1-A 单独就能把 1.07% 中的一部分变成真正完成;L1-B 兜住其余,把自愈率从 0%
拉回至少 32%。两者叠加优于任何单独一项。

L5 单列后续轮次。
