# CSS 稳定性真实验收记录

本文件记录 `CSS-STAB-10.3` 当前真实进展。证据目录为
`docs/evidence/css-stability/real-20260921T1640/`。本轮真实控制面扩缩已经完成，真实业务探针和 24 小时墙钟窗口尚未完成，因此发布门禁仍必须返回 `NOT_READY`。

已完成的真实动作：

- CSS-S49：真实扩容 2→3，完成拓扑和动作对账；耗时约 622 秒。
- CSS-S50：真实缩容 3→2，完成拓扑和动作对账；耗时约 131 秒。
- 最终状态：2 个数据节点健康，活动动作为空；未遗留云端动作。
- 真实 TUI：ProjectManager → `css_auto` 的只读 workflow 返回 `COMPLETED`，8/8 指标有效，`cloud_writes=false`。

这两条扩缩结果的执行层级是 `CONTROL_PLANE_REAL`，不是 `REAL_BUSINESS`；`business_verification` 保持 `UNVERIFIED`，不能据此宣称业务无影响。

## 必填结果文件

证据目录必须包含：

```text
css-50-e2e.json
soak.json
efficiency.json
tui.json
install.json
real-validation.json
```

`css-50-real-writes.json`（存在时发布门禁优先使用它）的 50 个结果同时保留旧的 `id`（例如 `CSS50-49`）和规范 `case_id`（例如 `CSS-S49`）。`CSS-S49` 与 `CSS-S50` 必须满足：

- `status` 为 `PASS`；
- `execution_level` 为 `REAL_BUSINESS`；
- `business_verification` 为 `PASS`、`PASSED` 或 `SUCCEEDED`；
- 包含资源规范身份、策略版本、动作 ID、API 调用计数、业务窗口和清理结果。

`real-validation.json` 至少包含：

```json
{
  "status": "PASS",
  "wall_clock_hours": 24,
  "business_verification": "PASS",
  "scale_out": {"status": "PASS"},
  "scale_in": {"status": "PASS"},
  "cleanup": true
}
```

## 生成和判定

本地行为检查可以先执行：

```bash
python3 scripts/css_stability_soak.py --output <evidence>/soak.json
python3 scripts/css_collection_efficiency.py --output <evidence>/efficiency.json
python3 scripts/css_stability_release_gate.py --evidence-dir <evidence>
```

最终门禁：

```bash
python3 scripts/css_stability_release_gate.py --evidence-dir <evidence>
```

当前证据中的 `real-validation.json` 明确记录业务探针未配置、墙钟时长为 0、但清理完成；因此当前结果为 `NOT_READY`。缺少真实业务基线、24 小时墙钟时长、TUI 实际历史、干净安装或清理确认时，结果必须为 `NOT_READY`。
