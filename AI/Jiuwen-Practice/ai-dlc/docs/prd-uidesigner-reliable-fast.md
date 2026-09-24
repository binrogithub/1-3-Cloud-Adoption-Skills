# PRD · UIDesigner 可靠交付与提速（uidesigner-reliable-fast）

> 三轮真实运行，ui-designer **每次都被调用了**，**每次都拿不到记录**。
> 最近一轮 53.7 分钟，其中 36.8 分钟花在一轮把整站写进推理块——96% 是复读。
> 本轮：让它跑得成，让门证明它跑了，让它快下来。

- 目标仓库：`<repo-path>`
- 上游：`prd-uidesigner-opendesign.md`（五条事实）· `prd-design-required.md`（门）· `prd-deliver-measures-work.md`（测量）
- 测量日期：2026-09-01 · <host-ip>
- 回滚锚点：开工前打 `v0.19.x-pre-reliablefast`（**先打 tag 再动手**）

---

## 01 问题

### 一 · 三次调用，零记录

| 轮 | 会话 | 时长 | 调用 ui-designer | 五条事实 | 签名记录 |
|---|---|---|---|---|---|
| country-a | `design-country-a-site-1` | 855s | ✅ `skill_tool{ui-designer}` | 修判据后**全过** | ❌ |
| country-d | `design-task-…f93794-1` | 1,337s | ✅ | **全过**（我用帧复验） | ❌ |
| client-x | `design-2026-09-01-client-x-ai-launch-3` | **3,224s** | ✅，读上游 19 个路径 | 4/5，卡 `writes_outside` | ❌ |

**机制是通的**——技能装了、注册了、`design_skill_state()` 返回 `ok: true`，
三轮都真的 `skill_tool {"skill_name": "ui-designer"}` 调起来了。
**但成功率是 0/3。** 三次失败的原因各不相同：

- **country-a**：判据本身有缺陷（幻影写入 / 自检日志 / 根绝对引用）——已由 `c58e9f2` 修好
- **country-d**：会话跑满 22 分钟、五条全过，**结果没回写**（`design_auto.rc = null`）
- **client-x**：判据**判得对**——角色真的把 `site/features.html` 写到了 `/tmp$client-x-ai-launch/`

client-x 那次的 `$` 不是解析幻影，那个目录**今天还在盘上**：

```
/tmp$client-x-ai-launch/site/features.html   9,679 B  20:49
/tmp/client-x-ai-launch/site/features.html  9,516 B  20:53   ← 正确路径，4 分钟后
```

角色自己发现了，跑过 `rm -rf /tmp\$client-x-ai-launch 2>/dev/null; echo "cleaned"`
——**转义写错，`\$` 在双引号里仍是字面 `$`**，垃圾目录留到现在。
同一轮的帧里满是 `$` 污染的痕迹：

```
edit_file  old_string: "  --ease: cubic-bezier(0.$22, 1, 0.36, 1);"
edit_file  old_string: "  --font$-body: \"Inter\", system-ui, sans-serif;"
grep       pattern: "[\$#!]{2,}"            ← 角色在全站搜自己注入的 $
grep       pattern: "[\$]|infraestr\"|0\$ 0"
```

CSS 内容里的 `$` 它自己修掉了，路径里的那个让它写到了产品面之外。

### 二 · 53.7 分钟，其中 36.8 分钟是一轮复读

```
总时长      3,223.8s
工具        54 次，合计 1.01s   ← 0.03%
模型侧      3,222.8s            ← 100.0%
吞吐        125,869 out tokens / 3,222.8s ≈ 39.1 tok/s
```

**单轮最慢 2,206 秒 = 36.8 分钟 = 全程的 68%。** 那一轮：

```
reasoning_content  302,814 字符   ← 全会话推理量（331,456）的 91%
5,426 行  →  去重后 219 行  →  重复率 96.0%
最高频行：``` 244×  |  } 119×  |  </svg> 62×
          src = attr_dict["src"] 61×
          if not src.startswith(("http://","https://","//")) 61×
该轮结尾："Let me now write everything. Let me start with the CSS, which is"
```

**它把整站（含测试文件源码）在推理块里翻来覆去写了 61 遍，然后才开始真正写。**
`<div` 出现 0 次——推理里没有页面结构，全是复读。

country-a是同一病理的小号：854s 里单轮最慢 322s（38%），该轮 reasoning 47,245 字符。
**规模随交付面增长，病理相同。**

### 三 · 已有的防重复护栏看不见它

```yaml
execution_guard.llm_retry_rail:
  repeat_window_chars: 1024      ← 窗口
  repeat_min_count: 6
  repeat_min_pattern_chars: 2
```

窗口 **1024 字符**，失控块 **302,814 字符**——窗口是它的 **0.3%**。
而且重复的是**散布全块的行**（61 次 `src = attr_dict["src"]` 相隔很远），
不是相邻复读。**这道护栏结构上看不见这种病理。**

### 四 · 顺带：`design_auto` 三次都是半截

```json
{"attempted_at": "2026-09-01T12:00:49Z", "change": "2026-09-01-client-x-ai-launch",
 "trigger": "deliver", "rc": null, "outcome": null,
 "session": null, "elapsed_seconds": null}
```

N4 让它可重试（所以到了 `-3`），但**三次都因同一原因失败——重试解不了**。

---

## 02 目标与非目标

### 目标

| ID | 目标 |
|---|---|
| **Y-A** | **可靠**：web 面上 design 轮产出签名记录的成功率**可测且显著大于 0**（今天 0/3） |
| **Y-B** | **门证明它跑了**：一条端到端回归门，真实派发、真实产出签名记录——不是夹具重言式 |
| **Y-C** | **快**：单轮推理失控被截断；交付面分片并发。目标是**同等交付面下墙钟时间减半** |
| **Y-D** | **不放宽五条事实**：client-x 那次判得对，不允许为了提高成功率去放行越界写 |
| **Y-E** | **失败要能自愈一次**：可自动修复的失败（越界写残留）修完重判，不可自愈的（真实缺陷）如实失败 |

### 非目标

- **不改五条事实本身**。本轮改的是「怎么跑」与「跑完怎么记账」。
- 不做 PPTX/PDF/MP4 导出（仍是上游 P4）。
- 不改设计门的判定（`prd-design-required.md` 的 M6 是对的）。
- 不改合并门的人工判官地位。

### 一处已推翻的非目标

本 PRD 初稿写过「**不关思考**」，理由是「关思考能提速」此前已实测并撤回。
**Robin 的决定（2026-09-02）推翻了它**：关掉 openjiuwen 连 MaaS 的 thinking。

这个推翻是有据的——初稿撤回的是「关思考能普遍提速」这个泛化结论，
而本轮面对的是一个**具体病理**：单轮 302,814 字符、96% 重复的推理块。
关掉之后已实测（§04 E8），不是推断。

---

## 03 不变式

| ID | 不变式 |
|---|---|
| **Z1** | **五条事实一条不减**。任何加速与自愈都不得降低判据强度；D8 门（没读上游就拿不到记录）保持绿。 |
| **Z2** | **自愈只清理，不改判**：越界写的自愈是**删除残留后重新测量**，不是把越界写从判据里豁免掉。清理了什么必须原样记账。 |
| **Z3** | **回写不可丢**：会话结束必有终态。`rc` 为 null 只能是「进程被杀」，且下次必须可重试（N4 已有），**同时必须能从会话帧补写**（本轮新增）。 |
| **Z4** | **截断是有据的**：推理截断必须记录截断点与被截掉的量，不静默。 |
| **Z5** | **分片不改风格**：首片确定模板与设计系统的 sha，后续片**必须复用同一个**，否则十个页面长成十种风格。 |
| **Z6** | **回归门必须真实派发**：Y-B 的门不接受 stub client——那只能证明代码路径通，不能证明 ui-designer 跑得成。 |
| **Z7** | **加速要有实测基线**：不接受「感觉快了」。基线是 client-x 的 3,223.8s / 5 个文件与country-d的 1,337s / 11 个文件。 |

---

## 04 实测约束

**E1 · 工具耗时可忽略。** 三轮都是 0.03%–0.2%。**OpenDesign 是文件读取，不是服务调用**——
读 `SKILL.md` 单次 0.02s。任何针对 IO 的优化都是白费。

**E2 · 瓶颈是单条 token 流，39.1 tok/s。** 加速只能靠**拆成多条并行的流**，
或**减少要生成的 token**。

**E3 · 并发是真的，实测 1.65×。** client-x 的 review 轮 `concurrency: 2`：

```
11:35:19 → 11:37:42  143.3s  review-security     ┐ 同时启动
11:35:19 → 11:38:18  179.5s  review-operability  ┘
11:37:42 → 11:39:53  130.5s  review-performance  ← security 一结束就补位
串行 453.3s / 实际 274s = 1.65×
```

第三个的启动时刻**正好等于**第一个的结束时刻——池子在工作。

**E4 · `max_workers: 2` 不是会话并发上限。** 它属于 `enabled: false` 的技能发现/分类子系统
（同块有 `branching_factor` / `classification_batch_limit` / `discovery_seed`），
**与 design 分片无关**。`gateway.agent_client.concurrency: 1` 需要单独确认。

**E5 · 上下文会先撞墙。** client-x 单轮 input 从 22,386 涨到 186,257
（200K 窗口的 93%）。**分片顺带解掉这个**，不分片则页面稍多必然超窗。

**E6 · `cmd_phase` 的并发池是现成的。** 跑出 E3 那个结果的就是它，
design 分片应复用，不要新写调度器。

**E8 · thinking 已关闭并实测（2026-09-02，本轮已落地）。**

端点直测（`api-ap-southeast-1.modelarts-maas.com`，`glm-5.2`，同一提问）：

| | `reasoning_content` | `reasoning_tokens` | `completion_tokens` |
|---|---|---|---|
| 默认 | 811 字符 | 471 | 511 |
| `thinking: {type: disabled}` | **0** | **0** | **55** |

**必须走 `extra_body`，不能裸写。** openjiuwen 把 `model_config_obj` 的每个键
变成 OpenAI SDK `create()` 的**具名参数**
（`common/reasoning_injector.py` → `_build_model_request_kwargs`），
所以裸 `thinking:` 会在第一次派发就炸：

```
openAI API async stream error:
TypeError: AsyncCompletions.create() got an unexpected keyword argument 'thinking'
```

这是活体实测出来的，不是推断——第一版配置就是这么失败的。
`extra_body` 才落到请求体顶层，而华为云 MaaS 文档要求 `thinking` 与
`model` / `messages` **同级**。落地形态：

```yaml
models.defaults[0].model_config_obj:
  temperature: 0.95
  extra_body:
    thinking:
      type: disabled
```

网关侧活体验证：会话 `cli-20260901-165822-e00bf83c`，4 帧，
**`reasoning_content` 0 字符**，`output_tokens` 40，8.7 秒，回答完整。

**一条到期条件**：GLM-5.3 起不再支持关闭思考，传 `disabled` 会直接报错。
`MODEL_NAME` 一旦移出 5.2，这条配置必须跟着动——脚本的 `--check` 会先判出来。

**E7 · 帧齐备，回归可离线。** 三轮的 `history.jsonl` 都在
（country-a 319 KB / country-d 472 KB / client-x 738 KB）。
**判据类回归不需要重跑会话**；只有 Y-B 的端到端门需要真实派发。

---

## 05 方案

三条线，可并行开发，但**上门的次序有依赖**。

### A 线 · 可靠（Y-A / Y-E）

```
A1 越界写自愈    产物面外的残留 → 删除 → 重新测量 → 重判（Z2）
                 只自愈「路径明显是事故」的形态（产品面同名文件写到了仓库外），
                 记进 record.self_healed，其余照旧失败
A2 终态补写      会话结束时 rc 仍为 null → 从会话帧离线补跑事实提取并回写
                 （country-d那条本该签发的记录就是这样丢的）
A3 路径护栏      派发前后校验：产品面写入必须落在 --repo 之内；
                 发现仓库外的同名产物立即报告，不等到五条事实那一步
```

### B 线 · 门证明它跑了（Y-B）

```
B1 端到端回归门  tests/collapse/ud_live_design.sh —— 一个最小真实站点（1 页），
                 真实派发 design，断言：ui-designer 被 skill_tool 调用、
                 签名记录产出、五条事实全过。默认跳过（需 --live），
                 CI 与发布前必跑。Z6：不接受 stub。
B2 调用断言      帧里必须出现 skill_tool{ui-designer}；未出现即失败并指出
                 「角色没有走指路牌」——这与 D8 互补：D8 管「没读上游」，
                 B2 管「没用技能」
B3 成功率记账    每轮 design 的结果进 /var/lib/aidlc/design-stats.jsonl
                 （change / elapsed / outcome / failed_facts）。Y-A 的「可测」由它兑现
```

### C 线 · 加速（Y-C）

```
C0 关闭 thinking  已落地（E8）：models.defaults[0].model_config_obj.extra_body
                 .thinking.type = disabled，由 scripts/configure-gateway-model.sh
                 管理（备份 → 编辑 → 结构化读回断言 → 失败即还原）。
                 端点直测 reasoning_tokens 471 → 0，completion 511 → 55
C1 推理失控截断  按「窗口内去重率」而非固定窗口检测：
                 滚动统计已生成推理的行级重复率，超阈值（默认 80%，
                 且累计 > 50,000 字符）即截断该轮并记账（Z4）
                 —— 现有 repeat_window_chars=1024 结构上看不见这种病理
C2 交付面分片    按测出的 web/deck 文件分片派发，复用 cmd_phase 的并发池（E6）
                 首片定模板与设计系统的 sha，后续片复用（Z5）
                 每片一条 design-<seq>.json；deliver 要求每个面文件被某条记录覆盖
C3 指路牌收窄    ui-designer SKILL.md 加一句：一次处理一个页面，
                 不要在动手前把整站在脑子里写一遍
                 —— client-x 那轮 36.8 分钟正是这么花掉的
```

### 加速的预期与验证

| | 今天（关 thinking 前） | C0 之后 | C0+C1 之后 | C0+C1+C2（4 片） |
|---|---|---|---|---|
| client-x 形状（5 文件） | 3,224s | **待测** | 待测 | 待测 |
| 依据 | 实测 | C0 已落地，**尚未在设计轮上量过** | 外推 | 叠加实测 1.65×（N=2）向 N=4 外推 |

**这张表现在只有第一列是实测。** C0 虽然已落地，但只在一个 8.7 秒的最小会话上验过
（`reasoning_content` 归零），**没有在一次真实 design 轮上量过端到端墙钟**。
在 S5 拿 client-x 形状重跑之前，任何加速倍数都不得被引用为结论（Z7）。

初稿曾在这里写过「C1 之后约 1,000–1,200s、四片后约 400–600s」——
那是纯外推，已删除。**先量，再写。**

---

## 06 新增

| ID | 内容 |
|---|---|
| **N1** | **越界写自愈（A1）**：产品面文件出现在 `--repo` 之外且路径形态是事故（与面内文件同名/同相对路径）→ 删除残留、重新测量、重判；`record.self_healed` 逐条记账（Z2）。**不豁免、不放宽。** |
| **N2** | **终态补写（A2）**：`design_auto.rc` 为 null 且会话帧存在 → 离线跑事实提取并回写记录；补写的记录标 `recovered_from_frames: true`。 |
| **N3** | **路径护栏（A3）**：派发后立即扫描 `--repo` 之外与面内同名的产物，早于五条事实报告。 |
| **N4** | **`tests/collapse/ud_live_design.sh`（B1）**：真实派发的端到端门，`--live` 开关，默认跳过并打印跳过原因。 |
| **N5** | **调用断言（B2）**：`skill_tool{ui-designer}` 未出现在帧里 → 失败，理由「角色没有走指路牌」。 |
| **N6** | **成功率记账（B3）**：`/var/lib/aidlc/design-stats.jsonl`，每轮一条。 |
| **N7** | **推理失控截断（C1）**：行级去重率 + 累计字符双阈值；截断记 `reasoning_truncated: {at_chars, dup_ratio}`（Z4）。 |
| **N8** | **交付面分片（C2）**：`plan.py design --shard N` / 自动按面文件数分片；复用 `cmd_phase` 并发池；首片定 sha，后续复用（Z5）；deliver 要求全覆盖。 |
| **N9** | **指路牌收窄（C3）**：`supervisor/skills/workspace/ui-designer/SKILL.md` 加「一次一页」的工作方式；**同步到运行时副本**（走 `prd-install-targets.md` 的一致性路径）。 |
| **N10** | **清理 client-x 残留**：`rm -rf '/tmp$client-x-ai-launch'`（角色没删掉），并把它作为 N3 的第一个真实用例。 |
| **N11** | **`scripts/configure-gateway-model.sh`（已落地）**：网关模型旋钮的唯一入口。`--disable-thinking` / `--enable-thinking` / `--check`；幂等；备份 → 按**结构**定位 `model_config_obj` 块（不按行号）→ 清掉旧的 `extra_body`/裸 `thinking` 再写 → **结构化读回断言**（yaml 解析，不是 grep）→ 读回失败即还原备份。专门判出**裸 `thinking` 键**并拒绝（E8 的失败形态）。有活跃会话时**拒绝重启**并给出手动命令，除非 `AI_DLC_FORCE_RESTART=1`。 |

---

## 07 反向门

| ID | 尝试 | 期望 | 今天 |
|---|---|---|---|
| **Y1** | **端到端（Z6）**：最小站点真实派发 design | 签名记录产出，五条全过 | **RED** — 今天 0/3 |
| **Y2** | 帧里没有 `skill_tool{ui-designer}` | 失败，指出「没走指路牌」 | **RED** — 今天不检查 |
| **Y3** | **D8 回归（Z1）**：帧里零上游读取、角色声称已美化 | 仍然拿不到记录 | **GREEN 回归门** |
| **Y4** | 产品面文件写到仓库外（client-x 的形状） | 自愈：删残留、重测、重判；`self_healed` 有记账 | **RED** |
| **Y5** | **自愈不得越界（Z2）**：把**真实产物**写到仓库外（不是事故形态） | **仍然失败**，不自愈 | **RED** — 防 N1 变成豁免口子 |
| **Y6** | `design_auto.rc = null` 且帧存在 | 离线补写记录，标 `recovered_from_frames` | **RED** — country-d那条今天永久丢失 |
| **Y7** | 构造 96% 重复的推理流 | 截断并记 `reasoning_truncated` | **RED** — `repeat_window_chars: 1024` 看不见 |
| **Y8** | **截断不得误伤（Z4）**：正常的长推理（低重复率） | 不截断 | **RED** |
| **Y9** | 4 片分片派发同一 change | 各片记录的 `template.sha256` 相同（Z5） | **RED** |
| **Y10** | 分片后 deliver | 每个 web 面文件都被某条记录覆盖，缺一即 `design_required` | **RED** |
| **Y11** | **加速实测（Z7）**：client-x 形状重跑 | 墙钟 ≤ 1,600s（基线 3,224s 的一半） | **RED** — 这是 Y-C 的唯一硬指标 |
| **Y12** | **并发真实性**：4 片的启动时刻 | 呈现池行为（补位），不是串行 | 可测（E3 已证明池在工作） |
| **Y13** | 三套现有门禁 | 真实退出码全绿 | **GREEN 回归门** |
| **Y14** | 配置里放一个**裸 `thinking`** 键，跑 `--check` | 拒绝并指出必须放 `extra_body` 下 | **GREEN**（已实测 rc=1） |
| **Y15** | `--disable` / `--enable` 往返 3 次 | `model_config_obj` 恒为 `{temperature, extra_body}`，注释恒 6 行，**不堆积** | **GREEN**（已实测） |
| **Y16** | 网关派发一次，读帧 | `reasoning_content` 为 0 字符 | **GREEN**（已实测：4 帧 / 0 字符 / 8.7s） |
| **Y17** | **到期条件**：`MODEL_NAME` 移出 glm-5.2 后跑 `--check` | 提示该配置需复核（5.3 起不支持 disabled） | **RED** — 今天脚本不看模型名 |

**Y1 与 Y3 缺一不可**：Y1 证明它跑得成，Y3 证明没有为了跑成而放宽判据。
**Y4 与 Y5 缺一不可**：Y4 解开事故，Y5 防止自愈变成越界写的免死金牌。
**Y7 与 Y8 缺一不可**：Y7 截住失控，Y8 防止把正常长推理也砍了。
**Y11 是 Y-C 的唯一硬指标**——没有它，「加速」只是叙述。

---

## 08 分期（次序有依赖）

| 期 | 内容 | 门 | 依赖 |
|---|---|---|---|
| **S0 · 探针** | 已完成：三轮成功率 0/3；53.7 分钟拆解（2,206s 单轮 / 96% 重复）；护栏窗口 0.3%；并发 1.65× 实测 | 四个事实进记录 | — |
| **S0b · thinking** | **已落地**：N11 脚本 + 配置改 `extra_body.thinking.type=disabled` + 网关重启 + 活体验证 | **Y14 Y15 Y16** 已绿；Y17 待补 | — |
| **S1 · 可靠** | N1 + N2 + N3 + N10 | **Y4** **Y5** Y6 | — |
| **S2 · 门** | N4 + N5 + N6 | **Y1** **Y2** Y3 | S1 |
| **S3 · 截断** | N7 + N9 | **Y7** Y8 | — |
| **S4 · 分片** | N8 | Y9 Y10 **Y12** | S3 |
| **S5 · 实测** | 不写代码：client-x 形状重跑，量真实加速比 | **Y11** Y13 | S4 |

**S2 必须在 S1 之后**——端到端门在一个还会因残留失败的系统上会一直红，
分不清是门的问题还是系统的问题。

**S1 落地当天就能验证**：client-x 的残留 `/tmp$client-x-ai-launch` 还在盘上，
其余四条事实都过——清掉它重派一次，**很可能一次成功**，
那将是 0/3 之后的第一条记录。

**S5 不是走过场**：Y11 是「加速」这件事有没有发生的唯一证据。
外推表（§05）在 S5 之前**不得被引用为结论**。

---

## 09 风险与残余

| ID | 风险 | 消化方式 |
|---|---|---|
| **R1** | **N1 自愈变成越界写的免死金牌** | Z2 + Y5：只自愈「与面内文件同名、路径形态是事故」的残留，且逐条记账。**残余**：一个恰好同名的真实越界写会被自愈——由 Y5 的反向用例守住边界。 |
| **R2** | **N7 截断误伤正常长推理** | 双阈值（去重率 + 累计字符），Y8 守住。**残余**：一个合法的高重复推理（比如逐行核对大表）会被截。截断记账可见，人可判断。 |
| **R3** | **分片让十个页面长成十种风格** | Z5：首片定 sha，后续复用，Y9 断言。**残余**：同一模板下不同片的具体表达仍会有差异——这是分片的固有代价。 |
| **R4** | **加速外推站不住** | Z7 + Y11：外推表明确标注为预期，S5 前不得引用。**1.65× 是 N=2 的实测，N=4 是外推。** |
| **R8** | **关掉 thinking 会不会降低设计质量** | **未知，本轮不声称**。E8 只证明了推理 token 归零与端点接受，**没有证明产出一样好**。判据侧不变（五条事实照旧），所以「变差」会在 Y1 的成功率上显形。**残余：**「好看程度」本来就不在判据里，这条只能靠人看。**S5 实测时应同时留意产出质量，不要只看墙钟。** |
| **R9** | **GLM-5.3 起不支持关闭思考** | 传 `disabled` 会直接报错，不是静默忽略。Y17 要求 `--check` 看模型名后再判——**今天还没做**，所以升级模型时这条会以派发失败的形式暴露，而不是提前拦住。 |
| **R5** | **`$` 注入是模型侧问题，改不到** | 本轮只做防御（N3 路径护栏 + N1 自愈），**不声称修好了 `$` 注入**。它出现在 CSS 内容、路径、和角色自己的清理命令转义里——值得单独观察，不在本轮范围。 |
| **R6** | **N9 改 SKILL.md 未同步到运行时** | 走 `prd-install-targets.md` 的一致性路径，落地后跑 `--doctor` 的 K5。**这是已经踩过一次的坑。** |
| **R7** | **`gateway.agent_client.concurrency: 1`** 可能是分片的隐藏上限 | S4 前先确认它的作用域（E4 已排除 `max_workers: 2`）。若它确实限流，加速比会退化到 1×——**必须在 S4 开工前量准，不能事后解释**。 |

---

## 10 回滚

1. `git reset --hard v0.19.x-pre-reliablefast`
2. `supervisor/skills/workspace/ui-designer/SKILL.md` 回滚后**必须重新同步到运行时副本**
3. `/var/lib/aidlc/records/` 与 `design-stats.jsonl` 保留不删（本轮证据）
4. `/opt/open-design`、gateway unit、openjiuwen 配置全程未动
5. N10 删掉的 `/tmp$client-x-ai-launch` 不恢复——它本身就是事故残留

---

*`docs/prd-uidesigner-reliable-fast.md` · 测量日期 2026-09-01 · <host-ip>*
