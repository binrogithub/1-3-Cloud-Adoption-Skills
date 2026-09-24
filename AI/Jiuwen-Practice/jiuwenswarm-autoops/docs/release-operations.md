# JiuwenSwarm AutoOps 发布运维手册

本文面向安装、升级和值守人员。所有命令都针对一个 AutoOps 实例执行，路径应以该实例的安装清单为准。备份和恢复只处理 AutoOps 胶水代码、配置、任务账本与 systemd 单元，不撤销 Rundeck、Ansible、Kubernetes 或其他外部系统已经发生的业务动作。

## 日常检查

```bash
systemctl is-active jiuwenswarm-autoops-watch.service
systemctl is-active jiuwenswarm-autoops-alert-dispatch.service
python3 /opt/Jiuwenswarm_AutoOps/scripts/autoops-control.py --action health
python3 /opt/Jiuwenswarm_AutoOps/scripts/autoops-control.py --action list
```

`health` 只表示本地实例和账本可读；数据源覆盖、任务业务状态和外部执行状态要分别查看。`RECONCILING` 表示外部提交结果未知，必须查询原 execution ID，不能重新提交相同写操作。`PARTIAL` 表示至少一个调查、验证或数据源证据不足，不能改写成成功。

## 停写、备份和恢复

升级或恢复前按顺序停止写入者，并保存命令输出和时间：

```bash
systemctl stop jiuwenswarm-autoops-alertmanager.service
systemctl stop jiuwenswarm-autoops-alert-dispatch.service
systemctl stop jiuwenswarm-autoops-watch.service

backup=/var/backups/jiuwenswarm-autoops/$(date +%Y%m%d-%H%M%S)
python3 /opt/Jiuwenswarm_AutoOps/scripts/autoops-runtime-backup.py create \
  --output "$backup" \
  --install-root /opt/Jiuwenswarm_AutoOps \
  --config-root /etc/jiuwenswarm-autoops \
  --state-root /var/lib/jiuwenswarm-autoops \
  --systemd-root /etc/systemd/system
```

备份使用 SQLite 一致性 backup API，包含已提交的任务、事件、delivery/action 账本、水位、配置和受管 unit；不会复制活跃的 `-wal`/`-shm` 文件。备份清单的 hash 必须保留。恢复前再次确认三个写入者均已停止：

```bash
python3 /opt/Jiuwenswarm_AutoOps/scripts/autoops-runtime-backup.py restore \
  --backup "$backup" --assume-stopped
```

恢复返回 `external_actions_replayed=false` 才能继续。未确认的 delivery、逻辑 action、`operation_id` 和 `external_execution_id` 必须仍在账本中；恢复工具不会根据它们自动重放外部写入。

恢复后先启动 watcher 和 dispatch，再查询原任务：

```bash
systemctl daemon-reload
systemctl start jiuwenswarm-autoops-watch.service
systemctl start jiuwenswarm-autoops-alert-dispatch.service
python3 /opt/Jiuwenswarm_AutoOps/scripts/autoops-task-reconcile.py \
  --state-db /var/lib/jiuwenswarm-autoops/autoops-state.db \
  --task-id <RECONCILING-task-id>
```

对账命令只能沿用原 `operation_id` 查询既有执行。若 Rundeck 返回仍在运行，任务保持 `RECONCILING`；若独立业务探针失败，任务保持 `PARTIAL` 或 `FAILED`。取消请求也只阻止新步骤，不抹去已提交的外部执行。

## 暂停、停止和清理

暂停只阻止新的 watcher 消费，停止还要停止 webhook 和 dispatch 写入者。先保存 `autoops-control.py` 的状态输出，再执行控制操作；不要直接删除 state-root、events、notifications 或 backup。每次验收夹具必须使用唯一 `run_id`，只删除该 run 的临时目录；客户配置、任务账本和未决 execution 永远保留。

清理失败时停止后续验收并标记 `BLOCKED`。不得通过删除未决记录、重置消费水位或重新生成 operation key 来清除失败。

## 卸载

卸载前先停止并留存状态与备份。只删除 AutoOps 自己登记的 unit、命令链接和 runtime；客户配置、状态账本、事件、未决 execution 和备份需要按客户保留策略单独归档，不由卸载动作隐式删除：

```bash
systemctl disable --now jiuwenswarm-autoops-alertmanager.service \
  jiuwenswarm-autoops-alert-dispatch.service jiuwenswarm-autoops-watch.service
rm -f /usr/local/bin/Jiuwen_autoops_tui /usr/local/bin/jiuwen_autoops_tui
systemctl daemon-reload
```

确认没有其他实例使用同一目录后，再由管理员按备份策略移除 `/opt/Jiuwenswarm_AutoOps`。`/etc/jiuwenswarm-autoops` 和 `/var/lib/jiuwenswarm-autoops` 不属于自动清理范围；保留它们可以支持回退和后续对账。

## 常见故障

| 现象 | 处理 |
|---|---|
| watcher 未运行 | 检查 `systemctl status`、runtime.json、服务账号可访问的 Python 和状态目录权限。 |
| Loki 无数据 | 区分空 stream 与 503/认证/TLS/超时；先查看本机 journal，再报告覆盖不足，不能把空结果当 clean。 |
| dispatch 重复投递 | 查看 SQLite `dispatch_deliveries`、`dispatch_actions` 和 `dispatch_watermarks`；同 incident 的同一 action 只能有一条逻辑记录。 |
| 外部结果未知 | 保持 `RECONCILING`，运行原 execution 对账；禁止盲目重试 POST。 |
| TUI 看不到任务 | 确认 TUI、PM、watcher 和 control 使用同一安装清单中的 instance roots，不能混用 checkout 的 `.runtime`。 |
| 配置缺失 | 补齐 `/etc/jiuwenswarm-autoops` 中的客户配置后重新运行安装/预检；日常启动不会隐式扩大权限或改写配置。 |
