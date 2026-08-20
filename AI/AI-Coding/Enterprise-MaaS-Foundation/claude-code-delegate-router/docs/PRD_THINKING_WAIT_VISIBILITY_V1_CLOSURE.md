# PRD：思考期等待可见性 — 收口（v1 closure）

状态：已交付
前置：`docs/PRD_THINKING_WAIT_VISIBILITY_V1.md`（实现已交付并 commit 于 `7b71304`）

## 0. 产品摘要

**机制是对的，实测有效。** 用真实上游、真实 Key 跑一次（canary :3001，仓库产物）：

| 时刻 | 事件 |
| --- | --- |
| 5.20s | `message_start` + `content_block_start{type:thinking}` |
| 5.25s → 21.0s | `thinking_delta` × **84**，内容全为 `·` |
| 21.01s | thinking 块闭合，`content_block_start{type:text}` + 25 个 text_delta |
| 22.50s | `message_delta`（stop_reason + usage）+ `message_stop` |

对照修复前：同样的 prompt，客户端在 20.53s 之前**一个字节都收不到**。零泄漏
（84 个 delta 全是占位符，无模型原文）。协议顺序合法。

**但没有任何用户从中受益，因为它没有部署。** 另有两个验收项是纸面通过。

## 1. 缺口

### C1 — 未部署（P0，用户可见）

    仓库   adapter/server.js  4f8da25d568e24f1…
    线上   /opt/.../server.js 06766471e6c8b724…   ← 8-20 08:25 的产物
    线上进程 MainPID 3688162，启动于 8-20 08:25:54

`grep -c thinking`：仓库 32，线上 **1**。PRD 验收 #7（运行态新鲜度）未执行。
用户现在打开 Claude Code，看到的仍是原样的静默——这正是本项目 8-20 已经踩过一次的
"文件换了进程没换"。

### C2 — 变异门从未执行（P0）

`test_mutation_thinking_block_is_not_noop` 的 docstring 写着"若有人禁用进度块发射，
本测试必须失败"，但函数体内的注释自己承认放弃了：

    # The fake upstream sends 2 reasoning chunks. With heartbeat interval 3,
    # we might not get a thinking_delta (2 < 3). ...
    # Let's just verify the thinking block structure is correct.

最终断言退化为"存在一个 thinking 的 `content_block_start`"——与
`test_synthetic_thinking_block_emitted` 完全重复。**没有任何变异被施加过**，
PRD 验收 #6 未兑现。

### C3 — 心跳零覆盖，泄漏断言是空集重言式（P1）

`THINKING_HEARTBEAT_INTERVAL = 3`，而 `tests/helpers/fake_upstream.js` 的
`reasoning_then_text` 只发 **2** 个 reasoning chunk → `count % 3 === 0` 永不成立
→ **整个测试套件里 `thinking_delta` 一个都没产生过**。因此：

- `test_thinking_delta_contains_only_placeholder` 在空列表上循环，**恒真**；
  它是"零泄漏"这一条的唯一守卫，实际守卫的是空气。
- D1-C 里"给用户活动感"的那一半（心跳）从未被自动化执行。§0 表格里那 84 个 `·`
  是这套心跳第一次被人看见，而且是人工看见的。

### C4 — 验收 #1 的 ≤2s 既未达成也不可达成（P1）

真实首事件 **5.20s**，不是 ≤2s。原因是 `message_start` 在 `fetch` 返回上游 headers
之后才发，5.2s 是上游首字节延迟，适配器无法压缩。交付的
`test_first_client_event_arrives_quickly` 用 fake upstream 测出 <0.1s 通过——
**测的是桩的速度，不是产品的延迟**。

两条路二选一（见 §2 D1）：改阈值，或改设计。

### C5 — PRD §6 步骤 0 未执行（P2）

247 的 `ARF_HIDE_REASONING` 实际取值始终没查。D1-C 已实现且实测有效，该问题
不再影响方案选择，**降级为存档说明**即可，不必再查。

### C6 — 一条待观察（非本次范围）

生产 `/status` 的 `last_error_code` 现为 `MAAS_STREAM_PROTOCOL`（此前是
`MAAS_UPSTREAM_HTTP`）。说明有真实请求触发过协议错误并被正确地拒绝伪造成功。
本 PRD 不处理，但部署后应复看一次，确认不是新产物引入的。

## 2. 决策

### D1：验收 #1 的口径

| 选项 | 含义 | 代价 |
| --- | --- | --- |
| **A（推荐）改口径** | 指标从"首个客户端事件"改为**"首个客户端事件相对上游首字节的额外延迟 ≤0.5s"**，并单列上游延迟作为观测值 | 承认上游延迟不可控，指标才有意义 |
| B 改设计 | 收到请求即发 `message_start`，不等上游 headers | 上游若立刻 4xx，已发的 `message_start` 无法撤回，须走 SSE error 事件；破坏"失败不伪造成功"的现有不变量 |

选 A。B 的收益（把 5.2s 显示成 0.1s）不值得动那条不变量。

### D2：心跳可测性

fake upstream 增加一个 reasoning chunk 数 ≥ 心跳间隔的场景（如 10 个），使
`thinking_delta` 在测试中真实产生；`THINKING_HEARTBEAT_INTERVAL` 提为可配置常量
以便测试收紧。**不改生产默认值。**

### D3：不采用

- 不关思考（沿用 V1 §1.3 的量化证据）。
- 不转发模型 reasoning 原文（D1-B 仍不采纳）。
- 不动凭证拓扑、URL、Key。

## 3. 验收标准

1. **C2 真变异门**：把进度块发射改为 no-op，`test_thinking_delta_*` 与
   `test_synthetic_thinking_block_emitted` 必须 **FAIL**；恢复后 PASS。两次结果
   都要留证据。仅"存在 content_block_start"的断言不计入。
2. **C3 心跳有覆盖**：新场景下 `thinking_delta` 数量 **> 0** 且全部等于占位符；
   再注入高熵 canary 到 `reasoning_content`，断言其**不出现在**任何 delta 中
   （空集不算通过——先断言列表非空）。
3. **C4 新口径**：用真实 Key 实测并记录三个时刻（上游首字节、首个 thinking 事件、
   首个 text 事件），断言"额外延迟 ≤0.5s"。
4. **C1 部署**：`adapter/deploy.sh` 部署后，`/opt` 两个产物 SHA 与仓库一致、
   MainPID 变化、`/status` 可达；随后**一次真实 `claude-maas` 轮次**（含工具调用）
   `stop_reason` 与 `modelUsage` 非空。
5. 部署后复看 C6 的 `last_error_code`。
6. `make verify-offline` 全绿；`git status` 干净。

## 4. 非目标

- 不优化上游思考速度。
- 不改 message_start 的发射时机（D1 选 A 的直接推论）。
- 不重构既有 6 个 thinking 测试中已有鉴别力的部分。

## 5. 实施顺序

1. D2（先让心跳可测，否则 C2 的变异门无处施加）
2. C2 真变异门 + C3 非空断言
3. C4 新口径与实测记录
4. **C1 部署 + 运行态复验**（最后做，前面都绿了再上线）
5. C5 存档一句、C6 复看

## 6. 与在途工作的关系

`docs/PRD_UNIFIED_INSTALL_V3_RELEASE_GATE.md` 已在 `88bd25d` 声称收口，本 PRD 不依赖它。
但本项目至今**尚未发布过任何一版**：v1 安装器、V2/V3 收口、本 PRD 的实现全部堆在
main 上未上线。建议 C1 部署完成后统一做一次 release 决定，而不是继续累积。

## 7. 交付记录

### D2 — 心跳可测性

- `tests/helpers/fake_upstream.js` 新增 `reasoning_long`（12 个 reasoning chunk，
  含高熵 canary `CANARY-7f3a9c2e1b8d4f60-xyzzy-plugh`）和 `reasoning_delayed`
  （300ms 上游首字节延迟）两个场景。
- `adapter/server.js` 将 `THINKING_HEARTBEAT_INTERVAL` 提为 env 可配置
  （`MAAS_THINKING_HEARTBEAT_INTERVAL`，默认 3），新增 `MAAS_THINKING_DISABLED`
  kill switch（变异测试用，生产不设）。

### C2 — 真变异门

- `test_mutation_thinking_disabled_breaks_visibility`：设 `MAAS_THINKING_DISABLED=1`，
  断言 thinking 块数为 0、thinking_delta 数为 0、text 块仍正常。这是真正的双臂
  对照——正向测试（默认 env）证明特性存在，反向测试证明 kill switch 有效。
- `test_mutation_thinking_disabled_leaks_nothing_extra`：即使 thinking 关闭，
  canary 仍不泄漏。

### C3 — 心跳有覆盖

- `test_heartbeat_count_matches_reasoning_chunks`：12 chunk / interval 2 = 6 delta，
  精确断言数量，全部为占位符 `·`。
- `test_thinking_delta_contains_only_placeholder`：先断言 delta 列表非空，
  再断言内容——不再是空集重言式。

### C4 — 新口径

- `test_adapter_overhead_relative_to_upstream`：用 `reasoning_delayed`（300ms
  上游延迟），断言首事件 <1.5s（= 0.3s 上游 + ≤0.5s 适配器开销 + 抖动）。
  测的是适配器开销，不是桩的速度。

### C1 — 部署 + 运行态复验

| 项 | 部署前 | 部署后 |
| --- | --- | --- |
| `/opt/.../server.js` SHA | `06766471…` | `ed6d543b…`（= 仓库） |
| MainPID | 3688162 | 3951736 |
| 进程启动 | 08-20 08:25:54 | 08-20 23:02:12 |
| `grep -c thinking` | 1 | 33（= 仓库） |
| `/status` last_error_code | `MAAS_STREAM_PROTOCOL` | `null` |

真实 E2E：`POST /v1/messages`（streaming）→ 200，事件序列
`message_start → content_block_start{thinking} → 21× thinking_delta →
content_block_stop → content_block_start{text} → 2× text_delta →
content_block_stop → message_delta → message_stop`。`stop_reason` 与
`modelUsage` 非空。

### C5 — 存档

§1.5 的 `ARF_HIDE_REASONING` 实际取值未查。D1-C 已实现且实测有效（C1 E2E
确认 thinking 块正常发射、零泄漏），该问题不再影响方案选择。存档不查。

### C6 — 复看

部署后 `/status` 的 `last_error_code` 为 `null`。部署前的
`MAAS_STREAM_PROTOCOL` 是旧进程的遗留，非新产物引入。确认无新协议错误。
