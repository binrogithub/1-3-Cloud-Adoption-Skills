# huawei-codearts-devops-operations

## Purpose

Operate everything in Huawei Cloud CodeArts EXCEPT project planning/design: CodeArts Repo, Check, Build, Artifact, TestPlan, Deploy, and Pipeline, using hcloud CLI (KooCLI). Discover resources, and where an operation's parameters are confirmed, create/modify and verify them. Where they are not confirmed, document the gap and route to a live probe, the console, or CodeArts Pipeline — never invent a command.

This is the operational counterpart to `huawei-codearts-project-design` (CodeArts Req / ProjectMan), which owns project creation. This skill never touches project creation/design; it only reads an existing `project_id`.

## Services covered

| Service | `hcloud` service name | Former/legacy name | Purpose |
|---|---|---|---|
| CodeArts Repo | `CodeArtsRepo` | CodeHub | Git-based code hosting: repositories, branches, members, SSH keys. |
| CodeArts Check | `CodeCheck` | CodeCheck (this is still the current KooCLI/API Explorer service name) | Static and security code-quality checks on a repository. |
| CodeArts Build | `CodeArtsBuild` | CodeCI / CloudBuildEx | Compiles source code into build artifacts and packages configuration/resource files. |
| CodeArts Artifact | `CodeArtsArtifact` | CloudArtifact | Manages build-artifact package repositories (Maven, npm, PyPI, NuGet, generic, Docker, and more). |
| CodeArts TestPlan | `CloudTest` | CloudTest (this is still the current KooCLI/API Explorer service name) | Test plan, test case, and execution-tracking management. |
| CodeArts Deploy | `CodeArtsDeploy` | CloudDeploy | Automates deployment of applications to hosts or containers. |
| CodeArts Pipeline | `CodeArtsPipeline` | CloudPipeline | Orchestrates CodeArts Check, Build, TestPlan, and Deploy tasks into a single CI/CD workflow. |

## Confirmed vs. unconfirmed operations per service

| Service | Confirmed (full parameter table verified) | Listed but not independently parameter-verified |
|---|---|---|
| CodeArts Repo | `CreateRepository`, `ListUserAllRepositories`, `ShowRepository` | `AddSshKey`, `ListSshKeys`, `ListRepoMembers`, `AddRepoMembers`, `CreateNewBranch`, `ListBranchesByRepositoryId`, `DeleteRepository` |
| CodeArts Check | `ShowTaskListByProjectIdV2`, `ShowTaskCmetrics`, `ShowTaskDetailV2`, `ShowTaskDefectsV2` | `StopTaskByIdV2` |
| CodeArts Build | `ShowJobConfigDiff` | none |
| CodeArts Artifact | `ListAllRepositories`, `ShowMavenInfo`, `ShowFileTree` | `CreateArtifactory`, `DeleteRepository`, `ListChildProxyRepositoriesList`, `ListArtifactoryComponent` |
| CodeArts TestPlan | `CreateTestCaseInPlan` | `ShowPlans` |
| CodeArts Deploy | `CreateHostCluster`, `ListEnvironments`, `ListEnvironmentHosts`, `StartDeployTask` | `ListNewHosts`, `ShowDeployTaskDetail` |
| CodeArts Pipeline | `CreatePipelineNew`, `RunPipeline`, `ShowPipelineRunDetail` | `ListPipelines`, `ListExecutionsOverview` |

## Architecture

```
Operation Intent (target_service, action, region, project)
                │
      Resolve project_id (hcloud ProjectMan ListProjectsV4)
                │
      hcloud <SERVICE_NAME> --help   (confirm operations available)
                │
      Discover existing resources (List.../Show... read call)
                │
        ┌───────┴────────┐
        │                │
  Read-only request   Write requested
        │                │
   (stop here)      Explicit approval
                          │
                 Execute write operation
                          │
                  Verify (read-back call)
```

## Known capability gaps

| Gap ID | Service | Decision |
|---|---|---|
| GAP-CODEARTS-OPS-101 | CodeArts Repo | PROBE_HELP_BEFORE_USE |
| GAP-CODEARTS-OPS-102 | CodeArts Check | USE_CONSOLE_OR_PIPELINE_FOR_CREATE |
| GAP-CODEARTS-OPS-103 | CodeArts Build | PROBE_THEN_FALLBACK_TO_PIPELINE_OR_CONSOLE |
| GAP-CODEARTS-OPS-104 | CodeArts Artifact | PROBE_HELP_BEFORE_USE |
| GAP-CODEARTS-OPS-105 | CodeArts TestPlan | PROBE_HELP_BEFORE_USE |
| GAP-CODEARTS-OPS-106 | CodeArts Deploy | AVOID_DEPRECATED_OP_PROBE_REPLACEMENT |
| GAP-CODEARTS-OPS-107 | CodeArts Pipeline | PROBE_HELP_AND_REUSE_CONSOLE_EXPORTED_DEFINITION |

The most significant gap is CodeArts Build (`GAP-CODEARTS-OPS-103`): no create/run build-task operation could be confirmed under the current `CodeArtsBuild` service name at authoring time. See `SKILL.md` → "Per-service operations" and "Capability gap handling" for full detail on every gap.

## Rules summary

1. Each service has its own distinct `hcloud` service name; there is no generic `CodeArts` service name and no dedicated MCP for any of them
2. Any operation not in a service's confirmed-operations table must be probed live (`hcloud <SERVICE_NAME> <OPERATION> --help`) before use
3. DISCOVER BEFORE CREATE: resolve every ID via a read operation, never hardcode
4. VERIFY AFTER EVERY WRITE
5. Every write operation requires explicit approval
6. The seven service modules are independent of each other and of CodeArts Req project design/creation
7. Never include secrets in commands, examples, or logs

## Required tools

| Tool | Purpose |
|---|---|
| hcloud CLI (KooCLI) | All operations across all seven services |
| Huawei Cloud auth (AK/SK) | API access |
| An existing CodeArts project | project_id required by nearly every operation |

## Workflow summary

1. Parse Intent → 2. Discover Auth/Region/Project → 3. Confirm Target Service Reachability → 4. Run the Target Service's Module (Discover → Plan → Execute → Verify, from `SKILL.md` → "Per-service operations") → 5. Closure

## Automation level by phase

| Phase | Automation | Mechanism |
|---|---|---|
| Parse intent | AUTOMATED | Logic |
| Discovery (auth/region/project) | ASSISTED | hcloud CLI read-only |
| Service reachability probe | ASSISTED | hcloud CLI read-only (`--help`) |
| Per-service discovery | ASSISTED | hcloud CLI read-only |
| Per-service create/write | ASSISTED | hcloud CLI + approval |
| Per-service verification | ASSISTED | hcloud CLI read-only |
| Closure | AUTOMATED | Logic |

## hcloud / verification status

- Verified from: official public CodeArts API Reference pages for each of the seven services (the "Online Debugging"/"CLI Examples" link on each operation's own page confirms the literal `hcloud` service name)
- Live CLI test performed: **No** (authoring environment had web-search/fetch access to public documentation only)

## MCP dependencies

| MCP | Required | Purpose |
|---|---|---|
| huaweicloud-ticket | No | Support escalation if a capability gap blocks a requested action and manual escalation is desired |

No dedicated MCP exists for any of the seven services. All operations via hcloud CLI.

## Approval gates

- Any create/update/start/run action, for any of the seven services
- Reuse of an existing resource instead of creating a new one
- Any delete/stop-style rollback action (only after confirming the operation exists for that service)

## Outputs

- artifacts/codearts-ops-intent.json
- artifacts/codearts-ops-auth-discovery.json
- artifacts/codearts-ops-project-resolution.json
- artifacts/codearts-ops-service-capability-probe.json
- artifacts/codearts-ops-execution-result.json
- artifacts/codearts-ops-verification.json
- artifacts/codearts-ops-final-report.md

## Known limitations

- CodeArts Build's create/run capability is unresolved; only `ShowJobConfigDiff` is confirmed
- Several operations across Repo, Artifact, TestPlan, Deploy, and Pipeline are listed/known to exist but not independently parameter-verified (see the table above)
- CodeArts Req / ProjectMan project planning/design is entirely out of scope (see the companion skill)
- No live hcloud CLI or tenant test was performed during authoring

## Troubleshooting

See `SKILL.md` → "Troubleshooting" for the full table.

| Symptom | Action |
|---|---|
| An operation is missing from `hcloud <SERVICE_NAME> --help` | Use the console, or (Build only) a CodeArts Pipeline job |
| `ListProjectsV4 --search=` returns no match | Use the companion `huawei-codearts-project-design` skill first |
| Write operation rejected (403) | Request the specific CodeArts permission for that service/action |
| Region rejected | Use a region already confirmed for other CodeArts services in the tenant |

## Maturity status

**READY_WITH_WARNINGS**

Six of the seven services have at least one operation confirmed with a full parameter table from its own public API Reference page. CodeArts Build has only a configuration-diff read operation confirmed; its create/run capability is an open gap. All write operations require approval. Every service module documents its own gap and probe-before-use requirement.

## Evidence

| Evidence | Type |
|---|---|
| At least one operation per service confirmed via its own "CLI Examples" link (repo, check, build, artifact, testplan, deploy, pipeline) | VERIFIED_FROM_PUBLIC_API_DOCS |
| Several further operations per service listed/known to exist but not independently parameter-verified | PARTIAL |
| No dedicated MCP exists for any of the seven services | VERIFIED_FROM_PUBLIC_API_DOCS |
| CodeArts Build create/run capability | NOT_CONFIRMED |
| Live hcloud CLI / tenant execution | NOT_LIVE_TESTED |
