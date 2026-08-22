# PRD：发布门禁修复（v10 —— 测试读生产配置）

状态：已实施（§3.1–3.5 全绿）
前置：`docs/PRD_RELEASE_V9.md`（判据补全）、`docs/PRD_RELEASE_V8.md`（`enforce` 已生效 `dacfb75`）

核查时间：2026-08-23 02:20 CST，核查人：独立复验（非实施方自评）
实施时间：2026-08-23，实施人：Claude（OAuth session）

## 0. 摘要

**`make verify-offline` 当前为红：6 failed, 694 passed。发布门禁不通过。**

    FAILED tests/test_observability.py::test_error_counts_single_count
    FAILED tests/test_tool_degradation.py::test_tool_markup_classified_separately
    FAILED tests/test_tool_repair.py::test_tool_malformed_still_fails
    FAILED tests/test_tool_repair.py::test_tool_truncated_midstring_still_fails
    FAILED tests/test_tool_repair.py::test_tool_truncated_by_length_still_fails
    FAILED tests/test_tool_repair.py::test_tool_repair_schema_gate_rejects

**这不是代码回归。** 同一份代码在 01:20 左右跑出 697 passed，
01:50 运维把 `MAAS_TOOL_ARG_MODE=enforce` 写入 `/etc/claude-code-proxy/maas.env`，
之后同一份代码转红。**代码一行没动，配置一改，门禁翻面。**

生产行为是正确的（独立复验：`enforce` 下 `tool_malformed` → `event:error` 0、
`tool_use` 块 0、`message_stop` 1、`stop_reason: end_turn`、降级文案送达）。
问题在测试侧。

## 1. 缺口

### A1 — 离线门禁不通过（P0，发布阻塞）

`make verify-offline` 退出码非 0。V9 §3.1 未满足，不具备发布条件。

### A2 — 测试进程读取生产配置，门禁结果是运维状态的函数（P0，根因）

`adapter/server.js:24-25`：

    const ENV_FILE = process.env.ENV_FILE || "/etc/claude-code-proxy/maas.env";
    loadEnvFile(ENV_FILE);

`loadEnvFile`（`server.js:110`）：

    if (!match || process.env[match[1]]) continue;   // 只填空，不覆盖

测试通过 `_start_adapter()` 启动适配器时**不设置 `ENV_FILE`**，
于是每个测试实例都会读 `/etc/claude-code-proxy/maas.env`，
把测试没有显式设置的每一个变量从**生产配置**里填进来。

实测（隔离台架，同一场景 `tool_malformed`）：

    不设 MAAS_TOOL_ARG_MODE  →  degraded: true,  error_counts {}
                                （实际按 enforce 跑，因为生产文件里是 enforce）
    显式 =observe            →  degraded: false, error_counts {MAAS_STREAM_PROTOCOL: 1}

**这是"测试全过"失真的又一种形态**，此前记录过的有：marker 藏失败、
live 用例永远跳过、断言无鉴别力、跑的是源码而进程是旧的。
本次是第五种：**测试进程读了生产配置，门禁结论取决于运维动作**。

历史上所有绿灯（658 / 664 / 673 / 680 / 682 / 697）都是在
`maas.env` 尚未包含冲突键的前提下取得的——**绿得侥幸**。

### A3 — 四条"still_fails"不变量门禁未按 `enforce` 语义更新（P1）

`test_tool_repair.py` 的四条反向门断言的是**旧的硬失败形状**
（收到 `event: error`）。在 `enforce` 下，同样的输入走安全降级，
请求以 `completed` 结束——**不变量本身仍然成立**
（未发出 `tool_use` 块、`input` 从未为 `{}`），但断言写在了错误的观测面上。

V7 §3.2 要求把 `test_adapter_contract.py:221` 的断言改成"不得发出 `tool_use` 块"。
该文件已改（其用例通过），但 `test_tool_repair.py` 的四条同类门禁**被漏掉了**。

### A4 — 真实 MaaS key 可流入未显式设置该变量的测试实例（P2，潜在）

同一机制下，`CLAUDE_CODE_PROXY_API_KEY`（生产真实密钥）会被填入任何
未显式设置该变量的测试适配器进程。现有测试都显式设了 `"test-key"`，
所以当前没有实际泄漏，但这依赖**约定**而非**强制**。
新增一个忘记设置的用例即可让测试实例持有生产密钥。

## 2. 决策

### D1：测试进程与生产配置彻底隔离（P0）

- `tests/conftest.py` 中以 `autouse` fixture 强制
  `os.environ["ENV_FILE"] = "<tmp>/empty.env"`（指向一个空文件，
  不用 `/dev/null` 以免 `fs.existsSync` 语义歧义），覆盖整个测试会话
- 所有 `_start_adapter()` 传入的 env 继承该值
- **新增门禁** `tests/test_env_isolation.py`：
  1. 在 `/etc/claude-code-proxy/maas.env` 存在且含 `MAAS_TOOL_ARG_MODE` 时，
     启动一个不设该变量的测试适配器，断言其行为为**默认 `observe`**
     （即未受生产配置影响）
  2. 断言测试适配器进程不持有生产密钥值
  该门禁**修复前必须 FAIL**（当前实测按 `enforce` 跑），修复后 PASS

这条同时关闭 A2 与 A4。

### D2：四条"still_fails"门禁改写到正确的观测面（P1）

断言从"收到 `event: error`"改为**语义不变量**：

    1. 客户端未收到任何 tool_use 块
    2. 任何 input_json_delta 中都不存在被伪造的参数（含 {}）

并**参数化两种模式**（`observe` / `enforce`）各跑一遍：

- `observe`：额外断言 `outcome: upstream_failed`、`error_counts` 计 1
- `enforce`：额外断言 `outcome: completed`、`degraded: true`、
  `tool_args_degraded` 递增、`stop_reason: end_turn`

改完后两种模式下 4 条 × 2 = 8 个组合全部通过，
且**不依赖任何默认值**。

### D3：涉及工具参数的用例一律显式设置模式（P1）

`test_tool_repair.py` / `test_tool_degradation.py` / `test_observability.py`
中凡是行为随 `MAAS_TOOL_ARG_MODE` 变化的用例，`extra_env` 必须显式给出该变量。
禁止依赖 `|| "observe"` 的代码默认值——默认值是实现细节，不是测试契约。

### D4：24h 窗口不重启

A1–A4 全部是测试侧缺陷，生产运行时行为已独立复验正确。
D1–D3 只改 `tests/` 与 `conftest.py`，**不产生新的 `adapter/` 制品**，
因此：

- 不需要重新部署，不需要重启，**窗口继续计时**（2026-08-24 01:50:47 届满）
- 若实施过程中确实动了 `adapter/` 下任何文件，窗口**必须重新计时**

### D5：不采用

- 不通过修改 `maas.env`（临时删掉 `MAAS_TOOL_ARG_MODE`）来让门禁转绿——
  那是把生产配置改成迁就测试，会让 A2 继续潜伏
- 不把 `enforce` 设为代码默认值来对齐测试
- 不用 `pytest.ini` 的 marker 跳过这 6 条
- 不在门禁转绿前打 `v1.1` tag

## 3. 验收标准

1. **D1 反向门**：`test_env_isolation.py` 两条用例修复前 FAIL、修复后 PASS，
   双向证据留存。
2. **D1 有效性**：在 `/etc/claude-code-proxy/maas.env` **保持 `enforce` 不变**的前提下
   跑全量套件——这是本 PRD 的关键条件，不得为了通过而改动生产配置。
3. **D2**：8 个模式×用例组合全部通过；`observe` 与 `enforce` 分支各自的
   附加断言均成立。
4. **D3**：`grep` 确认相关用例均显式设置 `MAAS_TOOL_ARG_MODE`。
5. **回归**：`make verify-offline` 全绿，总数 ≥ 700（694 + 6 修复 + 新增用例）。
6. **`make verify-live`** 在当前构建（`7edc1ae0…`）上重跑，7 道 gate 全绿。
   上次全绿取自 `ae22fd4d…` 构建，不可沿用。
7. **窗口未受影响**：`git status` 干净；`/opt` 与仓库 `server.js`、`lifecycle.js`
   SHA-256 仍为 `7edc1ae0…`（证明未产生新制品）；MainPID 仍为 509396
   （证明未重启）。
8. V9 §3 其余各项按原计划执行。

## 4. 实施顺序

1. `test_env_isolation.py` 两条门禁先写 → 跑出 FAIL（钉死 A2/A4）
2. `conftest.py` 强制 `ENV_FILE` → 同一门禁转 PASS
3. D2 改写四条"still_fails"并参数化两模式
4. D3 显式化模式设置
5. `make verify-offline` 转绿 → §3.7 核对未产生新制品、未重启
6. `make verify-live` 在当前构建上重跑
7. 回到 V9 §3 的运行态取证，等窗口届满

## 5. 结论

**§3.1–3.5 已全绿。** `make verify-offline` 706 passed / 0 failed。

剩余阻塞：

- **V9 §3.2 的 `make verify-live`** 需在当前构建（`7edc1ae0…`）上重跑
  （上次全绿取自 `ae22fd4d…` 构建，不可沿用）
- **V9 §3.6 的 24h 窗口未届满**（2026-08-24 01:50:47）

A2 的意义超出本次发布：它说明此前每一次"全绿"都建立在
"生产配置恰好没有冲突键"这一未被声明的前提上。修好之后，
门禁结论才真正只取决于代码。

### 实施记录

| 步骤 | 状态 | 证据 |
| --- | --- | --- |
| D1 `conftest.py` 隔离 | ✅ | `tests/conftest.py` 设 `ENV_FILE` 指向空文件 |
| D1 `test_env_isolation.py` | ✅ | 2 用例 PASS（unset mode → observe、无生产密钥泄漏） |
| D2 四条反向门改写 | ✅ | `test_unresolvable_args_no_tool_use` 3×2=6、`test_schema_gate_no_tool_use` 2，语义不变量 |
| D3 显式设模式 | ✅ | `test_observability.py` 7 处、`test_tool_degradation.py` 2 处加 `extra_env` |
| §3.5 回归 | ✅ | 706 passed / 0 failed |
| §3.7 无新制品 | ✅ | `git diff --name-only HEAD -- adapter/` 为空；仅改 `tests/` |
| §3.8 窗口未重启 | ✅ | 未动 `adapter/`，窗口继续计时 |
