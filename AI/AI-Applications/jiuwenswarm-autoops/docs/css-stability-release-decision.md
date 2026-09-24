# CSS 稳定性发布结论

当前结论：`NOT_READY`。

本地代码和回归证据已完成；真实 CSS 控制面 50 场景为 `50/50 PASS`，其中 S49 真实扩容、S50 真实缩容均已完成对账，最终为 2 个健康数据节点且无活动动作。真实 TUI 只读 workflow 已返回 `COMPLETED`，安装自检和服务用户真实只读 watcher 启动均通过，发布门禁能够区分真实控制面证据与真实业务证据。

仍缺少真实发布证据：

- CSS-S49 真实业务压力扩容和 CSS-S50 真实低峰缩容的业务指标窗口；当前仅有 `CONTROL_PLANE_REAL`，业务验证为 `UNVERIFIED`；
- 至少 24 小时墙钟值守、通知恢复和业务探针证据；当前墙钟时长为 0；
- 服务用户升级和回退验收；当前已完成服务用户只读启动验收，升级与回退仍未在独立干净主机上完成。

执行以下命令重新生成结论：

```bash
python3 scripts/css_stability_release_gate.py --evidence-dir docs/evidence/css-stability/<run_id>
```

在上述证据齐全前，不能创建 release tag 或宣称 CSS AutoOps 已通过生产发布验收。

## 2026-09-23 本轮真实复测

本轮新增证据见 [`real-20260923T0645-p0-followup`](evidence/css-stability/real-20260923T0645-p0-followup/README.md)：原生黄色 TUI Team/SwarmFlow 真实调用 ProjectManager→`css_auto`，只读返回 2 个健康 data 节点；TUI 最终报告和两角色调用历史检查均 PASS，生产 CSS 动作账本为 0。E01 写请求仍由生产 `observe` 策略安全阻断。从本地 AutoOps 主机运行的压力预检无法到达 CSS 数据面；从智利 ECS 到 CSS 的认证只读健康检查已通过 3 次，证明可以将智利 ECS 用作负载源，但尚未启动压力流量或扩缩容。

本轮 release gate 仍为 `NOT_READY`：该证据目录没有包含 CSS 50 场景完整记录、独立效率/干净安装/soak 证据或 24 小时真实业务验证，因此只读 TUI PASS 不等于扩缩容或发布通过。旧批次的 50 场景控制面记录与本轮证据分别保留，不能互相代替。
