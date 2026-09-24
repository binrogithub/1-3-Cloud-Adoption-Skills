# E05 本机 Linux 日志降级路径

E05 优先查询 Loki；当 Loki 返回空结果或暂时不可用时，`log-investigate.sh`
自动以只读方式查询本机 systemd journal。这样采集器尚未接入、标签不匹配或
Loki 暂无数据时，不会把“没有证据”误报为“没有异常”。报告会标明：

- `source=local-journal`：本机 journal 提供证据；
- `loki_status=empty` 或 `error`：Loki 的实际状态；
- `query_ref=journal-*`：本机查询的审计引用。

服务名经过固定字符校验，并作为独立参数传给 `journalctl --unit`，不会被拼接
成 shell 命令。查询默认限制在 1–1440 分钟、最多 200 行，E05 仍然没有重启、
安装、修改配置或其他写权限。

通过 `AUTOOPS_LOCAL_JOURNAL_FALLBACK=0` 可以在只允许远端日志的环境关闭该
降级路径。安装示例配置默认开启它。

## 防止同类问题

1. 证据协议必须包含 `source`、`status`、`entry_count` 和 `query_ref`；模型提示
   必须把 Loki 空结果与本机 journal 空结果分别报告。
2. E2E 验收同时覆盖 Loki 有数据、Loki 空但 journal 有数据、两者都空和 Loki
   不可用四条路径。
3. 采集链路监控应检查 Loki 最近写入时间、目标 label 和 collector 状态；空结果
   只能触发诊断分支，不能直接生成“无异常”结论。
4. 所有外部输入都必须经过白名单校验并使用 argv 传递；测试持续覆盖命令注入、
   敏感字段脱敏和行数边界。
