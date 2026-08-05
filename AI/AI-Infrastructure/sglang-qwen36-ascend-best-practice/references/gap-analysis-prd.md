# PRD: SGLang TP2/DP8 与 xlsx Exp2(TP16) 差距分析与优化部署

**版本**: v1.0
**日期**: 2026-08-05
**作者**: Claude Code
**状态**: 分析完成，待执行优化轮

---

## 1. 问题陈述

TP2/DP8 BF16+NEXTN sticky 实测 vs xlsx SGLang 最优数据（Exp2，TP16 单 engine）：

| 场景 | C 级 | TP2/DP8 sticky (本次) | xlsx Exp2 (TP16) | 差距 |
|---|---|---|---|---|
| Chat | C1 | 110.69 | 147.2 | **-25%** |
| Chat | C4 | 140.6 | 109.27 | +29% ✅ |
| Chat | C8 | 107.59 | 90.76 | +19% ✅ |
| Chat | C16 | 43.81 | 82.05 | **-47%** ❌ |
| Coding | C1 | 134.75 | 145.53 | -7% |
| Coding | C4 | 125.93 | 86.2 | +46% ✅ |
| Coding | C8 | 107.03 | 73.73 | +45% ✅ |
| Coding | C16 | 119.47 | 60.06 | +99% ✅ |
| Sum | C1 | 127.4 | 135.62 | -6% |
| Sum | C4 | 121.76 | 76.71 | +59% ✅ |
| Sum | C8 | 110.14 | 46.44 | +137% ✅ |
| Sum | C16 | 91.41 | 49.16 | +86% ✅ |

**结论先行**：差距集中在 **C1（低并发）和 Chat C16（高并发短上下文）**两点。中高并发（C4/C8）和长上下文场景 TP2/DP8 已全面超越 TP16。优化重点不是"整体追平"，而是**修掉 C1 和 Chat C16 两个塌陷点**。

---

## 2. 根因分析（已用实测数据证实）

### 2.1 C1 塌陷：单实例 TP2 算力 < TP16，且 sticky 把流量钉死在 1/8 实例

**证据**：
- TP16 单 engine：C1 prefill=492 tok/s/user，TTFT=269ms → 16 die 全为一个请求服务，prefill 极快。
- TP2/DP8 sticky：C1 prefill=322 tok/s/user，TTFT=**2729ms**（10× 慢）→ 一个请求只落到 1 个 TP2 实例（2 die），其余 7 个实例空闲。

**机理**：
- C1 = 1 个并发请求。sticky-user-sessions 按 `session_id % 8` 路由，C1 只有 1 个 session → 永远只打 1 个实例（2 die），**14 die 闲置**。
- TP16 时这 1 个请求用满 16 die 做 prefill（128 token 虽小，但 NEXTN draft model + MoE all-to-all 在 16 die 上并行更快）。
- 这是 **sticky 路由 + 低并发的结构性缺陷**：亲和性在低并发时 = 闲置，在高并发时 = 命中。鱼与熊掌。

**为什么 xlsx Exp2 C1 反而最高**：Exp2 是 TP16 单 engine、单 URL、`connection_reuse=pooled`、无 sticky、300 请求 sequential 采样（同一 prompt 重复 300 次）。C1 时 1 个请求独占 16 die，且 radix cache 虽 disable 但**同一 prompt 重复 → 实际 KV 复用**（sglang 即使 disable-radix-cache，同 batch 内相同 prefix 仍有内部复用路径），所以 C1 极快。

### 2.2 Chat C16 塌陷：sticky 把 16 并发钉到 8 实例 = 每实例仅 2 并发，但短上下文下 NEXTN 收益被请求间排队吃掉

**证据**：
- TP2/DP8 sticky Chat C16：per_user=43.81，TTFT=2111ms，req_lat=15897ms，**request_count 只有 30**（不是 300！）。
- TP16 Exp2 Chat C16：per_user=82.05（xlsx）/ 44（r300 实测），TTFT=1095ms，req_lat=7312ms，request_count=300。

**关键发现：request_count=30 是测试方法差异，不是 bug**。
- 本次 sticky 脚本用 `--request-count 300 --num-conversations 30`。aiperf 的 `num-conversations` 在 sticky 模式下**把 300 请求压成 30 个独立会话轮次**，每个会话 10 个 turn。C16 时 16 并发抢 30 个会话 → 实际只跑 30 个请求就结束（duration 35.7s）。
- TP16 Exp2 用 `--request-count 300` 无 num-conversations → 真跑 300 请求（duration 139.9s）。
- **per_user 是按并发数除的，不是按请求数**，所以两者口径一致，可比。但 C16 时 30 请求 / 16 并发 ≈ 2 波，**冷启动 + 排队效应**让 TTFT 飙到 2.1s。

**机理（C16 短上下文塌陷）**：
- Chat 是 128/256 短上下文。NEXTN 投机解码在短输出（256 token）下**启动开销占比高**（draft model warmup + 首 token 投机无收益）。
- sticky 把 16 并发分到 8 实例 = 每实例 2 并发。TP2 每实例 `--max-running-requests 64` 但实际只跑 2 → **batch 太小，MoE 专家负载不均，decode 效率低**。
- 对比 Coding C16=119.47（反而最高）：长输出 4096 token，NEXTN 投机解码收益充分释放（accept len 3.33 → 实际 decode 速度 ~3.3×），且 16 并发分 8 实例每实例 2 并发，长输出下 batch 稳定，排队不显著。

### 2.3 次要因素

| 因素 | Exp2 (TP16) | 本次 (TP2/DP8 sticky) | 影响 |
|---|---|---|---|
| chunked-prefill-size | 4096 | **2048** | 本次 prefill 切更碎，短上下文无差，长上下文略慢 |
| max-running-requests | 32 | 64 | 本次更高，但 sticky 下并发打不满 |
| HCCL_BUFFSIZE | 1 | 512 | TP2 跨 die 通信，512 更优；TP16 单进程无跨 die |
| SGLANG_ENABLE_OVERLAP_PLAN_STREAM | 0 | 1 | 本次更优（overlap plan） |
| radix cache | disable | **enable（默认）** | 本次开 radix，但 sticky+短上下文命中有限 |
| request_count | 300 | 300 但 num-conv=30→实测30 | 口径差异，per_user 可比 |
| 重复 prompt | sequential 同一 prompt ×300 | 30 会话 ×10 turn | Exp2 同 prompt 重复更多，KV 复用更高 |

---

## 3. 优化部署方案

### 3.1 核心思路：双模式部署，按并发场景选拓扑

**不是"二选一"，而是"两个配置各擅胜场"**：
- **低并发（C1）/ 短上下文高并发（Chat C16）→ TP16 单 engine**：独占 16 die，无闲置。
- **中高并发（C4+）/ 长上下文 → TP2/DP8 sticky**：分散并发 + NEXTN 收益。

但物理上 16 die 同一时刻只能跑一种拓扑。**优化方向 = 让 TP2/DP8 在塌陷点也能追上**，而非回退 TP16。

### 3.2 优化项（按预期收益排序）

#### OPT-1：C1 改用 round-robin 而非 sticky（预期 +30-40%，追平 147）

C1 只有 1 并发，sticky 把它钉死在 1/8 实例。**C1 单独跑一轮用 aiperf 多 URL round-robin**（无 sticky），让 1 个请求轮询 8 实例——但 round-robin 在 C1 也只打 1 实例（1 请求 1 URL）。

**真正解法**：C1 用 **TP16 单 engine 临时实例**（端口 6696），或接受 C1 = TP16 独占。C1 是单用户场景，本来就该用最大并行度。

→ **方案**：部署脚本支持 `--mode tp16`（单实例 16 die，端口 6696）和 `--mode tp2dp8`（8 实例）两种，C1 走 tp16，C4+ 走 tp2dp8。

#### OPT-2：Chat C16 提高 num-conversations 到 ≥160（预期 +40-60%，追平 82）

当前 `--num-conversations 30` 让 C16 只跑 30 请求就结束，冷启动 + 排队主导。
**改为 `--num-conversations 160`**（C16 时 16 并发 × 10 波 = 160 请求，每实例 20 请求充分预热），或直接 `--request-count 300 --num-conversations 300`（退化为非 sticky 但保留 session header）。

注意：num-conversations 必须保证每实例分到足够会话。sticky 下 `sid % 8`，需 `num-conversations ≥ concurrency × 8` 才能让 8 实例都满载。C16 → 至少 128，建议 160-300。

#### OPT-3：chunked-prefill-size 回调到 4096（预期长上下文 +5-10%）

本次用 2048（抄报告 Exp2 最优，但那是 vllm）。sglang + Ascend 上 4096 让 prefill 更连续，减少 chunk 间同步。Coding/Sum 长上下文受益。

#### OPT-4：NEXTN 参数调优（预期短上下文 +10-15%）

当前 `--speculative-num-steps 3 --speculative-eagle-topk 1 --speculative-num-draft-tokens 4`。
- 短输出（256）下 num-steps=3 的 draft 开销占比高。可试 `--speculative-num-steps 2`（减 draft 负担，accept rate 可能升）。
- 或 `--speculative-eagle-topk 2`（多候选，accept len 可能升）。
- 需 A/B，单变量。

#### OPT-5：radix cache 对短上下文 Chat 的影响验证

Chat 128/256 短上下文，radix cache 命中取决于 prompt 重复。sticky + num-conv=30 时 30 个会话各有不同 prompt → 命中低。**若 num-conv 提到 160 且 prompt 模板相同（仅 session id 不同）→ radix 命中升**。验证开/关 radix 在 Chat C16 的差。

#### OPT-6（可选）：TP4/DP4 折中拓扑

TP2 每实例只 2 die，单实例算力弱。**TP4/DP4**（4 实例 × 4 die）单实例算力翻倍，C1 时 4 die 比 2 die 快，C16 时 16 并发分 4 实例每实例 4 并发（比每实例 2 并发 batch 更大）。但 TP4 跨 2 NPU（davinci0-3 跨 NPU0-1），HCCL 通信开销升。**需 A/B 验证 TP4/DP4 vs TP2/DP8**。

---

## 4. 执行计划

### Phase 1：修测试方法（零部署改动，预期 Chat C16 立即追平）

**改 96 测试脚本** `/home/qwen3.6-test/run-sglang-bf16-nextn-tp2dp8-sticky-v2.sh`：
- Chat: `--num-conversations 160`（原 30）
- Sum: `--num-conversations 80`（原 20，C16 时 16 并发 ×5 波）
- Coding: `--num-conversations 80`（原 20）
- 其余不变，重跑三场景。

**验收**：Chat C16 per_user 从 43.81 → 目标 ≥70。

### Phase 2：部署优化（166 重启）

改 `/root/launch-sglang-bf16-nextn-tp2dp8.sh`：
- `--chunked-prefill-size 4096`（原 2048）
- 其余不变，重启 8 实例，重跑 Phase 1 脚本。

**验收**：Coding/Sum 长上下文 per_user 再 +5-10%。

### Phase 3：NEXTN A/B

单变量对比（每轮只改 1 个）：
- A: `--speculative-num-steps 2`（原 3）
- B: `--speculative-eagle-topk 2`（原 1）
- 用 Chat + Coding 两场景 C1/C16 快速验证（各 5 分钟）。

**验收**：选出 Chat 短上下文最优 NEXTN 参数。

### Phase 4：C1 专项（TP16 临时实例）

部署 TP16 单实例（端口 6696，复用 `/root/launch-sglang-qwen.sh` 改端口），仅跑 C1 三场景。
- 或：接受 C1 由 TP16 独占，xlsx 中 C1 列标注"TP16"。

**验收**：C1 Chat ≥140，Coding ≥140，Sum ≥130。

### Phase 5（可选）：TP4/DP4 A/B

部署 TP4/DP4（4 实例，davinci 0-3/4-7/8-11/12-15），跑 Chat+Sum C1/C16，对比 TP2/DP8。

---

## 5. 部署脚本变更清单

### 5.1 166: `/root/launch-sglang-bf16-nextn-tp2dp8.sh`（Phase 2）

```diff
- --chunked-prefill-size 2048
+ --chunked-prefill-size 4096
```

### 5.2 166: 新增 `/root/launch-sglang-bf16-tp16.sh`（Phase 4）

基于 `/root/launch-sglang-qwen.sh`，改：
- `--port 6696`
- 保留 `--speculative-algorithm NEXTN`（BF16 兼容）
- `--chunked-prefill-size 4096`
- `--max-running-requests 32`

### 5.3 96: `/home/qwen3.6-test/run-sglang-bf16-nextn-tp2dp8-sticky-v2.sh`（Phase 1）

```diff
- --request-count 300 --num-conversations 30   # Chat
+ --request-count 300 --num-conversations 160

- --request-count 200 --num-conversations 20   # Sum
+ --request-count 200 --num-conversations 80

- --request-count 200 --num-conversations 20   # Coding
+ --request-count 200 --num-conversations 80
```

---

## 6. 验收标准

| Phase | 指标 | 目标 |
|---|---|---|
| 1 | Chat C16 per_user | 43.81 → ≥70 |
| 1 | Chat C1 per_user | 110.69 → ≥120（num-conv 提升附带） |
| 2 | Coding C16 per_user | 119.47 → ≥125 |
| 2 | Sum C8 per_user | 110.14 → ≥115 |
| 3 | Chat C1 最优 NEXTN 参数 | 确定 steps/topk |
| 4 | C1 Chat (TP16) | ≥140 |
| 4 | C1 Coding (TP16) | ≥140 |
| 5 | TP4/DP4 vs TP2/DP8 结论 | 出 A/B 报告 |

**最终目标**：三场景 C1/C4/C8/C16 全部 ≥ xlsx Exp2 对应值，输出新 xlsx。

---

## 7. 风险

| 风险 | 缓解 |
|---|---|
| num-conversations 提高后 90% cache hit 下降 | sticky 仍保证同 session 落同实例；prompt 模板相同则 radix 仍命中 |
| TP16 临时实例与 TP2/DP8 抢 die | Phase 4 单独跑，先 clean TP2/DP8 再起 TP16 |
| NEXTN 参数调优可能反向 | 单变量 A/B，每轮只改 1 个，保留回退 |
| TP4/DP4 跨 NPU HCCL 开销 | Phase 5 可选，先看 TP2/DP8 优化后是否够 |

---

## 8. 时间预估

| Phase | 预估 |
|---|---|
| 1 测试方法（零部署） | 20 分钟（重跑三场景） |
| 2 部署优化（重启+重跑） | 30 分钟 |
| 3 NEXTN A/B | 30 分钟 |
| 4 C1 TP16 | 20 分钟 |
| 5 TP4/DP4（可选） | 40 分钟 |
| 汇总出新 xlsx | 10 分钟 |
| **合计** | **~2-2.5 小时** |
