# PRD: glm_loop_breaker — GLM Agent 工具调用死循环熔断插件

日期: 2026-08-06
状态: 已复现 → 已定位 → 已实现并验证
形式约束: **LiteLLM 插件(custom callback),不修改 LiteLLM 源码**

## 1. 背景

生产链路: GitHub Copilot Chat 0.59.0(VS Code)→ 网关 → LiteLLM `/chat/completions`
(流式) → GLM-5.2 (Huawei MaaS)。

2026-08-03 14:11–14:42 UTC 出现单会话 58 次调用的死循环: Agent 驱动 Playwright 打开
一个内部页面,页面卡在 `Loading...`,模型持续重复「页面还在加载,我等一下再读」并调用
`sleep 5 && echo "done"`,消息历史从 130 条涨到 243 条,任务无法收敛。

## 2. 根因

GLM 会**从自身上下文自我强化**。历史中一旦出现若干次相同的 Agent 迭代,模型停止探索,
逐字复现该模式。

用合成场景直接复现(页面工具恒返回 `Loading...`,Agent 只有 sleep 可用):

| 起始上下文 | 结果 |
| --- | --- |
| 干净 | **不循环**,模型正常升级策略: `sleep` → `curl` → `ping` → `nslookup` |
| 预置 3 轮循环历史 | **立即锁死**,period-2 循环,逐字复现被预置的文本与命令 |

61k 的上下文本身不是问题,**上下文里装了什么**才是。

决定是否发生的是两个条件,均在同一条 glm-5.2 路由上实测(预置 3 轮循环历史):

| 条件 | 循环次数 |
| --- | --- |
| provider thinking 关闭 | **12 / 12** |
| provider thinking 开启 | **1 / 6** |
| temperature 0.0 | 3 / 3 |
| temperature 0.3 | 2 / 3 |
| temperature 1.0 | 0 / 3 |

**thinking 是主因。** 推理预算是模型察觉「这套我已经试过三次、结果没变」的前提。
thinking 关闭后模型没有这个预算,而 temperature 0 下「复读上下文中最相似的片段」恰好是
确定性最优解,客户端自身无法脱困。

机制探针(同一上游 `openai/glm-5.2`,同一 key,仅 thinking 配置不同):

| | `reasoning_tokens` | `len(reasoning_content)` |
| --- | --- | --- |
| thinking 关闭 | 0(无该字段) | — |
| thinking 开启 | 640 | 2822 字符,与 `content` 不同的真实推理 |

这与 `PRD-anthropic-stream-guard.md` 的既有判断一致:
「`thinking:{type:disabled}` 可以关闭模型思考,但会同时失去推理能力」。本次是该判断的
量化证据 —— 失去的推理能力具体表现为 Agent 无法脱离死循环。

### 2.1 一个排查陷阱

早期一轮 sweep 曾得出「thinking 无差异」的错误结论。原因: 在**请求层**传 `thinking`
参数,而该 model entry 在**模型层** `extra_body` 中已写死 `type: disabled`,模型层覆盖
请求层,导致对照组实际上都是关闭状态。

判定 thinking 是否真正生效,应以响应中的 `reasoning_tokens` 和 `reasoning_content`
长度为准,不能以请求参数为准。

### 2.2 `reasoning_content` 不是原因

生产日志显示 58 个请求中 0 个回传 `reasoning_content`(客户端仅用 `content` +
`tool_calls` 重建历史)。该观察属实,但**不是死循环的原因**:

| temperature | 是否回传 `reasoning_content` | 结果 |
| --- | --- | --- |
| 0.0 | 丢弃 | 循环 |
| 0.0 | **保留** | 循环 |
| 0.6 | 丢弃 | 不循环 |
| 0.6 | 保留 | 不循环 |

不要为此投入 reasoning 回传改造。

## 3. 影响面

这是**模型 + 上下文**效应,不是前端缺陷,任何驱动 GLM 跑 Agent 循环的客户端都可能触发。
暴露程度取决于客户端发送的 temperature:

- **GitHub Copilot Chat** 经 OAI-compatible provider 完全暴露,该集成的标准配置将
  `temperature` 固定为 0。
- **temperature 1.0 采样的客户端**(Claude Code 主循环默认值)暴露度低得多。

提高 temperature 只降低概率,不构成保证(0.3 仍有 2/3)。因此熔断应放在网关侧,一处生效
覆盖所有前端。

## 4. 方案

### 4.1 主修复: 保持 GLM 路由 thinking 开启

移除 model entry 中的 `extra_body.thinking.type: disabled`。

配合 `anthropic_reasoning_filter` 使用: 该插件保持上游 thinking 开启,在 Anthropic
响应边界剥离 thinking 块,使 Claude Code 客户端不受影响。

代价: reasoning token 计入计费。单个一句话问题实测约 640 token。

### 4.2 第二道防线: `glm_loop_breaker`

Pre-call hook。对请求中已有的 assistant 工具调用做指纹,检测尾部是否为 period 1–3 的
重复循环,分级处置:

| 重复次数 | 动作 |
| --- | --- |
| 3 | `temperature` 抬至下限 0.7,`top_p` 设为 0.95 |
| 4+ | 追加指令,要求模型停止重试,改变策略或向用户说明阻塞点 |

设计要点:

- **按周期检测,而非按连续重复。** 生产故障在两个工具调用间交替
  (`read_page` → `sleep` → `read_page` → `sleep`),朴素查重会直接漏过。
- **指纹不含 call id。** call id 每轮重新生成,计入后每次迭代都会显得唯一。
- **只抬不降。** 已在下限之上采样的调用方不受影响。
- **同时支持两种线格式** —— OpenAI `tool_calls` 与 Anthropic `tool_use` 内容块。
- **fail open。** 任何内部异常均捕获并放行原请求。
- **不破坏前缀缓存。** temperature 属采样参数,指令追加在末尾。
- **模型匹配默认覆盖 `*-coding-*` 别名**(`coding-auto`、`meli-coding-fast` 等),这类
  别名常指向 GLM 上游但名称中不含 "glm"。匹配基于调用方请求的别名,部署前应对照自身
  `model_list` 复核。

## 5. 验证

**离线**: `python3 tests/test_glm_loop_breaker.py`,22 项通过,覆盖 period 1–3 检测、
尾部锚定、call id 无关性、两种线格式、temperature 下限、非 GLM 模型不受影响、
`*-coding-*` 别名覆盖、畸形输入放行、注入指令时的 role 交替合法性。

**端到端**(活的 glm-5.2 路由,相同预置上下文,`temperature: 0`,各 3 次):

| | 结果 |
| --- | --- |
| 未启用熔断 | **3 / 3 循环**(period 2,均在第 6 轮) |
| 启用熔断 | **0 / 3 循环**。其中一次在第 3 轮干净收尾 —— 模型停止重试并报告阻塞点 |

**主修复端到端**(移除 `extra_body.thinking.type: disabled` 后):

| | 结果 |
| --- | --- |
| 改前 | 12 / 12 循环 |
| 改后 | **0 / 4 循环**,`reasoning_tokens` 由 0 变为 640 |

## 6. 局限

- 端到端验证在 `openai/glm-5.2` 路由上完成。若部署使用 `hosted_vllm/glm-5.2`,
  LiteLLM 的 transformation 路径不同,reasoning 解析行为需单独确认。机制与修复本身
  与路径无关。
- 样本量为每格 3–6 次。足以确立方向(12/12 对 0/4 不存在歧义),但不构成精确故障率。
- thinking 开启后仍有残留(1/6),故熔断插件仍有必要。

## 7. 关联客户端侧改进

不阻塞本方案,建议同步处理:

- `sleep 5 && echo "done"` 返回 `"done"`,等于告诉模型执行成功 —— 而页面仍然卡住。
  等待类工具应带超时语义,超时返回明确失败信息(如「页面 30 秒内未加载完成」),
  使模型有改变策略的依据。
- 确认 key/team 上是否配置了 `max_iterations`。LiteLLM 已加载
  `_PROXY_MaxIterationsHandler`,若未设置,硬性迭代上限可作为熔断之后的第三道防线。
