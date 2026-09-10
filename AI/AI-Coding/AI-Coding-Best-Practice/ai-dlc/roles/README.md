# AI-DLC 角色总表(整列表)

两类扮演者:**编程 agent**(运行本 skill 的交互 agent,zcode/claude/codex…)
戴帽子执行,契约在各自 md;**jiuwenswarm**(网关每角色一次新鲜会话,事件帧
判定,网关代码零改动)。谁扮演、谁把关,一表看全。

## 编程 agent 侧(角色 md 契约,不派发)

| 角色 | md | 职责 | 产物 | 把关 |
|---|---|---|---|---|
| project-manager(PM) | [project-manager.md](project-manager.md) | 读仓分解:WBS+每子任务一个 handoff 包(四标记 brief);**不编码、不测试** | `openspec/changes/<id>/wbs.json` + `packages/<sid>.json` | `plan.py wbs`:schema/DAG/四标记/**净树证明** |
| coder | [coder.md](coder.md) | 按包**编码+测试一体**交付(实现与测试同交,决策 3a);按拓扑序执行子任务 | 源码 + 测试 | 执行门(真跑工具链)、validate 派发、review |

## jiuwenswarm 侧(每角色新鲜会话,经网关派发)

| 角色 | 职责 | 产物 | 把关 |
|---|---|---|---|
| proposal | 写提案工件 | `proposal.md` | openspec 模板 + validate 裁决 |
| specs | 写规格工件 | `specs/<域>/spec.md`(ADDED Requirements/Scenario) | `openspec validate --strict`(validator 派发) |
| design(D0-D3 管线) | 选模板、产出设计 | tokens.css/tokens.json/components.md/pages.md/assets.md + design-material/(含 pages/ 按页素材) + design/pages/<slug>.md | D3 机械六检 + design-pin(sha 钉住) |
| tasks | 写任务清单工件 | `tasks.md` | openspec 模板 |
| review-*(≤3 轴) | 对抗评审(security/operability/performance 轴) | findings + 追问 | 评审证据规则(无证据的结论不算) |
| validate(validator) | 规格裁决(每 change 一次) | `verdict-*.json`(HMAC 签名,含 validator_model) | 签名记录,报告≠验证 |
| archiver | close 时归档 | `archive-*.json`(HMAC) | close 双守卫(执行门/spec) |
| codegraph | 结构优先规划(可选) | codegraph 工件 + pin/digest | codegraph-query/pin |
| graph | 一次性工件图(角色集的唯一来源) | 签名 graph 记录 | `plan.py roles` 只读它 |

## 流程中的位置

```
[编程 agent·PM 帽] init(路由/tier 测量)→ 驱动派发,全程统筹
     → [jiuwenswarm] proposal → specs →(design)→ tasks
     → [PM 帽] 读仓分解 → wbs.json + 子包 → plan.py wbs 校验
     → [coder 帽] 按拓扑序:每个子包 编码+测试 → checkpoint
     → [jiuwenswarm] validate 派发(签名 verdict)→(review)
     → deliver(执行门真跑)→ MERGE_GATE(人类)→ close(归档)
```

**不变式**:无论谁扮演,三铁律不变——无自动合并、报告≠验证、机器事实
高于共识;PM 的"没编码"与 coder 的"没自裁"都由机器证明(wbs 净树检查、
validator 禁跑规则),不靠口头承诺。
