# E03 Kubernetes Operator 运行手册

E03 以项目配置作为 Kubernetes 资源目录，通过独立的只读 `kubectl` 适配器查询一个已发布工作负载。当前第一阶段只发布 `staging/orders/order-api` 的目录样例，集群默认关闭，避免新主机误连未知集群。

本机验收集群使用 `config/systemd/jiuwenswarm-autoops-k3s-e03-local.service` 管理。该 unit 只服务于本机 k3s 测试，不属于通用客户安装流程；生产环境应使用客户自己的 Kubernetes 生命周期管理。启用本机验收服务：

```bash
install -m 0644 config/systemd/jiuwenswarm-autoops-k3s-e03-local.service \
  /etc/systemd/system/jiuwenswarm-autoops-k3s-e03-local.service
systemctl daemon-reload
systemctl enable --now jiuwenswarm-autoops-k3s-e03-local.service
```

服务使用固定数据目录和 API 端口 `16443`，并把 kubeconfig 以 `root:rundeck`、`0640` 写入受控目录。停止本机验收集群：`systemctl disable --now jiuwenswarm-autoops-k3s-e03-local.service`。

## 安装后先做依赖检查

新主机安装后先执行只读 preflight：

```bash
python3 scripts/k8s-environment-check.py --cluster autoops-development
```

结果为 `READY` 才表示已发现已注册的 kubeconfig、context 且 Kubernetes API 可达。`kubectl` 客户端存在不等于集群可用；`CLUSTER_NOT_ENABLED`、`KUBECONFIG_NOT_AVAILABLE`、`KUBERNETES_CONTEXT_NOT_FOUND` 和 `KUBERNETES_API_UNREACHABLE` 都会明确阻止 E03 继续。preflight 不读取或输出 kubeconfig 内容，不执行 `apply`、`patch`、`delete`、`exec`。

## 配置

编辑项目或安装后的 `config/kubernetes/workloads.json`，为客户集群填写 `enabled`、已验证的 kubeconfig `context`、kubeconfig 环境变量名、namespace、Deployment 名称、固定 selector、基线副本数和业务服务名。运行时可通过 `AUTOOPS_KUBERNETES_WORKLOADS_FILE` 指向安装后的客户配置文件；凭据不写入 workload 目录，也不进入 TUI 对话或证据文件。

准备恢复闭环时增加 `--require-recovery`，它会检查受保护 Rundeck 注册表中是否已有每个 workload 的固定 `restore_job`：

```bash
python3 scripts/k8s-environment-check.py \
  --cluster autoops-development --require-recovery
```

检查返回 `RUNDECK_JOB_NOT_REGISTERED` 时，E03 仍可只读 inspect，但恢复动作会保持阻塞。

项目随安装器发布可审阅的 Job 模板 `config/rundeck/e03-k8s-restore-order-api-job.json`。导入前要确认客户 workload 的 context、namespace、Deployment、基线副本数和 kubeconfig 路径与模板一致；导入后将返回的 Job ID 写入受保护的 `rundeck-jobs.json`。模板默认只允许 `test-host-01`，不启用定时执行，且 kubeconfig 不随项目发布。

## 只读检查

```bash
python3 scripts/k8s-inspect.py \
  --cluster autoops-development \
  --workload staging/orders/order-api
```

通过 ProjectManager/TUI 时传入同一组已解析参数：

```bash
python3 scripts/autoops-project-manager.py \
  --request "检查 Kubernetes Deployment 副本和 Pod 状态" \
  --cluster autoops-development \
  --workload staging/orders/order-api
```

适配器固定执行四类 `get`：Deployment、匹配 selector 的 Pod、Deployment 相关 Event 和 namespace 内 HPA。结果包含期望/当前/Ready 副本、Pod phase 与重启次数、事件摘要、HPA 冲突和 `evidence_refs`。适配器不接受任意资源名、namespace、selector、JSONPath 或 shell 片段。

## 边界

E03 的 inspect 始终只读，不执行 `apply`、`patch`、`delete`、`exec` 或任意 kubectl 参数。副本恢复适配器已发布固定 `k8s.restore_replicas.v1`，经 Rundeck 唯一写入口执行，复用预授权、目标锁和执行前状态检查；发现 HPA 冲突时暂停，不争抢控制权；Rundeck 成功后必须再次 inspect，确认 desired 和 Ready 副本都达到基线，否则返回 `POSTCONDITION_NOT_MET` 或 `POSTCONDITION_INSPECTION_FAILED`。隔离 kind 集群的节点 Ready、Deployment/Pod/Event/HPA inspect、HPA 阻断、`NO_CHANGE` 和 k3s 真实副本恢复已通过。

本阶段属于 AN-13；inspect 和保护边界已通过隔离集群验收。恢复闭环还要求 Rundeck `autoops` 项目注册 `k8s-restore-order-api` 固定 Job，以及稳定的客户 Kubernetes API；缺少任一项时保持阻塞，不把 E03 恢复标记为完成。

恢复后的 Deployment desired/Ready 只代表资源后置状态。ProjectManager 会继续调用 E09 `recovery-verifier` 的已发布业务探针；没有在 workload 绑定中配置 `business_verification.health_url` 时，结果为 `UNVERIFIED/INCONCLUSIVE`，不会报告业务已恢复。
