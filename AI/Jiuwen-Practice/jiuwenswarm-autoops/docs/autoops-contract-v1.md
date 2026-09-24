# AutoOps 契约 v1

项目内的 TUI、CLI、ProjectManager 和角色适配器共用
`scripts/autoops_contract.py`。MaaS 或原生专家可以提出计划，但进入适配器前必须通过项目契约校验。

## AutoOpsRequest

请求由可信入口生成 `request_id` 和 `task_id`，自然语言原文保留在 `original_request`，模型解析结果保留在结构化字段，字段来源写入 `field_sources`。`scope` 至少包含一个已发布目标引用，`requested_window.requested_minutes` 必须为正整数。

```json
{
  "schema_version": 1,
  "request_id": "req-1",
  "task_id": "task-1",
  "original_request": "排查订单日志",
  "goal": "确认最近24小时是否存在异常",
  "intent": "diagnose",
  "scope": {"service_ref": "orders", "target_ref": "local"},
  "requested_window": {"requested_minutes": 1440},
  "constraints": {"effect": "read"},
  "completion_criteria": {"report": true},
  "field_sources": {"scope.service_ref": "operator"}
}
```

## Plan / Step

`validate_plan()` 校验版本、任务身份、计划状态、步骤字段、依赖引用和依赖环。调用方传入能力注册表时，校验器还会拒绝未发布的 capability。每个步骤必须明确 `invocation_kind`：`native_expert` 表示原生专家，`adapter` 表示直接适配器，`project_route` 表示经 ProjectManager 项目路由；这三类不能靠角色名称推断。

计划默认带有 `budget`：最多 12 个步骤、最多 3 个无依赖只读步骤并行、最多 1 次重规划。计划超过这些边界会在执行前被拒绝。

步骤还必须声明 `effect`、`inputs`、`depends_on`、`when`、`required`、`expected_result` 和正数 `timeout_seconds`。未知依赖、自依赖、重复步骤 ID 和循环依赖都会被拒绝。

```json
{
  "schema_version": 1,
  "task_id": "task-1",
  "plan_revision": 1,
  "goal": "检查服务",
  "scope": {"target_ref": "local"},
  "status": "PLANNED",
  "steps": [{
    "step_id": "inspect",
    "role": "runbook-operator",
    "capability": "host.inspect.v1",
    "invocation_kind": "project_route",
    "effect": "read",
    "inputs": {"target": "local"},
    "depends_on": [],
    "when": "always",
    "required": true,
    "expected_result": {"status": "SUCCEEDED"},
    "timeout_seconds": 300
  }]
}
```

## StepResult 兼容规则

`status` 是规范字段，允许值来自任务步骤状态集合。现有适配器的 `execution_status` 在 v1 过渡期继续保留；校验器在缺少 `status` 时读取它，并返回带规范 `status` 的副本。`SUCCEEDED` 搭配 `error_code`、或非成功步骤标记 `recovery_status=recovered`，都会被拒绝。

校验器只做结构和状态一致性校验，不把退出码 0、结果文本或旧的成功探针自动转换为 recovered。
