# CSS 稳定性测试问题记录

50 场景执行采用单例闭环：出现未预期结果后停止后续用例，记录证据，修复代码与安装配置，执行相关回归，再重跑当前用例。

每条问题至少记录：`run_id`、`case_id`、资源规范身份、输入、预期、实际、reason codes、API 调用、动作 ID、业务窗口、修复提交和重跑证据。`SKIPPED`、`UNKNOWN`、`BLOCKED` 和 `NOT_READY` 不能改写成 `PASS`。

当前本地 soak、采集效率和安装自检属于控制逻辑证据；真实业务压力、低峰缩容和 24 小时值守必须进入单独的真实验收目录，由 `scripts/css_stability_release_gate.py` 判定。

本轮真实测试修复记录：

- TUI ProjectManager 首次未转发 `--css-profile` 和 `--css-config-dir`，返回 `CSS_PROFILE_REQUIRED`；已修复 Skill/bootstrap，并在真实只读 TUI 会话中验证 profile、拓扑和指标均已返回。
- 原生 workflow 等待错误使用 `run_id`，导致 `async_task_output` 返回 task not found；已改为使用 launch 返回的 `task_id`，并加入失败证据检查。
- CSS workflow 子 Agent 的 bash 环境无法稳定继承宿主 KooCLI 运行上下文，且会丢失 ProjectManager 计划结构；已改为 workflow 宿主直接调用项目 PM 胶水入口，支持注册的 `koo_cli_home`，保留真实计划和角色边界。
- 发布门禁此前固定读取含 SKIPPED 用例的只读报告；已改为存在 `css-50-real-writes.json` 时优先使用真实控制面报告，同时仍以业务验证和 24 小时证据作为发布条件。
