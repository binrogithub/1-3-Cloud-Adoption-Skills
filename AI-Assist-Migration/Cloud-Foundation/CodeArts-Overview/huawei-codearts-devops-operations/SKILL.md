---
name: huawei-codearts-devops-operations
version: 1.0.0
description: Operate Huawei Cloud CodeArts Repo, Check, Build, Artifact, TestPlan, Deploy, and Pipeline (everything in CodeArts except CodeArts Req project planning/design) via hcloud CLI (KooCLI) — discover resources, and where confirmed, create/modify and verify them, with documented, per-service capability gaps instead of invented commands.
category: cicd-operations
risk_level: medium-high
status: READY_WITH_WARNINGS
requires_explicit_approval: true
license: Apache-2.0
compatibility:
  - OpenCode
  - Hermes
metadata:
  domain: DevOps-Execution
  family: CodeArts-Toolchain-Operations
  service: CodeArts-Repo-Check-Build-Artifact-TestPlan-Deploy-Pipeline
  risk_level: medium-high
  status: READY_WITH_WARNINGS
  create_operation_verification: PARTIAL_PUBLIC_DOCS_VERIFIED_NOT_LIVE_TESTED
---

# Purpose

Operate the seven Huawei Cloud CodeArts services that are NOT project planning/design — CodeArts Repo, Check, Build, Artifact, TestPlan, Deploy, and Pipeline — using hcloud CLI (KooCLI) as the only mechanism. For each service this skill discovers existing resources, and where an operation's parameters are confirmed against its own API Reference page, creates/modifies and verifies them. Where an operation cannot be confirmed (most notably build-task creation/execution), this skill documents the gap explicitly and routes to a live probe, the console, or CodeArts Pipeline, instead of inventing a command.

This skill is the operational counterpart to the companion `huawei-codearts-project-design` skill, which owns CodeArts Req (ProjectMan) project planning and creation. This skill never creates, renames, or deletes a CodeArts project; it only resolves an already-existing `project_id`.

# Supported scenario

- Source: an operation intent naming exactly one target service (repo, check, build, artifact, testplan, deploy, or pipeline) and an action (discover, create, or verify)
- Target: a resource within that service (repository, check task, build task config, artifact repository, test plan/case, host cluster/environment/deployment task, or pipeline/pipeline run), fully identified by its own ID
- Mechanism: each service's own REST API called through hcloud CLI, under that service's own `hcloud` service name (see table below); no dedicated MCP exists for any of the seven
- Storage: none beyond the artifacts this skill itself generates
- Topology: single-region, single-service operation per invocation

| Service | `hcloud` service name | Former/legacy name |
|---|---|---|
| CodeArts Repo | `CodeArtsRepo` | CodeHub |
| CodeArts Check | `CodeCheck` | CodeCheck (this is still the current KooCLI/API Explorer service name) |
| CodeArts Build | `CodeArtsBuild` | CodeCI / CloudBuildEx |
| CodeArts Artifact | `CodeArtsArtifact` | CloudArtifact |
| CodeArts TestPlan | `CloudTest` | CloudTest (this is still the current KooCLI/API Explorer service name) |
| CodeArts Deploy | `CodeArtsDeploy` | CloudDeploy |
| CodeArts Pipeline | `CodeArtsPipeline` | CloudPipeline |

# When to use this skill

- Creating or listing CodeArts Repo repositories, and querying their details
- Listing CodeArts Check tasks and reading their code-quality metrics and issues
- Inspecting CodeArts Build task configuration differences (the only confirmed operation for this service)
- Listing CodeArts Artifact package repositories and querying Maven repository/credential info
- Listing CodeArts TestPlan test plans and attaching existing test cases to a plan
- Creating a CodeArts Deploy host cluster, listing environments/hosts, and starting an existing deployment task
- Listing CodeArts Pipelines, running a pipeline, and checking a pipeline run's status
- Auditing what resources exist across any of these seven services in a tenant/region/project

# When not to use this skill

- Creating, renaming, deleting, or configuring the basic design of a CodeArts Req (ProjectMan) project — use the companion `huawei-codearts-project-design` skill
- Managing work items, iterations, sprints, or Wiki content inside a project — out of scope for both this skill and the project-design skill
- Authoring a CodeArts Pipeline's stage/job graph from scratch via CLI — this skill runs and inspects pipelines whose definition already exists (console, YAML, or an externally supplied `definition` payload)
- Uploading/downloading actual package files to/from a CodeArts Artifact repository, or performing git operations (clone/push/pull/merge) against a CodeArts Repo repository — use the package manager or git CLI directly, not hcloud
- Creating or starting a CodeArts Check task, or creating/running a CodeArts Build task, when no confirmed hcloud operation exists for that action (see the per-service capability gaps) and neither the console nor a CodeArts Pipeline substitute is acceptable to the requester
- When hcloud CLI is not available and cannot be installed

# Required inputs

- target_service (one of: repo, check, build, artifact, testplan, deploy, pipeline)
- action (discover, create, or verify — the create action is only available for the services/operations listed as confirmed or freshly probed in `# Per-service operations`)
- source_region
- project_id or project_name (used to resolve project_id via ProjectMan)
- approval_owner (required whenever action is create)

# Optional inputs

- repo_name / repository_uuid (CodeArts Repo)
- task_id (CodeArts Check)
- job_id (CodeArts Build)
- repository_name / tenant_id (CodeArts Artifact)
- plan_id / testcase_id_list / service_id (CodeArts TestPlan)
- application_id / environment_id / host_cluster_name / deployment_task_id (CodeArts Deploy)
- pipeline_id / pipeline_definition (CodeArts Pipeline)
- description (where the target operation supports one)

# Required MCPs

None. All operations across all seven services are performed via hcloud CLI.

# Optional MCPs

- huaweicloud-ticket (only to open a support ticket if a capability-gap probe fails for a critical-path operation and manual escalation is desired)

# Tool selection policy

- Use hcloud CLI for ALL operations across CodeArts Repo, Check, Build, Artifact, TestPlan, Deploy, and Pipeline: discovery, creation (where confirmed), and verification
- Never use a generic `hcloud CodeArts ...` service name; each service has its own distinct name (`CodeArtsRepo`, `CodeCheck`, `CodeArtsBuild`, `CodeArtsArtifact`, `CloudTest`, `CodeArtsDeploy`, `CodeArtsPipeline`) — using the wrong one, or inventing `CodeArts` as a catch-all, is a Rule violation, not a shortcut
- Never assume an operation not in a service's confirmed-operations table (see `# Per-service operations`) is available without probing it live first (`hcloud <SERVICE_NAME> <OPERATION> --help`)
- Never use huaweicloud-ticket to substitute a missing capability with an invented command; it is for support escalation only
- Never use this skill to create, rename, or delete a CodeArts Req project; resolve `project_id` read-only via `hcloud ProjectMan ListProjectsV4` and otherwise defer to the companion project-design skill
- For CodeArts Build specifically, if no create/run operation can be confirmed live, prefer routing the build through an already-defined CodeArts Pipeline job over the console when both are acceptable to the requester, since it keeps the action auditable through this same skill's Pipeline module

# Safety and approval gates

1. Any create/update/start/run operation (across any of the seven services) requires explicit approval before execution
2. Reusing an existing resource instead of creating a new one (for example, a repository that already exists with the intended name) requires explicit confirmation from the approval owner
3. Any delete/stop-style rollback action requires explicit approval and must first be confirmed to actually exist for that service (see `# Rollback` below) — never assumed
4. Starting a CodeArts Deploy deployment task or running a CodeArts Pipeline are treated as high-impact write actions (they can affect running environments) and require explicit approval every time, even on repeat requests
5. Adding members/roles to a CodeArts Repo repository, or attaching test cases to a CodeArts TestPlan plan, requires explicit approval

# Rules

1. Each of the seven services in this skill's scope is exposed through hcloud CLI under its own distinct service name; there is no generic `CodeArts` service name and no dedicated MCP for any of them. [VERIFIED_FROM_PUBLIC_API_DOCS]

2. **CodeArts Repo** is exposed under the hcloud service name `CodeArtsRepo` (formerly `CodeHub`). Confirmed operations with a fully verified parameter table: `CreateRepository`, `ListUserAllRepositories`, `ShowRepository`. AddSshKey, ListSshKeys, ListRepoMembers, AddRepoMembers, CreateNewBranch, ListBranchesByRepositoryId, and DeleteRepository are confirmed to exist for CodeArtsRepo (listed by hcloud CodeArtsRepo --help / API Explorer), but their exact parameter sets were not independently checked against each operation's own API Reference page during authoring. [VERIFIED_FROM_PUBLIC_API_DOCS] [PROBE_HELP_BEFORE_USE]

3. **CodeArts Check** is exposed under the hcloud service name `CodeCheck` (formerly `CodeCheck (this is still the current KooCLI/API Explorer service name)`). Confirmed operations with a fully verified parameter table: `ShowTaskListByProjectIdV2`, `ShowTaskCmetrics`, `ShowTaskDetailV2`, `ShowTaskDefectsV2`. No operation to create or trigger-run a check task was found in the public CodeArts Check API Reference under the CodeCheck service; check tasks are created and started from the CodeArts Check console or from a CodeArts Pipeline job. This skill only lists tasks and reads their metrics/issues via hcloud; it does not create or start check tasks. [VERIFIED_FROM_PUBLIC_API_DOCS] [USE_CONSOLE_OR_PIPELINE_FOR_CREATE]

4. **CodeArts Build** is exposed under the hcloud service name `CodeArtsBuild` (formerly `CodeCI / CloudBuildEx`). Confirmed operations with a fully verified parameter table: `ShowJobConfigDiff`. This is this skill's most significant capability gap, analogous to CreateProjectV4 in the companion CodeArts Req skill. The legacy build-task operations (CreateBuildJob, UpdateBuildJob, ListDeployTasks-style job listing) live under the older 'CodeCI' API namespace and several are explicitly marked deprecated or 'Out-of-date'/'Unavailable Soon' in their own API Reference pages. The current, non-deprecated CodeArtsBuild namespace only had ShowJobConfigDiff confirmed with a full parameter table at authoring time. No create-build-task or run/start-build-task operation could be confirmed under the current CodeArtsBuild service name. Before relying on any create/run/list build operation, this skill MUST probe `hcloud CodeArtsBuild --help` live and cross-check the operation's own API Explorer 'CLI Examples' tab; if the operation is missing, deprecated, or its parameters cannot be confirmed, use the CodeArts Build console, or drive the build through a CodeArts Pipeline job (see the pipeline module) instead of guessing a command. [VERIFIED_FROM_PUBLIC_API_DOCS] [PROBE_THEN_FALLBACK_TO_PIPELINE_OR_CONSOLE]

5. **CodeArts Artifact** is exposed under the hcloud service name `CodeArtsArtifact` (formerly `CloudArtifact`). Confirmed operations with a fully verified parameter table: `ListAllRepositories`, `ShowMavenInfo`, `ShowFileTree`. CreateArtifactory (creating a non-Maven repository) is confirmed to exist by name (it appears as the documented 'next topic' after DeleteRepository in the Repository Management section) but its full request-body parameter table was not independently fetched/verified during authoring. Probe `hcloud CodeArtsArtifact CreateArtifactory --help` and cross-check the CLI Examples tab before scripting a create call. [VERIFIED_FROM_PUBLIC_API_DOCS] [PROBE_HELP_BEFORE_USE]

6. **CodeArts TestPlan** is exposed under the hcloud service name `CloudTest` (formerly `CloudTest (this is still the current KooCLI/API Explorer service name)`). Confirmed operations with a fully verified parameter table: `CreateTestCaseInPlan`. ShowPlans (listing test plans in a project) is confirmed to exist and to sit immediately before CreateTestCaseInPlan in the Test Plan Management section (GET .../plans, consistent with the sibling path .../plans/{plan_id}/testcases/batch-add), but its own query-parameter table was not independently fetched. In addition, KooCLI's exact CLI syntax for the testcase_id_list ARRAY body parameter of CreateTestCaseInPlan was not observed live; confirm the current array syntax with `hcloud CloudTest CreateTestCaseInPlan --help` or the operation's CLI Examples tab before scripting it, rather than guessing a bracket/comma format. [VERIFIED_FROM_PUBLIC_API_DOCS] [PROBE_HELP_BEFORE_USE]

7. **CodeArts Deploy** is exposed under the hcloud service name `CodeArtsDeploy` (formerly `CloudDeploy`). Confirmed operations with a fully verified parameter table: `CreateHostCluster`, `ListEnvironments`, `ListEnvironmentHosts`, `StartDeployTask`. The application/task-listing operation ListDeployTasks (GET /v2/{project_id}/tasks/list) is confirmed to exist and confirmed under the CodeArtsDeploy service name, but its own API Reference page explicitly states it 'will not be maintained after September 30, 2024' and directs callers to use ListAllApp instead; ListAllApp's parameters were not independently verified during authoring. Do not use ListDeployTasks for new automation; probe `hcloud CodeArtsDeploy ListAllApp --help` first, and treat deployment-task/application listing as needing live confirmation. [VERIFIED_FROM_PUBLIC_API_DOCS] [AVOID_DEPRECATED_OP_PROBE_REPLACEMENT]

8. **CodeArts Pipeline** is exposed under the hcloud service name `CodeArtsPipeline` (formerly `CloudPipeline`). Confirmed operations with a fully verified parameter table: `CreatePipelineNew`, `RunPipeline`, `ShowPipelineRunDetail`. ListPipelines is confirmed to exist (its JSON response shape was observed in the public API Reference example), but its query-parameter table (pagination fields such as offset/limit, and any filters) was not independently fetched during authoring. CreatePipelineNew's 'definition' body field is a large nested JSON structure (stages/jobs/steps) whose full schema was only partially observed via example payloads; do not hand-author a 'definition' value from guesswork — generate it from the console's 'Create Pipeline' / YAML editor, or from a previously exported pipeline, and pass it through unmodified. [VERIFIED_FROM_PUBLIC_API_DOCS] [PROBE_HELP_AND_REUSE_CONSOLE_EXPORTED_DEFINITION]

9. DISCOVER BEFORE CREATE: for every service, always run its discovery/list operation before creating anything; never hardcode `project_id`, `repository_uuid`, `task_id`, `job_id`, `application_id`, `environment_id`, `plan_id`, or `pipeline_id` — resolve them via read operations. [VERIFIED_FROM_PUBLIC_API_DOCS]

10. VERIFY AFTER EVERY WRITE: every create/update/start/run operation must be followed by that same service's read/verify operation (see `# Per-service operations`). [VERIFIED_FROM_PUBLIC_API_DOCS]

11. Every write operation requires explicit approval before execution. [INFERRED]

12. This skill's scope excludes CodeArts Req (ProjectMan) project planning/design entirely; it only resolves an existing `project_id` via `hcloud ProjectMan ListProjectsV4` and never creates, renames, or deletes a project. [INFERRED] (explicit scope boundary requested when this skill was authored)

13. Never include secrets (AK, SK, tokens, passwords) in commands, examples, files, or logs; use the credentials already configured in the local hcloud profile. [INFERRED]

14. Each of the seven service modules is independent: a request scoped to one service must not require having exercised any other service's workflow first, and must not silently issue commands against a different service to compensate for a gap. [INFERRED] (explicit design requirement requested when this skill was authored)

15. This skill was authored and verified from the official public CodeArts API Reference pages for each of the seven services (specifically each operation's own "Online Debugging"/"CLI Examples" link, which exposes the literal `hcloud` service name). It was **not** executed against a live hcloud CLI installation or a live Huawei Cloud tenant. The first real use of this skill for any given service in any environment MUST start with that service's discovery probe (`hcloud <SERVICE_NAME> --help`) before relying on any operation not in its confirmed-operations table. [NOT_LIVE_TESTED]

# Prerequisites

| Tool or resource | Required | Purpose | Verification |
|---|---:|---|---|
| hcloud CLI (KooCLI) | Yes | All operations across all seven services | `hcloud version` |
| Huawei Cloud authentication (AK/SK) | Yes | API access | `hcloud configure show --cli-profile=default` |
| An existing CodeArts project | Yes | project_id required by nearly every operation in scope | `hcloud ProjectMan ListProjectsV4 --search=` |
| Target region (CodeArts-supported) | Yes | Service region/endpoint | Confirm via a successful `hcloud <SERVICE_NAME> --help`/discovery call |
| Per-service resource-creation permission | Only if action=create | Ability to create/modify the target resource | Confirmed only by a successful call or console check |
| Approval owner | Yes (for create actions) | Authorizes write operations | Specified in intent |
| Pre-existing check task / build task / test plan+cases / application+environment+deploy task / pipeline definition | Depends on target_service | This skill does not create these container resources for Check, Build, TestPlan, Deploy, or Pipeline — only operates within them | See `# Prerequisites` above |
| huaweicloud-ticket MCP | No | Support escalation if a capability gap blocks a request | MCP availability check |

See `# Prerequisites` above for full detail.

# Workflow

This skill's workflow has a short, generic front section (parse intent, discover auth/region/project) common to all seven services, followed by exactly one per-service module selected by `target_service`. The per-service modules are NOT sequential steps of one pipeline — only the module matching the request's `target_service` is executed.

## STEP 1 — PARSE INTENT

**Classification: AUTOMATED**

**Objective**: Extract and validate target_service, action, region, project reference, and any service-specific identifiers.

**Inputs**: User request.

**Preconditions**: None.

**Command**: None (parsing logic).

**Approval requirement**: None.

**Verification**: Confirm target_service is exactly one of `repo`, `check`, `build`, `artifact`, `testplan`, `deploy`, `pipeline`, and action is one of `discover`, `create`, `verify`.

**Expected result**: Complete intent object with a single target_service.

**Failure action**: If target_service is missing, ambiguous, or not one of the seven, STOP and request clarification. Do not guess which service was meant.

**Evidence artifact**: `artifacts/codearts-ops-intent.json`

## STEP 2 — DISCOVER AUTHENTICATION, REGION, AND PROJECT

**Classification: ASSISTED**

**Objective**: Verify hcloud CLI is installed/configured, and resolve the CodeArts project_id.

**Inputs**: source_region, project_id_or_project_name.

**Preconditions**: hcloud CLI installed (see `# Prerequisites` above).

**Commands** (read-only):

```bash
hcloud version
hcloud configure show --cli-profile=default
hcloud ProjectMan ListProjectsV4 --cli-region=<REGION> --offset=0 --limit=10 --search="<PROJECT_NAME>"
```

**Approval requirement**: None.

**Verification**: Version and profile confirmed; exactly one project resolves for the given name/ID.

**Expected result**: Authentication valid; `project_id` resolved.

**Failure action**: STOP. If zero or multiple projects match, do not guess; if zero, this indicates the project-design step (a different skill) has not run yet.

**Evidence artifact**: `artifacts/codearts-ops-auth-discovery.json`, `artifacts/codearts-ops-project-resolution.json`

## STEP 3 — CONFIRM TARGET SERVICE REACHABILITY

**Classification: ASSISTED**

**Objective**: Confirm the target service responds and list its operations.

**Inputs**: target_service.

**Preconditions**: Step 2 completed.

**Command** (read-only): `hcloud <SERVICE_NAME> --help`, using the exact service name from the table in `# Supported scenario` above.

**Approval requirement**: None.

**Verification**: The command lists operations rather than erroring.

**Expected result**: Target service confirmed reachable; the confirmed/unconfirmed operation split for this service (see `# Per-service operations`) is reviewed.

**Failure action**: STOP. Report the region/service/connectivity error.

**Evidence artifact**: `artifacts/codearts-ops-service-capability-probe.json`

## STEP 4 — RUN THE TARGET SERVICE'S MODULE

**Classification: ASSISTED**

**Objective**: Execute the per-service Discover → (Plan) → Execute → Verify sequence documented in `# Per-service operations`, using ONLY that service's confirmed (or freshly-probed) operations.

**Inputs**: project_id, action, service-specific identifiers.

**Preconditions**: Steps 1-3 completed.

Consult the dedicated file for the target service:

- `repo` → see `# Per-service operations` → CodeArts Repo (service: `CodeArtsRepo`)
- `check` → see `# Per-service operations` → CodeArts Check (service: `CodeCheck`)
- `build` → see `# Per-service operations` → CodeArts Build (service: `CodeArtsBuild`) — the most gap-affected module; see `GAP-CODEARTS-OPS-103`
- `artifact` → see `# Per-service operations` → CodeArts Artifact (service: `CodeArtsArtifact`)
- `testplan` → see `# Per-service operations` → CodeArts TestPlan (service: `CloudTest`)
- `deploy` → see `# Per-service operations` → CodeArts Deploy (service: `CodeArtsDeploy`)
- `pipeline` → see `# Per-service operations` → CodeArts Pipeline (service: `CodeArtsPipeline`)

If action is `discover`: run only the discovery command from that file; stop after recording results.

If action is `create`: request explicit approval, then run the create command from that file (only if it is a confirmed operation, or was freshly probed successfully), then immediately run the verify command.

If action is `verify`: run the verify command from that file directly (useful for re-checking a resource created in a previous run).

**Approval requirement**: EXPLICIT for any create/write action; none for discover/verify.

**Verification**: Per the target service's file.

**Expected result**: The requested resource state confirmed.

**Failure action**: STOP on any error; do not retry with a different, invented command; do not fall back to a different service without a new approval and a documented reason (Build → Pipeline is the one pre-approved fallback pattern, and even that still needs explicit approval for the Pipeline run itself).

**Evidence artifact**: `artifacts/codearts-ops-execution-result.json`, `artifacts/codearts-ops-verification.json`

## STEP 5 — CLOSURE

**Classification: AUTOMATED**

**Objective**: Generate final summary, evidence, and follow-up actions.

**Inputs**: All artifacts from Steps 1-4.

**Preconditions**: All previous steps completed.

Generate:
- Final summary (target_service, operation used, action, region, project_id, result)
- Capability probe result for the target service (so future runs against the same tenant/CLI version can skip re-probing confirmed operations, but MUST re-probe any operation still marked unconfirmed)
- Warnings (for example, if a known gap was encountered and routed to the console/Pipeline fallback)
- Explicit statement that no other of the seven services, and no CodeArts Req project data, was touched during this run
- Follow-up actions
- Unresolved risks

Do NOT perform any rollback/delete action automatically in this closure step.

**Expected result**: Complete closure report.

**Evidence artifact**: `artifacts/codearts-ops-final-report.md`

# Per-service operations

Only the section for the request's `target_service` is used; the seven sections below are independent of each other.

### CodeArts Repo (service name: `CodeArtsRepo`, formerly `CodeHub`)

Git-based code hosting: repositories, branches, members, SSH keys.

Confirmed operations (full parameter table verified against the operation's own API Reference page):

| Operation | HTTP method / path | Key parameters |
|---|---|---|
| `CreateRepository` | `POST /v1/repositories` | project_uuid (required), name (required), visibility_level, template_id, description, import_members, import_url, gitignore_id, license_id, enable_readme, caller |
| `ListUserAllRepositories` | `GET /v2/projects/repositories` | page_index, page_size, search |
| `ShowRepository` | `GET /v4/repositories/{repository_id}` | repository_id (path) |

Operations that exist but were not independently parameter-verified: `AddSshKey`, `ListSshKeys`, `ListRepoMembers`, `AddRepoMembers`, `CreateNewBranch`, `ListBranchesByRepositoryId`, `DeleteRepository`. Probe these with `hcloud CodeArtsRepo <OPERATION> --help` before using them in a write step.

**Discover:**
```bash
hcloud CodeArtsRepo --help
hcloud CodeArtsRepo ListUserAllRepositories --cli-region=<REGION> --page_index=1 --page_size=100 --search="<REPO_NAME>"
```

**Create/write** (`CreateRepository`) — requires EXPLICIT approval:
```bash
hcloud CodeArtsRepo CreateRepository --cli-region=<REGION> --project_uuid="<PROJECT_ID>" --name="<REPO_NAME>" --visibility_level=0
```

**Verify:**
```bash
hcloud CodeArtsRepo ShowRepository --cli-region=<REGION> --repository_id="<REPOSITORY_UUID>"
```

Known gap (`GAP-CODEARTS-OPS-101`): AddSshKey, ListSshKeys, ListRepoMembers, AddRepoMembers, CreateNewBranch, ListBranchesByRepositoryId, and DeleteRepository are confirmed to exist for CodeArtsRepo (listed by hcloud CodeArtsRepo --help / API Explorer), but their exact parameter sets were not independently checked against each operation's own API Reference page during authoring.

Out of scope for this service module: Repository content operations (git clone/push/pull, file edits, merge requests) are performed with the git CLI or the console, never with hcloud; hcloud only manages repository resources (create/list/show/branches/members/keys).

### CodeArts Check (service name: `CodeCheck`, formerly `CodeCheck (this is still the current KooCLI/API Explorer service name)`)

Static and security code-quality checks on a repository.

Confirmed operations (full parameter table verified against the operation's own API Reference page):

| Operation | HTTP method / path | Key parameters |
|---|---|---|
| `ShowTaskListByProjectIdV2` | `GET /v2/{project_id}/tasks` | project_id (path), offset, limit |
| `ShowTaskCmetrics` | `GET /v2/{project_id}/tasks/{task_id}/metrics-summary` | project_id (path), task_id (path) |
| `ShowTaskDetailV2` | `GET /v2/tasks/{task_id}/defects-summary` | task_id (path) |
| `ShowTaskDefectsV2` | `GET /v2/tasks/{task_id}/defects-detail` | task_id (path), status_ids |

Operations that exist but were not independently parameter-verified: `StopTaskByIdV2`. Probe these with `hcloud CodeCheck <OPERATION> --help` before using them in a write step.

**Discover:**
```bash
hcloud CodeCheck --help
hcloud CodeCheck ShowTaskListByProjectIdV2 --cli-region=<REGION> --project_id="<PROJECT_ID>" --offset=0 --limit=10
```

**Create/write**: no confirmed operation (GAP-CODEARTS-OPS-102). Do not invent one.

**Verify:**
```bash
hcloud CodeCheck ShowTaskCmetrics --cli-region=<REGION> --project_id="<PROJECT_ID>" --task_id="<TASK_ID>"
```

Known gap (`GAP-CODEARTS-OPS-102`): No operation to create or trigger-run a check task was found in the public CodeArts Check API Reference under the CodeCheck service; check tasks are created and started from the CodeArts Check console or from a CodeArts Pipeline job. This skill only lists tasks and reads their metrics/issues via hcloud; it does not create or start check tasks.

Out of scope for this service module: Rule configuration, quality gates, and check-profile management are not covered; only read operations on tasks already created elsewhere.

### CodeArts Build (service name: `CodeArtsBuild`, formerly `CodeCI / CloudBuildEx`)

Compiles source code into build artifacts and packages configuration/resource files.

Confirmed operations (full parameter table verified against the operation's own API Reference page):

| Operation | HTTP method / path | Key parameters |
|---|---|---|
| `ShowJobConfigDiff` | `GET /v1/job/{job_id}/diff` | job_id (path), original_no, revisedl_no |

Operations that exist but were not independently parameter-verified: none. Probe these with `hcloud CodeArtsBuild <OPERATION> --help` before using them in a write step.

**Discover:**
```bash
hcloud CodeArtsBuild --help
hcloud CodeArtsBuild ShowJobConfigDiff --cli-region=<REGION> --job_id="<JOB_ID>" --original_no=1 --revisedl_no=2
```

**Create/write**: no confirmed operation (GAP-CODEARTS-OPS-103). Do not invent one.

**Verify:**
```bash
hcloud CodeArtsBuild ShowJobConfigDiff --cli-region=<REGION> --job_id="<JOB_ID>" --original_no=1 --revisedl_no=2
```

Known gap (`GAP-CODEARTS-OPS-103`): This is this skill's most significant capability gap, analogous to CreateProjectV4 in the companion CodeArts Req skill. The legacy build-task operations (CreateBuildJob, UpdateBuildJob, ListDeployTasks-style job listing) live under the older 'CodeCI' API namespace and several are explicitly marked deprecated or 'Out-of-date'/'Unavailable Soon' in their own API Reference pages. The current, non-deprecated CodeArtsBuild namespace only had ShowJobConfigDiff confirmed with a full parameter table at authoring time. No create-build-task or run/start-build-task operation could be confirmed under the current CodeArtsBuild service name. Before relying on any create/run/list build operation, this skill MUST probe `hcloud CodeArtsBuild --help` live and cross-check the operation's own API Explorer 'CLI Examples' tab; if the operation is missing, deprecated, or its parameters cannot be confirmed, use the CodeArts Build console, or drive the build through a CodeArts Pipeline job (see the pipeline module) instead of guessing a command.

Out of scope for this service module: Build task creation/editing, build templates, and build-environment configuration are not automated by this skill; only configuration-diff inspection of an existing task is confirmed.

### CodeArts Artifact (service name: `CodeArtsArtifact`, formerly `CloudArtifact`)

Manages build-artifact package repositories (Maven, npm, PyPI, NuGet, generic, Docker, and more).

Confirmed operations (full parameter table verified against the operation's own API Reference page):

| Operation | HTTP method / path | Key parameters |
|---|---|---|
| `ListAllRepositories` | `GET /cloudartifact/v5/{tenant_id}/{project_id}/repositories` | tenant_id (path), project_id (path), in_project, format, page_no, page_size, qname, format_list, is_need_paging |
| `ShowMavenInfo` | `GET /cloudartifact/v5/maven/info` | project_id, policy, access, default, ids |
| `ShowFileTree` | `GET /cloudartifact/v5/{tenant_id}/{project_id}/{repo_name}/file-tree` | tenant_id (path), project_id (path), repo_name (path), path, is_recycle_bin |

Operations that exist but were not independently parameter-verified: `CreateArtifactory`, `DeleteRepository`, `ListChildProxyRepositoriesList`, `ListArtifactoryComponent`. Probe these with `hcloud CodeArtsArtifact <OPERATION> --help` before using them in a write step.

**Discover:**
```bash
hcloud CodeArtsArtifact --help
hcloud CodeArtsArtifact ListAllRepositories --cli-region=<REGION> --project_id="<PROJECT_ID>" --in_project=true --page_no=1 --page_size=20 --is_need_paging=true
```

**Create/write**: no confirmed operation (GAP-CODEARTS-OPS-104). Do not invent one.

**Verify:**
```bash
hcloud CodeArtsArtifact ShowMavenInfo --cli-region=<REGION> --project_id="<PROJECT_ID>" --policy=release --access=r
```

Known gap (`GAP-CODEARTS-OPS-104`): CreateArtifactory (creating a non-Maven repository) is confirmed to exist by name (it appears as the documented 'next topic' after DeleteRepository in the Repository Management section) but its full request-body parameter table was not independently fetched/verified during authoring. Probe `hcloud CodeArtsArtifact CreateArtifactory --help` and cross-check the CLI Examples tab before scripting a create call.

Out of scope for this service module: Uploading/downloading actual package files is normally done with the package manager (mvn, npm, pip, etc.) configured against the repository URL, not with hcloud; hcloud only manages the repository resource and metadata.

### CodeArts TestPlan (service name: `CloudTest`, formerly `CloudTest (this is still the current KooCLI/API Explorer service name)`)

Test plan, test case, and execution-tracking management.

Confirmed operations (full parameter table verified against the operation's own API Reference page):

| Operation | HTTP method / path | Key parameters |
|---|---|---|
| `CreateTestCaseInPlan` | `POST /v1/projects/{project_id}/plans/{plan_id}/testcases/batch-add` | project_id (path), plan_id (path), service_id, testcase_id_list |

Operations that exist but were not independently parameter-verified: `ShowPlans`. Probe these with `hcloud CloudTest <OPERATION> --help` before using them in a write step.

**Discover:**
```bash
hcloud CloudTest --help
hcloud CloudTest ShowPlans --cli-region=<REGION> --project_id="<PROJECT_ID>"
```

**Create/write** (`CreateTestCaseInPlan`) — requires EXPLICIT approval:
```bash
hcloud CloudTest CreateTestCaseInPlan --cli-region=<REGION> --project_id="<PROJECT_ID>" --plan_id="<PLAN_ID>" --service_id=<SERVICE_ID> --testcase_id_list=<TESTCASE_ID_ARRAY>
```

**Verify:**
```bash
hcloud CloudTest ShowPlans --cli-region=<REGION> --project_id="<PROJECT_ID>"
```

Known gap (`GAP-CODEARTS-OPS-105`): ShowPlans (listing test plans in a project) is confirmed to exist and to sit immediately before CreateTestCaseInPlan in the Test Plan Management section (GET .../plans, consistent with the sibling path .../plans/{plan_id}/testcases/batch-add), but its own query-parameter table was not independently fetched. In addition, KooCLI's exact CLI syntax for the testcase_id_list ARRAY body parameter of CreateTestCaseInPlan was not observed live; confirm the current array syntax with `hcloud CloudTest CreateTestCaseInPlan --help` or the operation's CLI Examples tab before scripting it, rather than guessing a bracket/comma format.

Out of scope for this service module: Test case authoring/design (manual or automated API test case content) is out of scope; this skill only lists plans and attaches already-existing test case IDs to a plan.

### CodeArts Deploy (service name: `CodeArtsDeploy`, formerly `CloudDeploy`)

Automates deployment of applications to hosts or containers.

Confirmed operations (full parameter table verified against the operation's own API Reference page):

| Operation | HTTP method / path | Key parameters |
|---|---|---|
| `CreateHostCluster` | `POST /v1/resources/host-groups` | name (required), description, project_id (required), os (required), slave_cluster_id, is_proxy_mode |
| `ListEnvironments` | `GET /v1/applications/{application_id}/environments` | application_id (path), project_id |
| `ListEnvironmentHosts` | `GET /v1/applications/{application_id}/environments/{environment_id}/hosts` | application_id (path), environment_id (path), page_index, page_size, key_field |
| `StartDeployTask` | `POST /v2/tasks/{task_id}/start` | task_id (path), params, record_id, trigger_source |

Operations that exist but were not independently parameter-verified: `ListNewHosts`, `ShowDeployTaskDetail`. Probe these with `hcloud CodeArtsDeploy <OPERATION> --help` before using them in a write step.

**Discover:**
```bash
hcloud CodeArtsDeploy --help
hcloud CodeArtsDeploy ListEnvironments --cli-region=<REGION> --application_id="<APPLICATION_ID>" --project_id="<PROJECT_ID>"
```

**Create/write** (`CreateHostCluster`) — requires EXPLICIT approval:
```bash
hcloud CodeArtsDeploy CreateHostCluster --cli-region=<REGION> --project_id="<PROJECT_ID>" --name="<HOST_GROUP_NAME>" --os=linux --is_proxy_mode=1
```

**Verify:**
```bash
hcloud CodeArtsDeploy StartDeployTask --cli-region=<REGION> --task_id="<TASK_ID>" --trigger_source=0
```

Known gap (`GAP-CODEARTS-OPS-106`): The application/task-listing operation ListDeployTasks (GET /v2/{project_id}/tasks/list) is confirmed to exist and confirmed under the CodeArtsDeploy service name, but its own API Reference page explicitly states it 'will not be maintained after September 30, 2024' and directs callers to use ListAllApp instead; ListAllApp's parameters were not independently verified during authoring. Do not use ListDeployTasks for new automation; probe `hcloud CodeArtsDeploy ListAllApp --help` first, and treat deployment-task/application listing as needing live confirmation.

Out of scope for this service module: Application definition, deployment action orchestration (the steps inside a deployment task), and host onboarding into a cluster are configured from the CodeArts Deploy console; this skill creates host clusters, lists environments/hosts, and starts an already-configured deployment task.

### CodeArts Pipeline (service name: `CodeArtsPipeline`, formerly `CloudPipeline`)

Orchestrates CodeArts Check, Build, TestPlan, and Deploy tasks into a single CI/CD workflow.

Confirmed operations (full parameter table verified against the operation's own API Reference page):

| Operation | HTTP method / path | Key parameters |
|---|---|---|
| `CreatePipelineNew` | `POST /v5/{project_id}/api/pipelines` | project_id (path), name (required), description, is_publish, sources, definition |
| `RunPipeline` | `POST /v5/{project_id}/api/pipelines/{pipeline_id}/run` | project_id (path), pipeline_id (path), sources, description, variables, choose_jobs, choose_stages |
| `ShowPipelineRunDetail` | `GET /v5/{project_id}/api/pipelines/{pipeline_id}/pipeline-runs/detail` | project_id (path), pipeline_id (path) |

Operations that exist but were not independently parameter-verified: `ListPipelines`, `ListExecutionsOverview`. Probe these with `hcloud CodeArtsPipeline <OPERATION> --help` before using them in a write step.

**Discover:**
```bash
hcloud CodeArtsPipeline --help
hcloud CodeArtsPipeline ListPipelines --cli-region=<REGION> --project_id="<PROJECT_ID>"
```

**Create/write** (`CreatePipelineNew`) — requires EXPLICIT approval:
```bash
hcloud CodeArtsPipeline CreatePipelineNew --cli-region=<REGION> --project_id="<PROJECT_ID>" --name="<PIPELINE_NAME>"
```

**Verify:**
```bash
hcloud CodeArtsPipeline ShowPipelineRunDetail --cli-region=<REGION> --project_id="<PROJECT_ID>" --pipeline_id="<PIPELINE_ID>"
```

Known gap (`GAP-CODEARTS-OPS-107`): ListPipelines is confirmed to exist (its JSON response shape was observed in the public API Reference example), but its query-parameter table (pagination fields such as offset/limit, and any filters) was not independently fetched during authoring. CreatePipelineNew's 'definition' body field is a large nested JSON structure (stages/jobs/steps) whose full schema was only partially observed via example payloads; do not hand-author a 'definition' value from guesswork — generate it from the console's 'Create Pipeline' / YAML editor, or from a previously exported pipeline, and pass it through unmodified.

Out of scope for this service module: Authoring a pipeline's stage/job graph from scratch via CLI is not covered; this skill lists, runs, and checks the status of pipelines whose definition already exists (created via console, YAML file, or CreatePipelineNew with a definition obtained elsewhere).


# Capability gap handling

When a capability required for a CodeArts Repo/Check/Build/Artifact/TestPlan/Deploy/Pipeline operation is not available or not confirmed:

1. Document the gap with Gap ID, phase (service), and impact (see `# Per-service operations` and the known gaps below)
2. Classify the gap: critical path (blocks the requested action) or optional
3. Evaluate alternatives:
   - Can the step be performed via hcloud CLI after a live `--help` probe? → PROBE_HELP_BEFORE_USE (preferred)
   - Can it only be done manually in the console? → USE_CONSOLE_OR_PIPELINE_FOR_CREATE / USE_MANUAL_CONSOLE_FALLBACK
   - Is there a documented, non-deprecated replacement operation? → AVOID_DEPRECATED_OP_PROBE_REPLACEMENT
   - Can an existing MCP tool accomplish the task? → USE_EXISTING_TOOL (not applicable to any gap in this skill)
   - Is a new MCP needed? → CREATE_NEW_MCP (last resort; not applicable to any gap in this skill)
4. Never auto-activate a generated MCP or invent an undocumented command as a workaround
5. Update the affected service's status in this document's `# Known limitations` section if critical gaps remain

Known capability gaps (see the frontmatter's `metadata` block above, and `# Per-service operations` for each service's specific gap):

- GAP-CODEARTS-OPS-101 (CodeArts Repo): AddSshKey, ListSshKeys, ListRepoMembers, AddRepoMembers, CreateNewBranch, ListBranchesByRepositoryId, and DeleteRepository are confirmed to exist for CodeArtsRepo (listed by hcloud CodeArtsRepo --help / API Explorer), but their exact parameter sets were not independently checked against each operation's own API Reference page during authoring.
- GAP-CODEARTS-OPS-102 (CodeArts Check): No operation to create or trigger-run a check task was found in the public CodeArts Check API Reference under the CodeCheck service; check tasks are created and started from the CodeArts Check console or from a CodeArts Pipeline job. This skill only lists tasks and reads their metrics/issues via hcloud; it does not create or start check tasks.
- GAP-CODEARTS-OPS-103 (CodeArts Build): This is this skill's most significant capability gap, analogous to CreateProjectV4 in the companion CodeArts Req skill. The legacy build-task operations (CreateBuildJob, UpdateBuildJob, ListDeployTasks-style job listing) live under the older 'CodeCI' API namespace and several are explicitly marked deprecated or 'Out-of-date'/'Unavailable Soon' in their own API Reference pages. The current, non-deprecated CodeArtsBuild namespace only had ShowJobConfigDiff confirmed with a full parameter table at authoring time. No create-build-task or run/start-build-task operation could be confirmed under the current CodeArtsBuild service name. Before relying on any create/run/list build operation, this skill MUST probe `hcloud CodeArtsBuild --help` live and cross-check the operation's own API Explorer 'CLI Examples' tab; if the operation is missing, deprecated, or its parameters cannot be confirmed, use the CodeArts Build console, or drive the build through a CodeArts Pipeline job (see the pipeline module) instead of guessing a command.
- GAP-CODEARTS-OPS-104 (CodeArts Artifact): CreateArtifactory (creating a non-Maven repository) is confirmed to exist by name (it appears as the documented 'next topic' after DeleteRepository in the Repository Management section) but its full request-body parameter table was not independently fetched/verified during authoring. Probe `hcloud CodeArtsArtifact CreateArtifactory --help` and cross-check the CLI Examples tab before scripting a create call.
- GAP-CODEARTS-OPS-105 (CodeArts TestPlan): ShowPlans (listing test plans in a project) is confirmed to exist and to sit immediately before CreateTestCaseInPlan in the Test Plan Management section (GET .../plans, consistent with the sibling path .../plans/{plan_id}/testcases/batch-add), but its own query-parameter table was not independently fetched. In addition, KooCLI's exact CLI syntax for the testcase_id_list ARRAY body parameter of CreateTestCaseInPlan was not observed live; confirm the current array syntax with `hcloud CloudTest CreateTestCaseInPlan --help` or the operation's CLI Examples tab before scripting it, rather than guessing a bracket/comma format.
- GAP-CODEARTS-OPS-106 (CodeArts Deploy): The application/task-listing operation ListDeployTasks (GET /v2/{project_id}/tasks/list) is confirmed to exist and confirmed under the CodeArtsDeploy service name, but its own API Reference page explicitly states it 'will not be maintained after September 30, 2024' and directs callers to use ListAllApp instead; ListAllApp's parameters were not independently verified during authoring. Do not use ListDeployTasks for new automation; probe `hcloud CodeArtsDeploy ListAllApp --help` first, and treat deployment-task/application listing as needing live confirmation.
- GAP-CODEARTS-OPS-107 (CodeArts Pipeline): ListPipelines is confirmed to exist (its JSON response shape was observed in the public API Reference example), but its query-parameter table (pagination fields such as offset/limit, and any filters) was not independently fetched during authoring. CreatePipelineNew's 'definition' body field is a large nested JSON structure (stages/jobs/steps) whose full schema was only partially observed via example payloads; do not hand-author a 'definition' value from guesswork — generate it from the console's 'Create Pipeline' / YAML editor, or from a previously exported pipeline, and pass it through unmodified.
- GAP-CODEARTS-OPS-000: No dedicated MCP exists for any of the seven services in this skill's scope; all operations via hcloud CLI. [VERIFIED_FROM_PUBLIC_API_DOCS]
- GAP-CODEARTS-OPS-999: This skill has not been executed against a live hcloud CLI or live tenant for any of the seven services; all CLI syntax is derived from each operation's own public API Reference page, not from `--help` output captured live. [NOT_LIVE_TESTED]

# Output artifacts

- artifacts/codearts-ops-intent.json — Parsed intent (target_service, action, region, project reference)
- artifacts/codearts-ops-auth-discovery.json — Authentication and hcloud version/profile check
- artifacts/codearts-ops-project-resolution.json — Resolved project_id
- artifacts/codearts-ops-service-capability-probe.json — Target service reachability and operation-availability classification
- artifacts/codearts-ops-execution-result.json — Result of the discover/create/verify action executed
- artifacts/codearts-ops-verification.json — Post-action verification (read-back) result
- artifacts/codearts-ops-final-report.md — Closure report

# Troubleshooting

| Symptom | Likely cause | Diagnosis | Resolution |
|---|---|---|---|
| `hcloud: command not found` | KooCLI not installed or not in PATH | `hcloud version` | Install KooCLI per `# Prerequisites` above; add `/usr/local/bin` to PATH |
| Authentication failure | hcloud profile misconfigured | `hcloud configure show --cli-profile=default` | Re-run `hcloud configure init` |
| Region rejected | Region not valid for CodeArts in this tenant | Try a region already confirmed for other CodeArts services in the tenant | Use a confirmed CodeArts region |
| `ListProjectsV4 --search=` returns no match | Project not yet created | N/A (out of this skill's scope) | Use the companion `huawei-codearts-project-design` skill first |
| `hcloud CodeArtsRepo --help` missing an expected operation | Older KooCLI/API Explorer metadata, or the operation genuinely does not exist under this service | Compare against that service's confirmed-operations table in `# Per-service operations` above | Use the console (or, for Build, a CodeArts Pipeline job) instead of inventing a substitute |
| `hcloud CodeCheck --help` missing an expected operation | Older KooCLI/API Explorer metadata, or the operation genuinely does not exist under this service | Compare against that service's confirmed-operations table in `# Per-service operations` above | Use the console (or, for Build, a CodeArts Pipeline job) instead of inventing a substitute |
| `hcloud CodeArtsBuild --help` missing an expected operation | Older KooCLI/API Explorer metadata, or the operation genuinely does not exist under this service | Compare against that service's confirmed-operations table in `# Per-service operations` above | Use the console (or, for Build, a CodeArts Pipeline job) instead of inventing a substitute |
| `hcloud CodeArtsArtifact --help` missing an expected operation | Older KooCLI/API Explorer metadata, or the operation genuinely does not exist under this service | Compare against that service's confirmed-operations table in `# Per-service operations` above | Use the console (or, for Build, a CodeArts Pipeline job) instead of inventing a substitute |
| `hcloud CloudTest --help` missing an expected operation | Older KooCLI/API Explorer metadata, or the operation genuinely does not exist under this service | Compare against that service's confirmed-operations table in `# Per-service operations` above | Use the console (or, for Build, a CodeArts Pipeline job) instead of inventing a substitute |
| `hcloud CodeArtsDeploy --help` missing an expected operation | Older KooCLI/API Explorer metadata, or the operation genuinely does not exist under this service | Compare against that service's confirmed-operations table in `# Per-service operations` above | Use the console (or, for Build, a CodeArts Pipeline job) instead of inventing a substitute |
| `hcloud CodeArtsPipeline --help` missing an expected operation | Older KooCLI/API Explorer metadata, or the operation genuinely does not exist under this service | Compare against that service's confirmed-operations table in `# Per-service operations` above | Use the console (or, for Build, a CodeArts Pipeline job) instead of inventing a substitute |
| A create/write operation is rejected (403/permission) | Tenant lacks the specific CodeArts permission for that service/action | Error message from the call | Request the specific permission from an administrator |
| `CodeArtsBuild` create/run cannot be confirmed at all | Known gap `GAP-CODEARTS-OPS-103` | `hcloud CodeArtsBuild --help` | Use the CodeArts Build console, or run the build via an existing CodeArts Pipeline job |
| Region mismatch between plan and call | `--cli-region` omitted or wrong on a later command | Compare command flags across steps | Ensure every command for the same operation uses the same `--cli-region` |


# Failure handling

- Authentication failure: verify hcloud config, region, IAM permissions. Do not retry with different credentials without operator confirmation.
- Project not resolved: stop; this skill does not create projects.
- Service unreachable / operation missing: cross-check against the target service's confirmed-operations table before assuming a transient error; if genuinely missing, use the console/Pipeline fallback, never an invented command.
- Write operation rejected for a permission reason: report; do not retry with different credentials without operator confirmation.
- Write operation rejected for any other reason: STOP, preserve evidence, report to approval owner; do not retry with a different, invented command.
- Verification failure: report; do not delete, stop, or recreate the resource automatically.

# Recovery procedure

1. If failure during discovery (Steps 2-3): no resource created/modified. Fix authentication/region/service issue and retry from Step 2.
2. If failure during the target service's module (Step 4), discover/verify sub-actions: re-run discovery; no resource was created, retry once the root cause is fixed.
3. If failure during a create/write sub-action: check the error. If authorization-related, request the specific permission (or, for Build, use the console/Pipeline fallback) with a new approval request. If a parameter/name error, correct and retry.
4. If failure during verification: the resource may be in an inconsistent state. Do not delete/stop/recreate it automatically; report and await a decision.
5. Never expand recovery into a different service's module, or into CodeArts Req project data, to compensate for a failure in the target service.

# Rollback

Most operations in this skill are read-only or additive; a symmetric "undo" API does not exist for every action. Never delete or stop a resource automatically after a downstream failure — report and let the approval owner decide. Only use a Delete/Stop-style operation after confirming (via `hcloud <SERVICE_NAME> --help`) that it exists for that service, and only with explicit approval.

**CodeArts Repo:**
```bash
hcloud CodeArtsRepo DeleteRepository --cli-region=<REGION> --repository_id="<REPOSITORY_UUID>"
```
Listed for CodeArtsRepo but not independently parameter-verified (`GAP-CODEARTS-OPS-101`); probe `--help` first.

**CodeArts Check** and **CodeArts Build**: read-only in this skill; nothing to roll back.

**CodeArts Artifact:**
```bash
hcloud CodeArtsArtifact DeleteRepository --cli-region=<REGION> --project_id="<PROJECT_ID>" --repo_name="<REPOSITORY_NAME>"
```
Listed for CodeArtsArtifact but not independently parameter-verified; probe `--help` first.

**CodeArts TestPlan**: no remove-test-case-from-plan operation was confirmed; report to the approval owner and remove cases from the console instead.

**CodeArts Deploy**: a deployment started with `StartDeployTask` cannot be rolled back through this skill; the correction is a new, separately approved deployment of a previous version.

**CodeArts Pipeline**: a completed run cannot be undone. To stop an in-progress run, first probe `hcloud CodeArtsPipeline --help` to confirm whether a stop/cancel operation exists — do not assume it exists or guess its name.

Do NOT delete or stop any resource automatically after a failure in any phase. Do NOT invent a Delete/Stop/Cancel command not confirmed to exist for that specific service. Do NOT treat a rollback in one service as a substitute for fixing the root cause in another. Do NOT touch CodeArts Req project data as part of any rollback in this skill.

# Evidence and traceability

- All hcloud CLI commands logged with timestamps
- project_id and every service-specific resource identifier recorded in artifacts
- Approval decisions recorded with approver identity and timestamp
- Per-service capability probe results recorded and reusable across runs against the same tenant/CLI version (re-probe if either changes, and always re-probe any operation still marked unconfirmed for that service)
- No secrets in any artifact

# Known limitations

- No dedicated MCP exists for any of the seven services in this skill's scope [VERIFIED_FROM_PUBLIC_API_DOCS]
- CodeArts Build's create/run capability is unresolved under the current `CodeArtsBuild` service name; only configuration-diff inspection (`ShowJobConfigDiff`) is confirmed [NOT_LIVE_TESTED] [GAP-CODEARTS-OPS-103]
- CodeArts Repo: AddSshKey, ListSshKeys, ListRepoMembers, AddRepoMembers, CreateNewBranch, ListBranchesByRepositoryId, and DeleteRepository are confirmed to exist for CodeArtsRepo (listed by hcloud CodeArtsRepo --help / API Explorer), but their exact parameter sets were not independently checked against each operation's own API Reference page during authoring.
- CodeArts Check: No operation to create or trigger-run a check task was found in the public CodeArts Check API Reference under the CodeCheck service; check tasks are created and started from the CodeArts Check console or from a CodeArts Pipeline job. This skill only lists tasks and reads their metrics/issues via hcloud; it does not create or start check tasks.
- CodeArts Artifact: CreateArtifactory (creating a non-Maven repository) is confirmed to exist by name (it appears as the documented 'next topic' after DeleteRepository in the Repository Management section) but its full request-body parameter table was not independently fetched/verified during authoring. Probe `hcloud CodeArtsArtifact CreateArtifactory --help` and cross-check the CLI Examples tab before scripting a create call.
- CodeArts TestPlan: ShowPlans (listing test plans in a project) is confirmed to exist and to sit immediately before CreateTestCaseInPlan in the Test Plan Management section (GET .../plans, consistent with the sibling path .../plans/{plan_id}/testcases/batch-add), but its own query-parameter table was not independently fetched. In addition, KooCLI's exact CLI syntax for the testcase_id_list ARRAY body parameter of CreateTestCaseInPlan was not observed live; confirm the current array syntax with `hcloud CloudTest CreateTestCaseInPlan --help` or the operation's CLI Examples tab before scripting it, rather than guessing a bracket/comma format.
- CodeArts Deploy: The application/task-listing operation ListDeployTasks (GET /v2/{project_id}/tasks/list) is confirmed to exist and confirmed under the CodeArtsDeploy service name, but its own API Reference page explicitly states it 'will not be maintained after September 30, 2024' and directs callers to use ListAllApp instead; ListAllApp's parameters were not independently verified during authoring. Do not use ListDeployTasks for new automation; probe `hcloud CodeArtsDeploy ListAllApp --help` first, and treat deployment-task/application listing as needing live confirmation.
- CodeArts Pipeline: ListPipelines is confirmed to exist (its JSON response shape was observed in the public API Reference example), but its query-parameter table (pagination fields such as offset/limit, and any filters) was not independently fetched during authoring. CreatePipelineNew's 'definition' body field is a large nested JSON structure (stages/jobs/steps) whose full schema was only partially observed via example payloads; do not hand-author a 'definition' value from guesswork — generate it from the console's 'Create Pipeline' / YAML editor, or from a previously exported pipeline, and pass it through unmodified.
- This skill's scope explicitly excludes CodeArts Req / ProjectMan project planning and creation
- No live hcloud CLI or tenant test was performed during authoring for any of the seven services

# Status justification

Status: READY_WITH_WARNINGS

Evidence:
- CodeArts Repo (`CodeArtsRepo`): `CreateRepository`, `ListUserAllRepositories`, `ShowRepository` confirmed with a full parameter table from the operation's own public API Reference page; `AddSshKey`, `ListSshKeys`, `ListRepoMembers`, `AddRepoMembers`, `CreateNewBranch`, `ListBranchesByRepositoryId`, `DeleteRepository` listed/known to exist but not independently parameter-verified. [VERIFIED_FROM_PUBLIC_API_DOCS]
- CodeArts Check (`CodeCheck`): `ShowTaskListByProjectIdV2`, `ShowTaskCmetrics`, `ShowTaskDetailV2`, `ShowTaskDefectsV2` confirmed with a full parameter table from the operation's own public API Reference page; `StopTaskByIdV2` listed/known to exist but not independently parameter-verified. [VERIFIED_FROM_PUBLIC_API_DOCS]
- CodeArts Build (`CodeArtsBuild`): `ShowJobConfigDiff` confirmed with a full parameter table from the operation's own public API Reference page; no further operations listed/known to exist but not independently parameter-verified. [VERIFIED_FROM_PUBLIC_API_DOCS]
- CodeArts Artifact (`CodeArtsArtifact`): `ListAllRepositories`, `ShowMavenInfo`, `ShowFileTree` confirmed with a full parameter table from the operation's own public API Reference page; `CreateArtifactory`, `DeleteRepository`, `ListChildProxyRepositoriesList`, `ListArtifactoryComponent` listed/known to exist but not independently parameter-verified. [VERIFIED_FROM_PUBLIC_API_DOCS]
- CodeArts TestPlan (`CloudTest`): `CreateTestCaseInPlan` confirmed with a full parameter table from the operation's own public API Reference page; `ShowPlans` listed/known to exist but not independently parameter-verified. [VERIFIED_FROM_PUBLIC_API_DOCS]
- CodeArts Deploy (`CodeArtsDeploy`): `CreateHostCluster`, `ListEnvironments`, `ListEnvironmentHosts`, `StartDeployTask` confirmed with a full parameter table from the operation's own public API Reference page; `ListNewHosts`, `ShowDeployTaskDetail` listed/known to exist but not independently parameter-verified. [VERIFIED_FROM_PUBLIC_API_DOCS]
- CodeArts Pipeline (`CodeArtsPipeline`): `CreatePipelineNew`, `RunPipeline`, `ShowPipelineRunDetail` confirmed with a full parameter table from the operation's own public API Reference page; `ListPipelines`, `ListExecutionsOverview` listed/known to exist but not independently parameter-verified. [VERIFIED_FROM_PUBLIC_API_DOCS]
- No dedicated MCP exists for any of the seven services [VERIFIED_FROM_PUBLIC_API_DOCS]
- All write operations require explicit approval [INFERRED]
- No cloud-side or CLI-side live test was executed for any of the seven services; this authoring environment had web-search/fetch access to public documentation only, not a live hcloud CLI install or Huawei Cloud credentials [NOT_LIVE_TESTED]
- Because of the above, this skill mandates a live per-operation probe (`hcloud <SERVICE_NAME> <OPERATION> --help`) before any workflow instance relies on an operation outside the confirmed-operations table for its target service, and documents an explicit fallback (console or, for Build, CodeArts Pipeline) for the one service (CodeArts Build) where no create/run operation could be confirmed at all
