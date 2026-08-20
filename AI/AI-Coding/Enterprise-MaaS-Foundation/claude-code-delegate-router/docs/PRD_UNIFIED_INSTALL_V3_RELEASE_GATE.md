# PRD：统一安装脚本发布门禁收口（bootstrap v3）

状态：已交付
前置：`docs/PRD_UNIFIED_INSTALL_V2_CLOSURE.md`（已交付 a7f0dbc）

## 0. 产品摘要

v2 的功能是对的：两次真实全路径安装（隔离 service/port/dest/HOME、真 systemd、
真上游，只变 Key 一个变量）验证了 G1 代码成立——无效 Key → exit 4，有效 Key →
exit 0。632 passed 属实，test_g6_systemd_full_path 确实实跑 systemd。

挡住 release 的不是功能，是**门禁本身**。v3 只做三件事，不改任何安装行为：

1. **R3**：测试摘掉生产端口 3000，否则后两条的测量都不可信。
2. **R2**：verify 的 /status 轮询改为按时间判定，上限 15s。
3. **R1**：G1 反向门重写为双臂对照 + 变异测试。

## 1. 证据与缺口

### R1 — G1 的反向门是重言式（P0）

`test_g1_invalid_key_fails_verify_with_exit_4` 传了 `--skip-systemd`，适配器
根本没起，exit 4 来自 PATH 检查 / stage 1，跟 Key 有没有效没有关系。把整个
上游 canary（V2 存在的唯一理由）改成恒真再跑：

    MUTATION applied: upstream canary always passes
    test_g1_invalid_key_fails_verify_with_exit_4  →  1 passed in 0.43s

删掉被测特性，门禁依然全绿。PRD V2 §4 要求"先证明它在修复前失败"，这一条
没兑现。（test_g2 在同一变异下通过是对的——G2 的门禁成立。）

### R2 — G4 的轮询上限是 5s，不是 PRD 要求的 ≥10s（P1）

`sleep 0.5` 但计数器每轮 `+1`，`_POLL_DEADLINE=10` → 实际 10 轮 × 0.5s = 5s。
对无人监听的端口计时：

    整个 bootstrap 耗时: 5.409157216s
    bootstrap: verify: FAIL — ... not reachable on port 3099 after 10s

文案把 5s 报成 10s，误差 2 倍且方向是让人以为等得更久。生产部署时实测撞到过
restart 后 0ms 连不上，等待窗口是这条门禁唯一的抗抖动手段。

### R3 — 测试打到生产（P1）

`test_g1` / `test_g2` 都不传 `--port`，落到默认 3000 = 本机生产端口：

    bootstrap: verify: adapter /status ok (port 3000)      ← 生产服务应答的
    生产 /status → last_error_code: "MAAS_UPSTREAM_HTTP"    ← 测试拿假 Key 打上游留下的指纹

于是 `make verify-offline` 每跑一次，就有一把假 Key 经生产适配器向真实 MaaS
发一次请求；而在没有生产服务的全新机器上，用例会走另一条失败路径然后"依然
通过"——通过的理由完全变了。

## 2. 决策

### 2.1 采用

- **R3 先做**：所有 V2 测试使用隔离的高端口（≥30000），不碰 3000。
- **R2**：轮询改为按时间判定（`SECONDS` / `date +%s`），上限 15s；错误消息
  报告实际经过的时间，不是 deadline 常量。
- **R1**：重写为双臂对照——同一隔离环境只变 Key 一个变量：
  - 无效 Key 臂 → exit 4，stderr 指出 upstream canary failed
  - 有效 Key 臂 → exit 0（需要真实 Key；缺 Key 时显式 skip 并在 CI 摘要列出）
  - 变异测试：canary 恒真时 G1 用例必须 FAIL
- **不改安装行为**：bootstrap.sh 的安装步骤不变，只改 verify 的轮询实现和
  测试的端口/Key 隔离。

### 2.2 不采用

- 不改 verify 的三段结构（local /status + PATH + canary，V2 已定）。
- 不改 `--verify-live` / `--no-verify-live` 语义。
- 不改 `--config-dir`、`--user`、`--skip-verify` 等接口。
- 不引入新的安装能力。

## 3. live 用例约束

v3 新增的"有效 Key 臂"是 live 用例——它向真实 MaaS 发请求。约束：

1. **Key 来源**：从 `/etc/claude-code-proxy/maas.env` 读取
   `CLAUDE_CODE_PROXY_API_KEY`（root 拥有，0600）。不从环境变量、不从 argv。
2. **缺 Key 时显式 skip**：`pytest.skip("no real MaaS key available — G1
   valid-key arm skipped (listed in CI summary)")`。不许静默通过。
3. **端口隔离**：使用 ≥30000 的动态端口，不碰 3000。
4. **清理**：finally 块停止/禁用/删除临时 systemd unit，daemon-reload。

## 4. 验收标准

每一条都要求**先证明它在修复前失败**（反向门），再证明修复后通过。

1. **R3**：`grep -r '3000' tests/test_bootstrap.py` 不出现在任何 `--port`
   或默认端口上下文；所有 V2 测试使用 ≥30000 的端口。修复前 test_g1/test_g2
   打到生产 3000。
2. **R2**：对无人监听的端口计时，verify 轮询实际等待 ≥15s（±1s 容差）；错误
   消息报告的实际经过时间与计时一致。修复前实际等待 5s 但报 10s。
3. **R1 双臂**：
   - 无效 Key 臂：exit 4，stderr 含 "upstream canary"
   - 有效 Key 臂：exit 0（或显式 skip）
   - **变异门**：将 bootstrap.sh 的 canary 调用 stub 为恒真，G1 用例必须
     FAIL。修复前（v2）变异后仍 PASS。
4. `make verify-offline` 全绿，新增测试数 ≥ 3。
5. `git status` 干净。

## 5. 非目标

- 不改安装行为（env file、systemd unit、adapter deploy、client config）。
- 不改凭证拓扑。
- 不改 `adapter/` 的协议行为。
- 不自动获取 MaaS Key（live 用例从 env file 读，不交互）。

## 6. 实施顺序

1. R3（摘端口——否则 R1/R2 的测量都不可信）
2. R2（轮询改按时间判定、上限 15s）
3. R1（双臂对照 + 变异测试）
4. 验收 + 提交

## 7. 已验证、v3 不必重做的部分

以下在 v2 已实测验证，v3 不改这些行为，可直接进 release note：

- **G3**（`--user` 优先级）：`--user root` + `SUDO_USER=nobody` → root。门禁成立。
- **G5**（URL 校验错误路径）：`die()` 分支可达，消息含 `bootstrap:` 前缀。
- **G7**（`--config-dir` 隔离）：自定义目录生效，端口不匹配时 WARNING。
- **G6**（systemd 全路径）：test_g6 实跑 systemd，断言 active + /status version。
- **G2**（PATH 检查）：launcher 不在 PATH → exit 4。变异测试（canary 恒真）
  不影响 G2，门禁成立。
- **凭证拓扑**：真实 Key 只进 root-owned env file，客户端拿 dummy key。
- **幂等性**：重跑 bootstrap，env file + artifacts 稳定。
- **Key 不入 stdout/argv/用户 home**：v1/v2 既有断言，v3 不回退。
- **`--dry-run` 无副作用**：env file mtime 不变。
- **prohibited-dependency scan**：bootstrap.sh 不引入 litellm/CCR/openrouter。
