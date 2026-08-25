# PRD — Upstream Profile V1（上游可配置化 + claude-glm 退出正式代码）

状态: 待实施
作者: Claude（事实经独立取证，非采信自述）
日期: 2026-08-24
被复核构建: `14154eb7297df8084135…`
前序: PRD_RELEASE_V12 / PRD_SECURITY_HARDENING_V1

---

## 0. 范围与决策记录

维护者决策（2026-08-24）：

1. **P-A**：`claude-maas` 项目的**模型、API URL、API key 三者均可配置**。
2. **P-B**：`claude-glm` **不作为正式代码提交**，仅在 83.10 临时使用。

两条决策相互耦合：**P-A 做完后，P-B 才有干净的落地方式** —— 参数化之后
`claude-glm` 不再需要是一份分叉代码，它退化成一份**本地配置**，
从而不再重新打开 SECURITY_HARDENING_V1 的 S9（「未纳管可执行文件进入 PATH」）。

本 PRD 不新增产品功能，只把已经存在的隐式可配置性显式化。

---

## 1. 现状：哪些已经可配置，哪些没有

### 1.1 已经可配置（我今天在生产上实测验证过）

运行时三要素**已经是 env 驱动**的。我今天把 `:3000` 的上游从华为 MaaS
切到智谱、再切回来，全程只改 `/etc/claude-code-proxy/maas.env`，未改一行代码：

| 变量 | 作用 | 证据 |
| --- | --- | --- |
| `CLAUDE_CODE_PROXY_API_KEY` | 上游 API key | 切换后智谱请求 200 |
| `ANTHROPIC_PROXY_BASE_URL` | 上游 URL | 启动日志打印新 URL 生效 |
| `COMPLETION_MODEL` | 模型名 | `adapter/server.js:36` 为 `COMPLETION_MODEL \|\| "glm-5.2"`，字面量只是默认值 |

客户端侧同样已参数化：`client/claude-maas` 的模型取自
`~/.config/claude-maas/config.json`，源码里的 `glm-5.2` **只出现在注释**
（第 5、197 行）。

**结论：适配器与启动器不是阻塞项。** 阻塞在验证层与文档层。

### 1.2 架构不变量并不禁止换模型

`docs/PRD.md:148、438` 原文是「**单模型单上游**、无路由决策、无 fallback」。
该约束讲的是**每个实例的基数**（一个实例只服务一个模型、一个上游），
**不是** 绑定字面量 `glm-5.2`。因此 P-A 与架构不变量**不冲突**。

但文档从未把这点写清楚，导致「单模型 glm-5.2」被当成了不变量本身
（`RELEASE_NOTES_v1.2.md` 的范围声明即如此表述）。需要澄清，见 D4。

### 1.3 真正没有参数化的部分

| 位置 | 内容 | 影响 |
| --- | --- | --- |
| `tests/claude_e2e_probe.sh:27` | `MODEL="glm-5.2"`，并断言 `modelUsage` 恰为该模型 | 换模型后 **live 门禁必红** |
| `tests/claude_maas_launcher_probe.sh:12` | 同上 | 同上 |
| `scripts/verify.sh:652` | 发布证据 JSON 写死 `model`/`endpoint_host`/`endpoint_path` | **证据失真**，见 D3 |
| `scripts/verify.sh:286` | 匿名鉴权探针体内写死 `"model":"glm-5.2"` | 仅影响可读性（该探针只断言 401，模型值不参与判定） |
| `scripts/bootstrap.sh:35` | `DEFAULT_MODEL="glm-5.2"` | 默认值，可保留 |

---

## 2. 缺陷

### D1 (P1) — 验证层写死模型，换上游即全红

`verify.sh` 调用的两个探针脚本把 `glm-5.2` 作为字面量断言。
只要 `COMPLETION_MODEL` 不是 `glm-5.2`，`make verify-live` 必然失败，
**而失败原因与被测系统的健康程度无关**。这是一条没有鉴别力的门禁：
它测的是"部署是否等于某个历史常量"，不是"部署是否自洽"。

修复方向见 D2。

### D2 (P1) — 门禁应断言"自洽"，而非断言字面量

正确的判据是**部署内部一致性**：

```
COMPLETION_MODEL (env file)
  == config.json.model (客户端)
  == modelUsage 中实际返回的模型 (探针实测)
```

三者一致即 PASS，与具体取值无关。这样换任何模型都不需要改门禁，
而"客户端与服务端模型配置不一致"这类真实故障反而**第一次**被覆盖到
（当前门禁完全看不到它）。

### D3 (P1) — 发布证据 JSON 由字面量拼装，当前已与生产不符

`scripts/verify.sh:652` 附近：

```
"endpoint_host": "api-ap-southeast-1.modelarts-maas.com",
"endpoint_path": "/anthropic",
"model": "glm-5.2",
```

而生产 `maas.env` 实际是：

```
ANTHROPIC_PROXY_BASE_URL=https://api-ap-southeast-1.modelarts-maas.com/v2/chat/completions
```

**`endpoint_path` 已经是错的**（`/anthropic` vs `/v2/chat/completions`），
且这个错误与本次改动无关 —— 它一直在，因为证据是"写出来的"而不是"读出来的"。
发布证据的价值在于记录**实际验证了什么**；由常量拼装的证据不具备该价值。

修复：三个字段全部从部署配置解析得到，禁止字面量。

### D4 (P2) — 不变量表述需澄清

`docs/PRD.md` 与 `RELEASE_NOTES_v1.2.md` 需明确：
不变量是「**每个适配器实例**单模型单上游、无路由、无 fallback」，
**不是**「产品只支持 glm-5.2」。否则 P-A 会被后来者当成违反架构。

### D5 (P2) — 上游状态码未透传（实测）

实测：智谱返回 `HTTP 429`（`您的账户已达到速率限制`）时，
适配器向客户端返回 **502**。`server.js` 的 `!upstream.ok` 分支写的是
`upstream.status || 502`，本应透传 429，说明该请求实际走了 catch 路径。

后果：客户端（Claude Code）无法区分"上游限流，应退避重试"与
"上游故障"，拿不到 `Retry-After` 语义。需定位并修复，使 4xx 上游状态码
按原值透传（5xx 可继续统一为 502）。

### D6 (P2) — 缺少上游兼容矩阵

不同上游行为差异已实测到，但无处记录：

| 上游 | 格式 | 实测差异 |
| --- | --- | --- |
| 华为 MaaS `/v2/chat/completions` | OpenAI | 基线；未观察到限流 |
| 智谱 `open.bigmodel.cn/api/paas/v4/chat/completions` | OpenAI | **限流很紧**：连续请求即 `429`，约 80s 恢复；返回 `reasoning_content`；工具调用正常 |

Claude Code 是高频连续调用的客户端，智谱的限流会实际影响可用性。
需建立 `docs/UPSTREAMS.md` 记录每个受支持上游的实测行为与已知限制。

---

## 3. 设计

### D7 — 启动器支持 profile（P-B 的前提）

`client/claude-maas` 第 26–29 行的四个路径改为由单一变量派生：

```bash
profile="${CLAUDE_MAAS_PROFILE:-claude-maas}"
config_dir="$HOME/.config/$profile"
config_file="$config_dir/config.json"
key_file="$config_dir/api-key"
claude_config_dir="$HOME/.$profile"
```

自指排除逻辑（第 49、67 行）改为按 `$self_path` 比较，去掉按名字的硬编码。

**效果**：`claude-glm` 不再需要是一份分叉的可执行文件，而是

```bash
CLAUDE_MAAS_PROFILE=claude-glm claude-maas ...
```

或一个本地的一行 wrapper。**S9 不会重新打开**，因为 PATH 里不再有
任何未纳管的可执行代码。

### D8 — bootstrap 支持 `--profile`

把我今天手工做了三遍的隔离动作固化：`--profile <name>` 时统一派生
`/etc/claude-<name>-proxy/`、`/opt/claude-<name>-proxy/`、
`claude-<name>-proxy.service`、`~/.config/claude-<name>/`，
每个 profile **独立生成 client key**（互不通用，我已实测两套 401 交叉拒绝），
systemd 加固指令与主 profile 完全一致。

`--profile` 缺省为 `claude-maas`，现有安装路径与行为完全不变。

### D9 — claude-glm 退出正式代码（P-B）

1. `git rm client/claude-glm`，从仓库移除；
2. 83.10 上的 `~/.local/bin/claude-glm` 改为**不指向仓库内文件**
   —— 用 D7 的 profile 机制（wrapper 放 `/usr/local/lib/claude-glm-local/`，
   明确标注 local-only、不受支持）；
3. `docs/OPERATIONS.md` 增一节「本地临时 profile」，写明：
   - 该部署**不在发布范围内**、不进 release notes 的支持矩阵；
   - 但**必须满足与正式 profile 相同的安全水位**（enforced 鉴权、
     构建与 repo 一致、systemd 加固）—— 当前 83.10 的 `:3100` 已满足，实测：
     `glm key -> :3000 = 401`、`maas key -> :3100 = 401`、`anonymous -> :3100 = 401`；
4. `scripts/window-check-v12.sh` 的 **N1-G 需改写**（见 D10）。

### D10 — N1-G 从「单监听」改为「每个监听都合规」

原断言「除 `:3000` 外无本项目派生监听」在维护者决定保留 `claude-glm`
之后已不成立，当前为红。改写为：

> 主机上每一个本项目派生的监听都必须满足：
> (a) `sha256(server.js)` 与 repo 一致；
> (b) enforced 鉴权（匿名与其他 profile 的 key 均返回 401）；
> (c) systemd unit 含全部加固指令。

该判据对"多 profile"友好，同时**保留了原门禁真正想防的东西**
（未纳管、未加固、无鉴权的克隆进程 —— 即 N2 的 `:3001` 那类）。

---

## 4. 验收门禁

沿用项目规矩：**每条必须附「回退修复后该门禁 FAIL」的证据**。

| 门 | 断言 | 反向用例 |
| --- | --- | --- |
| G1 | `COMPLETION_MODEL` == `config.json.model` == 探针实测 `modelUsage` 键，三者一致即 PASS，不比对字面量 | 把 `config.json.model` 改成别的值后必须 FAIL（当前门禁**不会**发现该不一致） |
| G2 | 以 `COMPLETION_MODEL=<非 glm-5.2>` 跑 `verify-live` 全绿 | 保留字面量断言时必须 FAIL |
| G3 | 发布证据 JSON 的 `model`/`endpoint_host`/`endpoint_path` 与部署 env 逐字段相等 | 改回字面量拼装后必须 FAIL（**当前即为红**：`/anthropic` vs `/v2/chat/completions`） |
| G4 | `CLAUDE_MAAS_PROFILE=X` 时读 `~/.config/X/`、会话写 `~/.X/`；缺省仍为 `claude-maas` | 恢复硬编码路径后必须 FAIL |
| G5 | `--profile X` 安装出的实例：独立 client key、与主 profile 交叉鉴权互拒 401、unit 加固齐全 | 复用同一 client key 后必须 FAIL |
| G6 | `git ls-files client/` 不含 `claude-glm`；且 PATH 中不存在仓库外的未纳管可执行文件 | 把 claude-glm 加回仓库后必须 FAIL |
| G7 | 上游返回 429 时客户端收到 429（非 502） | 修复前必须 FAIL（**当前即为红**，已实测） |

G3 与 G7 **修复前即为红，无需另造反向用例**。

---

## 5. 与发布的关系

- 本 PRD **不阻塞** v1.2 的既有安全修复，但 **G1/G2/G3 未完成前不应声称
  "上游可配置"** —— 运行时确实可配置，验证层不可配置，对外承诺会落空。
- D9/D10 必须与 `PRD_RELEASE_V12` 的 N1 决策记录同步更新：
  该决策已由维护者从 **A（下线）改为 B（保留并纳管）**，
  V12 文档与 `window-check-v12.sh` 目前仍写着 A，属陈旧记录。
- D6 的智谱限流应进 `RELEASE_NOTES` 的已知限制：
  **`claude-glm` 在高频 agent 任务下会撞 429**，这是账号档位问题，不是代码缺陷。

## 6. 建议顺序

1. **D7 + D9 + D10**（claude-glm 退出代码，同时关掉 N1-G 的红）
2. **D1/D2 + D3**（验证层去字面量化，G1/G2/G3）
3. **D8**（bootstrap `--profile`，把手工动作固化）
4. **D4 + D6**（文档澄清与上游矩阵）
5. **D5**（429 透传）

第 1 步同时兑现 P-B 并修复一条当前为红的门禁，收益最高。
