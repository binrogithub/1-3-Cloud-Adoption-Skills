# JiuwenSwarm AutoOps 发布说明

当前工作区是 **candidate-unverified**，尚未形成可发布 RC 或 GA。发布版本、制品 SHA、配置 SHA 和真实验收 run 只能由冻结制品生成后填写；本文不预填不存在的版本号或通过结论。

本轮发布准备覆盖：

- 安装、升级、备份、恢复与持久实例路径；
- 原生 JiuwenSwarm TUI 到 ProjectManager 和 E05/E04/E06 等已登记角色的胶水路由；
- Loki、Prometheus、OpenSearch 的分层就绪、覆盖窗口和异常降级语义；
- Alertmanager webhook、持久 delivery/action 账本、未知外部执行对账和独立业务验证；
- AO50 真实业务验收、关键场景重复运行及带事件 24 小时长稳。

已关闭范围：不修改 JiuwenSwarm 或官方 TUI 源码，不改变 `/root/jiuwenswarm` 虚拟环境，不承诺恢复上游原生工作流栈，不把未验证的远端主机、Kubernetes 集群或任意日志路径声明为支持。

## 已知限制

当前没有最终冻结制品、完整 AO50 业务回执、同制品三次关键场景证据或带事件的真实 24 小时 systemd 证据，因此 release gate 应返回 `NO_GO`。单元测试、fixture、路由记录和空闲长稳不能替代这些证据。

## 发布记录模板

```text
版本：待冻结
制品 SHA-256：待冻结
配置 SHA-256：待验收
环境清单：待验收
RC 判定：NO_GO，直到同制品 P0 证据齐全
GA 判定：NO_GO，直到同制品全部 P1、REL-07 和支持矩阵证据齐全
```
