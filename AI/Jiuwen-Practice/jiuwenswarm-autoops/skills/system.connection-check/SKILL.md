---
name: system.connection-check
version: 0.1.0
owner: jiuwenswarm-autoops
allowed_roles:
  - ops-leader
risk_level: read
executor: local-adapter
timeout_seconds: 30
---

# 系统连接检查

检查 JiuwenSwarm AutoOps 控制端的 MaaS API 连通性，并报告可用模型数量与配置状态。

输入为空。适配器只调用 `${HUAWEI_MAAS_BASE_URL}/models`，API Key 仅从进程环境读取；不得写入任务记录、日志、提示词或返回值。

成功时返回 `status=ready`、端点主机名和模型数量。认证失败、网络失败或返回结构异常时返回非成功状态与非敏感错误类别。该 Skill 不调用任何运维工具，也不访问生产系统。
