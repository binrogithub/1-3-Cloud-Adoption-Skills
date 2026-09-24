# CSS TUI 角色链路验收

这份验收只接受 JiuwenSwarm TUI 会话历史中的持久证据。终端重绘、模型文字说明和本地路由函数结果不能代替角色调用证据。

## 执行

先启动已配置的 TUI，再输入：

```text
查看 css 集群最近 24 小时流量；如果容量不足，先生成扩容计划，调用 ProjectManager 选择角色并完成核验
```

退出或任务完成后，使用会话历史检查：

```bash
python3 scripts/css_tui_role_chain_check.py \
  "$HOME/.jiuwenswarm/agent/sessions/<session>/history.jsonl"
```

通过条件是历史中同时出现 `project-manager`、`css_auto`、`runbook-operator`、`recovery-verifier`，有 CSS 运维工具结果，并且最后一个工具结果之后仍有助手最终消息。失败时保留 `NOT_READY`，继续修复 TUI 或后端链路。

本地检查器不会把一次成功的路由计划当成真实云端扩缩容，也不会把缺少业务探针的容量对账当成业务成功。
