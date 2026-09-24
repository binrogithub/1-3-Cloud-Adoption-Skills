# CSS 稳定性 50 场景任务 Spec

依据：[CSS 运维效率、稳定性与业务保护 PRD](prd-css-operations-efficiency-stability-20260921.md)。

执行规则：每次只执行一个场景；若实际结果与预期不符，暂停后续场景，登记问题、修复、执行相关回归，再重跑当前场景。`MOCK` 和 `INJECTED` 只验证控制逻辑，不能计入真实业务通过。`REAL_CONTROL_PLANE` 证明云端控制面，`REAL_BUSINESS` 才能证明业务影响。

| ID | 场景 | 层级 | 预期断言 |
|---|---|---|---|
| CSS-S01 | CES 点带原始时间和单位 | REAL_CONTROL_PLANE | 样本保存 provider 时间、单位，年龄按原始点计算 |
| CSS-S02 | CES 返回旧点 | INJECTED | 质量为 stale，禁止自动缩容 |
| CSS-S03 | CES 空序列 | INJECTED | 保留 empty 原因，不转为 0 |
| CSS-S04 | CES 单位未知 | INJECTED | `METRIC_UNIT_UNKNOWN`，不提交变更 |
| CSS-S05 | CES 403/429 | INJECTED | 数据源告警，既有压力告警不 resolve |
| CSS-S06 | 采集时间窗口缺口 | INJECTED | coverage 不足，状态 UNKNOWN/hold |
| CSS-S07 | CSS 字段缺 AZ | REAL_CONTROL_PLANE | AZ UNKNOWN，严格缩容阻断 |
| CSS-S08 | 控制面 200、引擎未验证 | REAL_BUSINESS | 只能 CAPACITY_READY/UNVERIFIED |
| CSS-S09 | 指标未来或时钟偏差 | INJECTED | 记录质量异常并阻断决策 |
| CSS-S10 | 规范资源身份与 profile 别名 | INJECTED | 同一集群共享快照和动作互斥 |
| CSS-S11 | 1 个采样点 CPU 突发 | INJECTED | 不触发持续扩容 |
| CSS-S12 | 5 分钟 3 个有效点持续压力 | INJECTED | 生成一次 scale_out 计划 |
| CSS-S13 | 压力低于阈值 | INJECTED | HOLD，无写入 |
| CSS-S14 | CPU 高但搜索拒绝正常、存在热点证据 | REAL_BUSINESS | 调查热点，不盲目扩容 |
| CSS-S15 | 磁盘增长预测触达提前量 | INJECTED | 给出可解释 planning hint |
| CSS-S16 | 达到 max_data_nodes | INJECTED | `MAX_NODE_BOUND`，不重复提交 |
| CSS-S17 | 业务压力达到 max 且无替代方案 | REAL_BUSINESS | 告警并升级，不能越过上限 |
| CSS-S18 | 扩容窗口中发布事件 | REAL_BUSINESS | E06 关联，动作互斥 |
| CSS-S19 | 扩容期间批量写入 | REAL_BUSINESS | 业务 SLO 独立记录 |
| CSS-S20 | 预测输入缺失 | INJECTED | UNKNOWN，不声称 P95 |
| CSS-S21 | 缩容前历史不足 | INJECTED | `LOW_LOAD_WINDOW_INSUFFICIENT` |
| CSS-S22 | 缩容前快照为 false | INJECTED | `SNAPSHOT_REQUIRED` |
| CSS-S23 | 缩容前快照缺失 | INJECTED | 严格模式阻断 |
| CSS-S24 | 缩后磁盘余量不足 | INJECTED | 阻断缩容，报告目标容量 |
| CSS-S25 | AZ 分布不足 | REAL_CONTROL_PLANE | 阻断缩容，不调用写 API |
| CSS-S26 | 副本不能满足 | REAL_BUSINESS | E09 退化，冻结新动作 |
| CSS-S27 | 2→1 provider 约束 | REAL_CONTROL_PLANE | `PROVIDER_SCALE_IN_CONSTRAINT` |
| CSS-S28 | 3→2 合法缩容 | REAL_CONTROL_PLANE | 通过前置检查并等待对账 |
| CSS-S29 | 缩容期间查询流量升高 | REAL_BUSINESS | 保持对账，停止下一轮变更 |
| CSS-S30 | 缩容后业务稳定窗口 | REAL_BUSINESS | 达到应用 SLO 才 SUCCEEDED |
| CSS-S31 | 扩容冷却未到 | INJECTED | `SCALE_OUT_COOLDOWN_ACTIVE` |
| CSS-S32 | 缩容冷却未到 | INJECTED | `SCALE_IN_COOLDOWN_ACTIVE` |
| CSS-S33 | 扩容后保护窗口 | INJECTED | `SCALE_OUT_PROTECTION` |
| CSS-S34 | Watcher 重启 | INJECTED | 冷却和历史不丢失 |
| CSS-S35 | 两个相同 idempotency key | INJECTED | 第二次只读返回原动作 |
| CSS-S36 | 两个 profile 指向同集群 | INJECTED | 规范资源级互斥 |
| CSS-S37 | 两个进程并发写 | INJECTED | SQLite 原子约束最多一个意图 |
| CSS-S38 | 409 CSS.0011 | REAL_CONTROL_PLANE | RECONCILING，不立即重试 |
| CSS-S39 | 400 CSS.0001 | REAL_CONTROL_PLANE | BLOCKED，不重试 |
| CSS-S40 | 提交后网络断开 | INJECTED | UNKNOWN，保留互斥，恢复先对账 |
| CSS-S41 | 节点达到目标但 GROWING | REAL_CONTROL_PLANE | 继续 RECONCILING |
| CSS-S42 | 所有节点 200 但动作未清空 | REAL_CONTROL_PLANE | 继续 RECONCILING |
| CSS-S43 | 分片 relocating/initializing | REAL_BUSINESS | 不通过引擎验收 |
| CSS-S44 | 业务探针登录重定向 | REAL_BUSINESS | 探针失败，不通过 |
| CSS-S45 | 业务样本不足 | REAL_BUSINESS | INSUFFICIENT_SAMPLES |
| CSS-S46 | Watcher 缺数后恢复 | INJECTED | 正向新鲜样本后才 resolve |
| CSS-S47 | 告警重复事件 | INJECTED | 稳定指纹去重 |
| CSS-S48 | 通知通道断开后恢复 | INJECTED | 持久投递，不伪造送达 |
| CSS-S49 | 真实压力驱动扩容 | REAL_BUSINESS | 控制面、引擎、业务全过程验收 |
| CSS-S50 | 真实低峰安全缩容 | REAL_BUSINESS | 历史、快照、AZ、引擎、业务均通过 |

## 执行记录字段

每个场景必须写入 `run_id`、`case_id`、`attempt`、`execution_level`、资源规范身份、负载来源、父子任务 ID、policy revision、action ID、API 调用计数、开始/结束时间、预期、实际状态、reason codes、业务指标窗口、清理结果和证据路径。

CSS-S49/S50 需要业务负责人提供稳定基线、压力停止阈值、成功率/P95/吞吐/积压指标和回退联系人。没有这些输入时只能做控制面测试，场景状态为 NOT_READY，不得改写为 PASS。
