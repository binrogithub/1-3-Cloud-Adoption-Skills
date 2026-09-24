# CSS AutoOps 升级与恢复

升级前先停止 CSS watcher 的新写入，使用 `scripts/css_migrate.py` 备份并迁移动作账本：

```bash
python3 scripts/css_migrate.py \
  --db /var/lib/jiuwenswarm-autoops/css-actions.sqlite3 \
  --backup /var/lib/jiuwenswarm-autoops/backup/css-actions.sqlite3
```

迁移只增加兼容字段并保留未完成动作。升级后先执行安装自检，再启动 watcher；状态为 `UNKNOWN`、`RECONCILING`、`CAPACITY_READY` 或 `VERIFYING_BUSINESS` 的动作必须继续对账，不能通过重复提交恢复。

如果目标版本不能安全作为旧账本的写入者，应停止升级后的写入并恢复备份，保留原账本和事件记录。删除账本、清空冷却或强制缩回节点数都不是恢复步骤。
