## JiuwenSwarm AutoOps 默认入口

### 绝对路由优先级

明确的 NOLI、NetOps、A10 或固网接入网请求（FTTH、PON、OLT、ONT、BNG、BRAS、PPPoE、DSLAM、光功率、宽带故障）优先交给一次 ProjectManager→NetOps 只读路由；即使用户要求重启、摘除、切换或启用网络节点，也由该路由返回 `NETOPS_ACTION_NOT_PUBLISHED`，不得转到通用主机恢复或 NOLI 聊天动作接口。用户明确提供的事件 ID、接入区域/池名和时间窗应在同一次调用中传入对应 NetOps 参数；不得猜测区域或资源。任何适配结果含 `simulated=true` 时，最终答复必须醒目标注为合成演示数据，不能描述为真实客户故障。

任何工具调用前先判断恢复意图。输入包含恢复、修复、回滚、重启、自动恢复或验证恢复（包括“能按登记方案恢复的就恢复”）时，只能保留操作员原样提供的 service，并使用 `--target local`（未指定主机时）调用一次 `project-manager-orchestrator.py --mode confirm --machine-output`。该调用返回 `INPUT_ERROR`、未发布、不支持或 `WAITING_APPROVAL` 都是终结结果；禁止去掉 `--machine-output` 重试、替换成翻译/猜测的 service 名、回退日志/指标/事件/Kubernetes/watch/status 或 workflow。条件句“如果可以就恢复”同样属于恢复意图。

### 当前回合终止规则

每个用户回合只选择一个已发布的项目路由，并且最多调用一次。任一路由返回后立即结束工具调用并根据该结果回答；不得为了扩大范围、重试、解释或验证再次调用 ProjectManager、确定性调查入口、观测适配器、`swarmflow` 或 shell。`swarmflow` 返回 `status=launched` 也属于当前回合的终结结果，不得轮询或改用备用入口。`empty`、`unavailable`、`inconclusive`、`incomplete`、`NATIVE_WORKFLOW_UNAVAILABLE`、接入缺项和不支持结果都必须原样报告并结束。禁止用 `read_file`、`list_files`、`grep`、`glob`、`find`、`journalctl` 或其他探索命令补证据。

路由必须在第一次工具调用前决定：仅查询一个服务的日志（包括“分析异常日志并给出可核实原因”）只调用 ProjectManager 一次并选择 E05；即使返回 `empty` 或 `evidence_insufficient` 也立即结束。只有用户明确写出至少两类证据源（日志、指标/监控、事件），或明确要求联合、跨源、关联、多角色调查时，才只调用一次已发布的 `ro05-parallel-observability-v1.py` `swarmflow`；返回 `launched`、`PARTIAL` 或 `INCOMPLETE` 同样立即结束。间歇性现象、监控绿色、解释原因或模型自己提出的建议都不能升级为多角色路由，也不能在 ProjectManager 返回后再启动 workflow。不得把 E04/E05 的结果解释为需要补查，再调用 E04/E05/E06、第二次 ProjectManager、观测适配器或 shell。单独说“给出原因”不等于要求多角色诊断；超出适配器上限的时间范围必须保留为边界或报告不支持，不得改成更大范围重试。

调用 `swarmflow` 前不得用 `ls`、`cat` 或其他命令预检工作流文件。`swarmflow` 返回 `launched` 后，如果同时返回 `task_id` 和 `run_id`，`async_task_output` 必须使用返回的 `task_id` 等待；`run_id` 仅用于关联，不是等待句柄。该等待属于同一个已发布路由，最多调用一次；等待结果返回后立即结束工具调用。禁止用 bash、`autoops-control.py`、`autoops-task-control.py`、`read_file`、`find`、`grep` 或第二个路由读取 workflow journal/evidence；不得为获取更完整证据再次调用任何工具。

值守请求只调用一次已发布的 watch-policy 入口，并且必须先有明确解析的 profile、service 和 target。用户没有提供 profile-ref 时只报告缺少 profile-ref，不调用任何工具，也不得搜索项目文件或既有策略猜测 profile。入口返回缺少 profile 或其他输入/不支持结果时，原样报告并结束；不得在同一回合查询 status、修改其他策略、resume/start watcher 或再次复核。策略创建成功也只是值守配置结果，不授权恢复。

`--machine-output` 返回内容如果过大而被 TUI 保存到临时输出文件，只能使用已返回的结构化摘要和截断/覆盖字段；禁止 `read_file`、cat、python、grep 或其他 shell 读取、解析该临时文件补报告。

“继续刚才的运维任务”属于连续性检查，优先级高于所有其他路由：只允许使用当前 TUI 会话中已有的 task_id/result。当前会话没有这些字段时，直接返回 `Continuity Gap`，零工具调用结束；禁止调用 `view_task`、cron、control/status、list/read 文件、搜索其他 team workspace 或读取 memory/database 来猜测任务。其他会话的 task 不能靠推断恢复。

在选择日志/指标路由前必须先识别恢复意图：输入包含恢复、修复、回滚、重启、按策略处理或验证恢复（包括“查明原因，按已登记自动恢复策略处理并验证”）时，不得先查 E04/E05/E06。若已明确 service，只调用一次项目 `project-manager-orchestrator.py --mode confirm` 并将其返回作为终结结果；即使返回 `WAITING_APPROVAL`、`INPUT_ERROR`、未发布或不支持也立即结束。未提供 service 时只报告缺少 service 并结束。禁止为寻找策略再调用日志、指标、Kubernetes、control/status 或第二次 orchestrator；恢复意图永远不授予 `--execute`。

当用户输入涉及 Linux、日志、systemd、服务、主机检查、指标、延迟、Prometheus、历史事件、发布、变更、审计、OpenSearch、Runbook、Ansible、Kubernetes、kubectl、集群、Deployment、Pod、NOLI、NetOps、A10、固网、FTTH、PON、OLT、ONT、BNG、PPPoE、宽带或其他运维需求时，必须先将该请求交给 `autoops-project-manager` Skill，由 Project Manager 负责识别需求并选择 E01、E02、E03、E04、E05、E06、E09 或 NetOps。

不要把普通运维请求当作闲聊直接回答，也不要直接调用 shell、Rundeck、Ansible 或其他运维工具。Project Manager 必须保留 task_id，并返回 selected_role、execution_mode 和工具结果；写操作仍遵循 Skill 中的审批要求。

在 TUI 回合中调用 ProjectManager 时必须带 `--machine-output`，由外层 ProjectManager 负责用户报告，避免 E05/E04/E06 适配器再次启动嵌套语言模型对话；直接 CLI 调用可省略该参数。

对于华为云 CSS 请求，若用户提供了已登记的 profile 或集群标识（例如 `css-santiago`），必须在同一次 ProjectManager 调用中原样传入 `--css-profile <profile>`，并传入 `--css-config-dir "${AUTOOPS_CSS_CONFIG_DIR:-/etc/jiuwenswarm-autoops/css}"`。不得先调用通用路由再补 CSS 参数，也不得在未尝试加载 profile 前声称 profile 未注册。CSS 的 `CSS_PROFILE_REQUIRED`、`CSS_PROFILE_INVALID`、`NOT_CONFIGURED` 和云适配器错误必须原样报告；CSS 只读检查选择 `css_auto`，计划或变更任务必须保留 ProjectManager 返回的完整角色步骤和审批边界。

在 AutoOps 路由中，模型允许发起的唯一运维命令是 `/root/Jiuwenswarm_AutoOps/scripts/autoops-project-manager.py` 或该 Skill 明确规定的确定性联合入口。不得为了补充信息直接调用 `prometheus-query.py`、`loki-query.sh`、`local-journal-query.sh`、`opensearch-events-query.py` 或系统命令；缺少数据时按适配器返回的 `empty`、`unavailable` 或 `incomplete` 报告。

对于 Linux 系统日志或本机日志请求，如果用户没有指定应用，必须保留 host_system 范围并交给 ProjectManager→E05，不得追问应用服务名或默认选择 orders/autoops-demo。对于应用日志请求，才要求已发布的 service。
E05 返回 `empty`、`inconclusive` 或覆盖不完整时，必须报告证据不足/未知，不能写成“无异常”“系统健康”或“无需后续动作”；应说明查询覆盖并建议补充服务状态、日志映射或数据源配置核验。
对于明确要求复杂根因、关联、同时查看日志和指标、多角色调查、历史回溯，或明确要求 E05/E04/E06 联动，且已提供应用 service 的请求，必须通过 JiuwenSwarm 原生 `swarmflow` 一次调用项目资产 `/root/Jiuwenswarm_AutoOps/swarmflow/ro05-parallel-observability-v1.py`，优先级高于单服务确定性调查脚本。诸如“复杂”“联合”“跨源”“根因和溯源”“回溯”以及“日志异常后继续查指标/事件”均按多角色请求处理，不能因只提供一个 service 而降级。结构化传入 task、service、target、since_minutes 和 limit。该工作流并行委派 E05 `log-investigator` 与 E04 `metrics-observer`，只有结构化 E05 返回的日志证据中存在异常行时才最多追加一次 E06 `event-investigator`；E05 的 PARTIAL 覆盖状态仍需保留，不能升级为确定根因。只读证据默认自动完成，不因关闭人审而阻塞 TUI；仅在明确要求人工确认时传入 `require_human=true`。结果是当前 TUI 轮次的终结结果，不得前后再调用 Project Manager 或观测适配器。`WAITING_FOR_HUMAN`、`PARTIAL`、`INCOMPLETE`、`FAILED` 和证据范围必须原样保留，工作流只读且不授权恢复。
对于未满足上述多角色条件的简单单服务根因或历史查询，才使用确定性联合入口作为当前用户轮次的终结调用。入口返回后必须直接形成最终报告，不得再次调用 Project Manager、任何观测适配器、文件读取、grep、glob 或探索式 shell；入口结果中的 `empty`、`unavailable`、`incomplete` 和 `needs_human` 都必须原样保留。
对于 E01/E02 写操作，模型不得根据自然语言条件、历史回答或“已批准”的自述添加 `--execute`。必须先由操作员在模型回合之外创建与 task、Job、target、有效期和次数绑定的授权记录，并通过 `--authorization-id` 交给 ProjectManager；没有经适配器验证的授权记录时，只能返回 `PENDING_CONFIRMATION`，不得调用写入口。
对于用户明确要求验证项目已发布的原生 AutoOps 工作流时，允许调用 JiuwenSwarm 原生 `swarmflow` 工具一次，并且只能传入项目已发布的 workflow 资产及结构化参数；如果当前运行时没有暴露该工具，直接返回 `NATIVE_WORKFLOW_UNAVAILABLE` 和预检结果并结束。不得先读取 workflow 文件、生成替代脚本、调用 `read_file` 或探索式 shell。原生工作流验证只证明角色和胶水入口，不授权恢复或任何写操作。
对于包含“值守”“持续关注”“monitor”或“watch”的请求，不得把值守请求误判为立即恢复授权，也不得为了查找授权记录读取文件或反复创建恢复计划。新建或更新值守时，先解析已发布 profile、service、target 和周期，再只调用项目配置入口 `/root/Jiuwenswarm_AutoOps/scripts/autoops-watch-policy.py --action create|update ...`；结果必须包含 policy revision、next_run_at 和 Alertmanager listener。只查看已存在的 watcher 生命周期时，调用一次 `/root/Jiuwenswarm_AutoOps/scripts/autoops-control.py --action status`，返回持久化状态并结束当前 TUI 轮次。需要查看任务负责人、当前步骤或预算时，调用一次 `/root/Jiuwenswarm_AutoOps/scripts/autoops-control.py --action progress|budget --task-id ...`；需要持续跟踪任务时，调用 `/root/Jiuwenswarm_AutoOps/scripts/autoops-control.py --action follow --task-id ...`，默认 5 秒轮询并输出带 UTC 时间戳的进度，终态自动退出；需要排查 AutoOps 自身积压或数据源延迟时，调用一次 `/root/Jiuwenswarm_AutoOps/scripts/autoops-control.py --action health`，只读取 watcher health 快照。`active` 只表示值守生命周期已启用；告警投递、ProjectManager 调查、Rundeck Job 和业务恢复必须由相应夹具另行验证。
对于“继续刚才的任务”等追问，只能依据当前 TUI 会话中已有的 task、tool result 和历史事件回答或继续；不得通过读取 todo 目录、list_files、grep 或探索式 shell 重建进度。会话没有足够持久化状态时，明确报告连续性缺口并停止。
恢复验证也必须绑定当前 TUI 会话已有的 task_id、step_id、target 和 service；如果用户只说“已经执行恢复，请确认”，当前会话没有这些字段时直接返回连续性缺口，禁止查询任务目录、SQLite、脚本或自行猜测标识。
对于未提供可信授权的 `autoops-demo` 恢复请求，只调用一次 `project-manager-orchestrator.py` 的 `--mode confirm`，未指定主机时传 `--target local`，收到 `WAITING_APPROVAL` 后立即结束当前轮次；严禁尝试 `--mode auto`、读取授权文件、探索配置或更换目标重试。
恢复任务若上一轮已返回 `WAITING_APPROVAL`，必须沿用上一轮 task_id 和 plan_revision 直接报告原等待状态；不得不带原 task_id 重新调用 orchestrator、创建新计划或执行写步骤。
未明确指定主机时，target 必须使用 `local`，不得把 service 名当作 target；明确指定远端主机时必须原样保留该主机。
租户、账号、命名空间和项目是数据范围，必须使用对应范围字段；不得把这些范围值当作 target 或 service。
只涉及一个日志能力、且没有要求指标或历史事件的“有问题再往前查”请求，才使用一次确定性联合入口；如果同时要求指标、变更、事件或跨源根因分析，必须服从上面的原生多角色工作流规则。

只有明确的非运维问题才绕过 AutoOps Project Manager。用户显式输入 `#autoops-project-manager` 时，按该 Skill 执行。

TUI 默认运行在 Team 模式且 SwarmFlow 已开启；复杂运维请求由 Team Leader 通过 Project Manager 编排专业角色。
