---
name: huawei-codearts-project-design
version: 1.0.0
description: Design and create Huawei Cloud CodeArts Req (ProjectMan) projects — parse intent, discover, validate naming, create or reuse the project, and configure its basic design (description, members) using hcloud CLI, with a documented manual fallback.
category: provisioning
risk_level: medium
status: READY_WITH_WARNINGS
requires_explicit_approval: true
license: Apache-2.0
compatibility:
  - OpenCode
  - Hermes
metadata:
  domain: DevOps-Foundation
  family: Project-Provisioning
  service: CodeArts-Req-ProjectMan
  risk_level: medium
  status: READY_WITH_WARNINGS
  create_operation_verification: SDK_SOURCE_VERIFIED_NOT_LIVE_TESTED
---

# Purpose

Design and create a Huawei Cloud CodeArts Req (ProjectMan) project — resolve inputs, discover existing projects, validate the project name, create (or reuse) the project, and configure its basic design (description, enterprise project, members) — using hcloud CLI (KooCLI) as the primary mechanism, with a documented manual console fallback when CLI creation is not available for the tenant.

# Supported scenario

- Source: design intent (project name, project type, optional description/members)
- Target: a new (or reused) CodeArts Req project, fully identified by project_id
- Mechanism: ProjectMan v4 REST API called through hcloud CLI, `CreateProjectV4` (or manual console creation as fallback) + `UpdateProjectV4` + `AddMemberV4`
- Storage: none (this skill does not touch code repositories, artifacts, or backups)
- Topology: single-region project creation and configuration

# When to use this skill

- Creating a new CodeArts Req project (Scrum, Kanban/xboard, Normal/basic, or Phoenix type)
- Validating whether a desired project name is available before creating it
- Reusing an existing project instead of creating a duplicate
- Updating a project's name or description after creation (design phase)
- Adding members and roles to a project during its design/setup phase
- Auditing what CodeArts Req projects exist in a tenant/region

# When not to use this skill

- Creating, cloning, or importing CodeArts Repo repositories (use a dedicated CodeArts Repo skill)
- Configuring CodeArts Build, Check, Deploy, Pipeline, or Release (out of scope; use dedicated skills)
- Managing work items, iterations, sprints, or Wiki content inside an existing project (use a CodeArts Req work-item-management skill)
- Enterprise Project (EPS) creation itself — `enterprise_id` here only associates an existing enterprise project; creating one is a separate IAM/EPS operation
- When hcloud CLI is not available and cannot be installed, and the manual console path is also not permitted

# Required inputs

- project_name
- project_type (scrum, xboard, basic, or phoenix)
- source_region
- approval_owner

# Optional inputs

- description
- enterprise_id (existing enterprise project to bind the project to)
- template_id (an existing custom project template id, if the tenant has one configured)
- members_to_add (list of {user_id, domain_id, role_id})
- existing_project_reuse_allowed (boolean; default false — never silently reuse without confirming)

# Required MCPs

None. All ProjectMan (CodeArts Req) operations are performed via hcloud CLI.

# Optional MCPs

- huaweicloud-ticket (only to open a support ticket if the CreateProjectV4 capability probe fails and manual escalation is desired)

# Tool selection policy

- Use hcloud CLI for ALL ProjectMan (CodeArts Req) operations: discovery, name validation, creation, update, member management
- Never use huaweicloud-deploy / GenerateTerraformFromArchitecture to create CodeArts projects — CodeArts Req is not a Terraform-managed resource in that MCP
- Never invent a `hcloud CodeArts ...` command; the KooCLI service name for this API family is `ProjectMan`, not `CodeArts`
- Never assume `CreateProjectV4` is available without probing it first for the active hcloud CLI installation and tenant (see Capability gap handling)
- Use huaweicloud-ticket only for support escalation, never to substitute a missing capability with an invented command

# Safety and approval gates

1. Project creation (`CreateProjectV4`, or the manual console equivalent) requires explicit approval
2. Reusing an existing project instead of creating a new one requires explicit confirmation from the approval owner
3. Updating project name/description (`UpdateProjectV4`) requires explicit approval
4. Adding a member to the project (`AddMemberV4`) requires explicit approval
5. Deleting a project (`DeleteProjectV4`) is out of scope for this skill's normal workflow; only perform it as an explicit, separately approved rollback action (see `# Rollback` below), never as part of normal design/creation

# Rules

1. CodeArts Req (ProjectMan) is exposed through hcloud CLI under the service name `ProjectMan`; there is no `CodeArts` service name and no dedicated CodeArts MCP. [VERIFIED_FROM_PUBLIC_API_DOCS]

2. `CreateProjectV4` (`POST /v4/project`, note the singular path) exists in the officially released Huawei Cloud ProjectMan SDK source code, with request body fields `project_name` (required), `project_type` (required: `scrum`, `xboard`, `basic`, `phoenix`), and optional `description`, `source`, `enterprise_id`, `template_id`. It is **not** listed in the public CodeArts Req API Reference "Project Information" index at the time of this verification. Treat its availability through KooCLI as a capability that MUST be probed live before use, not assumed. [VERIFIED_FROM_SDK_SOURCE] [NOT_IN_PUBLIC_DOCS]

3. If the `CreateProjectV4` probe fails (operation not present for the installed KooCLI version, or the API call is rejected/forbidden), fall back to the documented manual console procedure: CodeArts console → "Create Project" → select type → enter the validated name. Do not invent an alternative CLI command to work around the gap. [INFERRED]

4. `ProjectMan` publishes its own regional endpoints, independent from other Huawei Cloud services. Confirmed regions: `cn-north-4`, `cn-north-1`, `cn-east-2`, `cn-south-1`, `cn-southwest-2`, `cn-east-3`, `ap-southeast-3`, `la-north-2`, `sa-brazil-1`. Do not assume a region used for another service (for example `ap-southeast-1`) is also valid for ProjectMan; verify against this list or a fresh region/endpoint lookup first. [VERIFIED_FROM_SDK_SOURCE] [REGION_DEPENDENT]

5. DISCOVER BEFORE CREATE: always run `CheckProjectNameV4` and `ListProjectsV4` (filtered by `search`) before creating a project. Never hardcode `project_id`, `project_num_id`, `domain_id`, `user_id`, `template_id`, or `enterprise_id`; resolve them via read operations. [VERIFIED_FROM_PUBLIC_API_DOCS]

6. Project names are unique at the platform level, not only within the caller's account; `CheckProjectNameV4` returning `exist: true` does not necessarily mean the project belongs to the current tenant. [INFERRED]

7. There is no discovered operation to list "project creation templates" globally; `ListTemplates` requires an existing `project_id` and returns work-item templates for that project, not templates usable in `CreateProjectV4.template_id`. Treat `template_id` as optional and only use it if the approval owner supplies a known, already-verified value. [VERIFIED_FROM_SDK_SOURCE] [INFERRED]

8. VERIFY AFTER EVERY WRITE: `CreateProjectV4` (or manual creation) must be followed by `ListProjectsV4`/`ShowProjectInfoV4`; `UpdateProjectV4` must be followed by `ShowProjectInfoV4`; `AddMemberV4` must be followed by `ListProjectMembersV4`. [VERIFIED_FROM_PUBLIC_API_DOCS]

9. Every write operation (`CreateProjectV4`, `UpdateProjectV4`, `AddMemberV4`, `DeleteProjectV4`) requires explicit approval before execution. [INFERRED]

10. This skill's scope ends at project design/creation and basic configuration (name, description, enterprise project, members). Do not extend the workflow into CodeArts Repo, Build, Check, Deploy, Pipeline, or Release; those require separate skills. [INFERRED] (explicit scope boundary requested when this skill was authored)

11. Never include secrets (AK, SK, tokens, passwords) in commands, examples, files, or logs; use the credentials already configured in the local hcloud profile. [INFERRED]

12. This skill was authored and verified from the official public CodeArts Req API Reference and the official released ProjectMan SDK source code. It was **not** executed against a live hcloud CLI installation or a live Huawei Cloud tenant (no cloud network access / credentials were available at authoring time). The first real use of this skill in any environment MUST start with the live capability probe in Step 4 before relying on `CreateProjectV4`. [NOT_LIVE_TESTED]

# Prerequisites

| Tool or resource | Required | Purpose | Verification |
|---|---:|---|---|
| hcloud CLI (KooCLI) | Yes | All ProjectMan operations | `hcloud version` |
| Huawei Cloud authentication (AK/SK) | Yes | API access | `hcloud configure show --cli-profile=default` |
| Target region (ProjectMan-supported) | Yes | Project region/endpoint | See Rule 4 region list |
| CodeArts Req project-creation permission | Yes | Ability to create a project | Confirmed only by a successful create attempt or console check |
| Approval owner | Yes | Authorizes write operations | Specified in intent |
| Existing enterprise project (if `enterprise_id` used) | No | Bind project to an enterprise project | Enterprise Management (EPS) console/API |
| huaweicloud-ticket MCP | No | Support escalation if capability gap blocks creation | MCP availability check |

# Workflow

## STEP 1 — PARSE INTENT

**Classification: AUTOMATED**

**Objective**: Extract and validate all required and optional inputs for the project design/creation request.

**Inputs**: User request specifying project name, project type, region, description, enterprise project, template, members, approval owner.

**Preconditions**: None.

**Command**: None (parsing logic).

**Approval requirement**: None.

**Verification**: Confirm all required fields are present and `project_type` is one of `scrum`, `xboard`, `basic`, `phoenix`.

**Expected result**: Complete intent object.

**Failure action**: If critical information is missing or `project_type` is invalid, STOP and request clarification. Do not invent values or guess a project type.

**Evidence artifact**: `artifacts/codearts-intent.json`

Extract:
- project_name
- project_type
- source_region
- description
- enterprise_id
- template_id
- members_to_add
- existing_project_reuse_allowed
- approval_owner

## STEP 2 — DISCOVER AUTHENTICATION, REGION AND SERVICE

**Classification: ASSISTED**

**Objective**: Verify hcloud CLI is installed and configured, confirm the region is valid for ProjectMan, and confirm the ProjectMan service responds.

**Inputs**: source_region from intent.

**Preconditions**: hcloud CLI installed (see `# Prerequisites` above).

**Commands** (read-only):

```bash
hcloud version
hcloud configure show --cli-profile=default
hcloud ProjectMan --help
hcloud ProjectMan ListProjectsV4 --cli-region=<SOURCE_REGION> --offset=0 --limit=1
```

**Approval requirement**: None.

**Verification**: Confirm `hcloud version` returns a version, the profile shows a region and AK configured, `ProjectMan --help` lists operations, and `ListProjectsV4` returns a response (even an empty list) rather than an auth/region error.

**Expected result**: Authentication valid, region accepted by ProjectMan, service reachable.

**Failure action**: STOP. Report authentication, region, or connectivity error. If the region is rejected, cross-check against the confirmed region list in Rule 4 before assuming a transient failure.

**Evidence artifact**: `artifacts/codearts-auth-discovery.json`

## STEP 3 — DISCOVER EXISTING PROJECTS AND VALIDATE NAME

**Classification: ASSISTED**

**Objective**: Apply DISCOVER BEFORE CREATE — check whether a project with this name already exists, and catalog similarly named projects.

**Inputs**: project_name, source_region.

**Preconditions**: Step 2 completed successfully.

**Commands** (read-only):

```bash
hcloud ProjectMan CheckProjectNameV4 --cli-region=<SOURCE_REGION> --project_name="<PROJECT_NAME>"
hcloud ProjectMan ListProjectsV4 --cli-region=<SOURCE_REGION> --offset=0 --limit=10 --search="<PROJECT_NAME>"
```

**Approval requirement**: None.

**Verification**: Record `exist: true|false`. If `true` and a matching project is visible in the current tenant's `ListProjectsV4` results, present the reuse decision to the approval owner instead of creating a duplicate.

**Expected result**: Name-availability decision made; if reuse is chosen, `project_id` resolved from `ListProjectsV4` and the workflow jumps to Step 8 (skip creation).

**Failure action**: If `exist: true` but no matching project appears in this tenant's list, STOP and inform the approval owner the name is taken platform-wide by another tenant; request a different name. Do not guess a new name automatically.

**Evidence artifact**: `artifacts/codearts-existing-projects.json`

## STEP 4 — PROBE CREATE-PROJECT CAPABILITY

**Classification: ASSISTED**

**Objective**: Determine, for the installed KooCLI version and the authenticated tenant, whether `CreateProjectV4` is actually available before relying on it (see Rule 2).

**Inputs**: None beyond an authenticated hcloud profile.

**Preconditions**: Step 2 completed successfully.

**Commands** (read-only / non-mutating):

```bash
hcloud ProjectMan CreateProjectV4 --help
```

**Approval requirement**: None (this is a capability probe, not an execution).

**Verification**:
- If the command prints parameter help for `CreateProjectV4` (accepting `project_name`, `project_type`, etc.): classify capability as `AVAILABLE`.
- If the command errors with "operation not found" / "unknown operation" or equivalent: classify capability as `NOT_AVAILABLE_IN_CLI`.
- If help is shown but a later real call in Step 6 is rejected with a permissions/authorization error: classify capability as `NOT_AVAILABLE_FOR_TENANT`.

**Expected result**: A documented capability classification that determines whether Step 6 uses Path A (CLI) or Path B (manual console).

**Failure action**: If the probe cannot be run at all (for example, `hcloud ProjectMan --help` in Step 2 did not list `CreateProjectV4` among available operations), classify as `NOT_AVAILABLE_IN_CLI` and proceed directly to planning the manual fallback. Do not retry with a different, invented operation name.

**Evidence artifact**: `artifacts/codearts-create-capability-probe.json`

## STEP 5 — PLAN PROJECT

**Classification: AUTOMATED**

**Objective**: Build a project plan documenting name, type, description, enterprise/template association, region, chosen creation path (CLI or manual), and reuse decision.

**Inputs**: Intent, existing-projects discovery, capability probe result.

**Preconditions**: Steps 1-4 completed.

**Command**: None (plan generation logic).

**Approval requirement**: None (plan only, no execution).

**Verification**: Plan contains all required fields and an explicit creation path.

**Expected result**: Project plan document ready for review.

**Failure action**: STOP. Report planning error.

**Evidence artifact**: `artifacts/codearts-project-plan.md`

Plan includes:
- project_name (validated available or reuse target)
- project_type
- description
- enterprise_id / template_id (if supplied)
- region
- creation_path: `CLI` or `MANUAL_CONSOLE`
- reuse_decision: `CREATE_NEW` or `REUSE_EXISTING`

## STEP 6 — CREATE OR REUSE PROJECT

**Classification: ASSISTED**

**Objective**: Create the project (Path A or Path B per the plan) or confirm reuse of an existing one.

**Inputs**: Project plan, approval.

**Preconditions**: Step 5 plan approved by the approval owner.

If reusing (`reuse_decision: REUSE_EXISTING`):
- Re-verify the existing project's state with `ShowProjectInfoV4` (see Step 7). Do not create.

If creating and `creation_path: CLI` (capability probe was `AVAILABLE`):

- **Approval requirement**: EXPLICIT. Request approval before creation.
- **Command**:

```bash
hcloud ProjectMan CreateProjectV4 --cli-region=<SOURCE_REGION> \
  --project_name="<PROJECT_NAME>" \
  --project_type="<PROJECT_TYPE>" \
  --description="<DESCRIPTION>"
```

Add `--enterprise_id="<ENTERPRISE_ID>"` and/or `--template_id=<TEMPLATE_ID>` only if the approval owner supplied verified values (Rule 7).

If the call fails with an authorization/forbidden error despite the probe succeeding: reclassify capability as `NOT_AVAILABLE_FOR_TENANT`, update the probe artifact, and fall back to Path B in the same step (do not silently retry).

If creating and `creation_path: MANUAL_CONSOLE` (capability probe was `NOT_AVAILABLE_IN_CLI` or `NOT_AVAILABLE_FOR_TENANT`):

- **Approval requirement**: EXPLICIT. Request approval before creation.
- **Manual procedure** (present to a human operator; this skill does not automate console clicks):
  1. Sign in to the Huawei Cloud console and open CodeArts.
  2. Click "Create Project".
  3. Select the project type equivalent to `<PROJECT_TYPE>` (Scrum, Kanban, or Normal).
  4. Enter `<PROJECT_NAME>` (already validated as available in Step 3).
  5. Confirm creation.

**Expected result**: Project created (or reuse confirmed), pending ID resolution in Step 7.

**Failure action**: STOP. Preserve error evidence. Do not retry with a different or invented command; if Path A fails for a reason other than authorization, report and await a decision instead of auto-falling back.

**Evidence artifact**: `artifacts/codearts-project-result.json`

## STEP 7 — VERIFY PROJECT CREATED

**Classification: ASSISTED**

**Objective**: Resolve `project_id` and confirm the project exists with the expected attributes, regardless of which path created it.

**Inputs**: project_name, source_region.

**Preconditions**: Step 6 completed (creation, reuse, or manual creation confirmed by the human operator).

**Commands** (read-only):

```bash
hcloud ProjectMan ListProjectsV4 --cli-region=<SOURCE_REGION> --offset=0 --limit=10 --search="<PROJECT_NAME>"
hcloud ProjectMan ShowProjectInfoV4 --cli-region=<SOURCE_REGION> --project_id="<PROJECT_ID>"
```

**Approval requirement**: None.

**Verification**: Confirm exactly one project matches `<PROJECT_NAME>` (reject ambiguous multiple matches — if the name was reused across regions or renamed concurrently, escalate), and that `project_type` and `description` match the plan.

**Expected result**: `project_id` resolved and validated.

**Failure action**: STOP. If zero matches, the manual creation (Path B) may not have completed; ask the human operator to confirm. If multiple matches, present all and let the approval owner pick.

**Evidence artifact**: `artifacts/codearts-project-verification.json`

## STEP 8 — CONFIGURE PROJECT DESIGN

**Classification: ASSISTED**

**Objective**: Apply any remaining design configuration: update name/description if it needs correction, and add members with roles.

**Inputs**: project_id, description (if changed), members_to_add.

**Preconditions**: Step 7 completed with `project_id` resolved.

If updating name/description:

- **Approval requirement**: EXPLICIT.
- **Command**:

```bash
hcloud ProjectMan UpdateProjectV4 --cli-region=<SOURCE_REGION> \
  --project_id="<PROJECT_ID>" \
  --project_name="<PROJECT_NAME>" \
  --description="<DESCRIPTION>"
```

If adding members (repeat per member):

- **Approval requirement**: EXPLICIT per member, or as a single batch approval covering the full member list presented to the approval owner.
- **Command**:

```bash
hcloud ProjectMan AddMemberV4 --cli-region=<SOURCE_REGION> \
  --project_id="<PROJECT_ID>" \
  --domain_id="<DOMAIN_ID>" \
  --user_id="<USER_ID>" \
  --role_id=<ROLE_ID>
```

`role_id` reference: `-1` project creator, `3` project manager, `4` developer, `5` test manager, `6` tester, `7` participant, `8` viewer, `9` O&M manager, `10` product manager, `11` system engineer.

**Expected result**: Project description/name finalized; all requested members added.

**Failure action**: STOP on any individual failure; report which members succeeded and which failed. Do not roll back successful additions automatically.

**Evidence artifact**: `artifacts/codearts-design-config-result.json`

## STEP 9 — VERIFY DESIGN CONFIGURATION

**Classification: ASSISTED**

**Objective**: Confirm the final project state matches the approved plan.

**Inputs**: project_id.

**Preconditions**: Step 8 completed.

**Commands** (read-only):

```bash
hcloud ProjectMan ShowProjectInfoV4 --cli-region=<SOURCE_REGION> --project_id="<PROJECT_ID>"
hcloud ProjectMan ListProjectMembersV4 --cli-region=<SOURCE_REGION> --project_id="<PROJECT_ID>"
```

**Approval requirement**: None.

**Verification**: `project_name`, `description`, and `project_type` match the plan; every member from `members_to_add` appears in `ListProjectMembersV4` with the expected role.

**Expected result**: Design configuration fully verified.

**Failure action**: Report validation failure. Do NOT delete or recreate the project automatically.

**Evidence artifact**: `artifacts/codearts-design-verification-report.md`

## STEP 10 — CLOSURE

**Classification: AUTOMATED**

**Objective**: Generate final summary, evidence, and follow-up actions.

**Inputs**: All artifacts from Steps 1-9.

**Preconditions**: All previous steps completed.

Generate:
- Final summary (project_id, project_name, project_type, region, creation path used)
- Members added
- Capability probe result (so future runs can skip re-probing if still valid)
- Warnings (for example, if Path B/manual creation was used)
- Explicit statement that CodeArts Repo, Build, Check, Deploy, Pipeline, and Release are out of scope and were not touched
- Follow-up actions
- Unresolved risks

Do NOT delete the project automatically under any circumstance in this closure step.

**Expected result**: Complete closure report.

**Evidence artifact**: `artifacts/codearts-final-report.md`

# Capability gap handling

When a capability required for CodeArts project design/creation is not available or not confirmed:

1. Document the gap with Gap ID, phase, and impact (see the known gaps listed below)
2. Classify the gap: critical path or optional
3. Evaluate alternatives:
   - Can the step be performed via hcloud CLI? → USE_HCLOUD_CLI
   - Can it only be done manually in the console? → USE_MANUAL_CONSOLE_FALLBACK
   - Can an existing MCP tool accomplish the task? → USE_EXISTING_TOOL
   - Is a new MCP needed? → CREATE_NEW_MCP (last resort; not applicable to this skill's known gaps)
4. Never auto-activate a generated MCP or invent an undocumented command as a workaround
5. Update skill status if critical gaps remain

Known capability gaps:
- GAP-CODEARTS-001: No dedicated CodeArts/ProjectMan MCP exists. All operations via hcloud CLI. [VERIFIED_FROM_PUBLIC_API_DOCS]
- GAP-CODEARTS-002: `CreateProjectV4` exists in the official SDK but is not documented in the public CodeArts Req API Reference index; must be probed live per tenant/CLI version before use (Step 4), with a manual console fallback. [VERIFIED_FROM_SDK_SOURCE] [NOT_IN_PUBLIC_DOCS]
- GAP-CODEARTS-003: No operation exists to list global project-creation templates; `template_id` can only be used if already known and verified by the approval owner. [VERIFIED_FROM_SDK_SOURCE]
- GAP-CODEARTS-004: This skill has not been executed against a live hcloud CLI or live tenant; all CLI syntax is derived from public API documentation and official SDK source, not from `--help` output captured live. [NOT_LIVE_TESTED]

# Output artifacts

- artifacts/codearts-intent.json — Parsed intent
- artifacts/codearts-auth-discovery.json — Authentication, region, and service availability
- artifacts/codearts-existing-projects.json — Name-check and existing-project discovery
- artifacts/codearts-create-capability-probe.json — CreateProjectV4 availability classification
- artifacts/codearts-project-plan.md — Project plan (name, type, path, reuse decision)
- artifacts/codearts-project-result.json — Creation or reuse result
- artifacts/codearts-project-verification.json — Post-creation verification (project_id resolved)
- artifacts/codearts-design-config-result.json — Update/member-addition results
- artifacts/codearts-design-verification-report.md — Final design verification
- artifacts/codearts-final-report.md — Closure report

# Troubleshooting

| Symptom | Likely cause | Diagnosis | Resolution |
|---|---|---|---|
| `hcloud: command not found` | KooCLI not installed or not in PATH | `hcloud version` | Install KooCLI per `# Prerequisites` above; add `/usr/local/bin` to PATH |
| Authentication failure | hcloud profile misconfigured | `hcloud configure show --cli-profile=default` | Re-run `hcloud configure init` |
| Region rejected for ProjectMan | Region not in ProjectMan's endpoint list | Compare against Rule 4 region list | Use a confirmed region (for example `ap-southeast-3`, not `ap-southeast-1`) |
| `CreateProjectV4` not listed in `hcloud ProjectMan --help` | Older KooCLI/API Explorer metadata without this operation | Step 4 probe result | Use the manual console fallback (Path B); do not invent a substitute command |
| `CreateProjectV4` call rejected (403/permission) | Tenant lacks CodeArts project-creation permission, or the operation is gated for that account | Error message from the call | Request CodeArts project-creator permission from the admin, or use Path B |
| `CheckProjectNameV4` returns `exist: true` unexpectedly | Project name is unique platform-wide, not per-tenant | `ListProjectsV4 --search=` shows no matching project in this tenant | Choose a different project name |
| `ListProjectsV4`/`ShowProjectInfoV4` return no results after creation | Manual creation not yet completed, or search term mismatch | Ask human operator to confirm console creation | Retry the read after confirming creation, or correct the search term |
| `AddMemberV4` fails for a specific user | Invalid `user_id`/`domain_id`, or role not permitted | Error details from the call | Re-resolve the user's IAM identifiers; confirm role_id is a supported value |
| Region mismatch between plan and call | `--cli-region` omitted or wrong on a later command | Compare command flags across steps | Ensure every ProjectMan command uses the same `--cli-region` used at creation |

# Failure handling

- Authentication failure: verify hcloud config, region, IAM permissions. Do not retry with different credentials without operator confirmation.
- Region rejected: verify against the confirmed ProjectMan region list before assuming a transient error.
- Capability probe negative: switch to manual console fallback; do not invent a replacement command.
- Name check ambiguous or taken: present to approval owner; do not auto-select or auto-rename.
- Creation failure (CLI or manual): STOP, preserve evidence, report to approval owner.
- Update/member-addition failure: STOP, report which operations succeeded/failed; do not roll back successful ones automatically.
- Verification failure: report; do not delete or recreate the project automatically.

# Recovery procedure

1. If failure during discovery (Steps 2-4): no resource created. Fix authentication/region/capability issue and retry from Step 2.
2. If failure during creation (Step 6, Path A): check the error. If authorization-related, switch to Path B in the same step. If quota/name related, correct and retry.
3. If failure during creation (Step 6, Path B): ask the human operator whether the console step actually completed before assuming failure; re-run Step 7 to check.
4. If failure during design configuration (Step 8): project exists but is only partially configured. Report exactly which updates/members succeeded; retry only the failed ones.
5. If failure during verification (Step 9): project and/or members may be in an inconsistent state. Do not delete the project; report and await a decision.

# Rollback

Project creation is not automatically reversible in this skill's normal workflow. A project should NOT be deleted automatically after a downstream failure (for example, a failed member addition) — report and let the approval owner decide. Members can be removed individually without deleting the whole project. Manual (Path B) creation cannot be "rolled back" by this skill; a human operator created it and must also remove it if needed.

Rollback actions below require explicit approval and are never part of the normal Steps 1-10 workflow:

**Remove a member:**
```bash
hcloud ProjectMan BatchDeleteMembersV4 --cli-region=<SOURCE_REGION> \
  --project_id="<PROJECT_ID>" \
  --user_ids='["<USER_ID>"]'
```

**Delete the project (last resort):**
```bash
hcloud ProjectMan DeleteProjectV4 --cli-region=<SOURCE_REGION> --project_id="<PROJECT_ID>"
```

Verify after deletion:
```bash
hcloud ProjectMan ListProjectsV4 --cli-region=<SOURCE_REGION> --offset=0 --limit=10 --search="<PROJECT_NAME>"
```
Confirm the project no longer appears.

Do NOT delete the project automatically after any failure in Steps 8-9. Do NOT remove members without explicit approval. Do NOT attempt to "undo" a manual (Path B) console creation programmatically. Do NOT invent a bulk-rollback command that is not documented here.

# Evidence and traceability

- All hcloud CLI commands logged with timestamps
- project_id, project_num_id, and member identifiers recorded in artifacts
- Approval decisions recorded with approver identity and timestamp
- Capability probe result recorded and reusable across runs against the same tenant/CLI version (re-probe if either changes)
- No secrets in any artifact

# Known limitations

- No dedicated CodeArts or ProjectMan MCP exists; all operations via hcloud CLI [VERIFIED_FROM_PUBLIC_API_DOCS]
- `CreateProjectV4` is undocumented in the public API Reference index; its live availability through KooCLI has not been confirmed by this skill's authors and MUST be probed before first use [NOT_LIVE_TESTED] [NOT_IN_PUBLIC_DOCS]
- No global "list project-creation templates" operation exists; `template_id` can only be supplied, not discovered, by this skill [VERIFIED_FROM_SDK_SOURCE]
- ProjectMan is only confirmed available in 9 regions (see Rule 4); other regions are unverified [REGION_DEPENDENT]
- This skill's scope explicitly excludes CodeArts Repo, Build, Check, Deploy, Pipeline, and Release
- Manual console fallback (Path B) cannot be automated by this skill; it requires a human operator to click through the console

# Status justification

Status: READY_WITH_WARNINGS

Evidence:
- `ListProjectsV4`, `CheckProjectNameV4`, `ShowProjectInfoV4`, `UpdateProjectV4`, `DeleteProjectV4`, `AddMemberV4`, `ListProjectMembersV4` are documented in the public Huawei Cloud CodeArts Req API Reference [VERIFIED_FROM_PUBLIC_API_DOCS]
- `CreateProjectV4` (`POST /v4/project`) is present and fully defined (request/response models, required/optional fields, HTTP method and path) in the officially released `huaweicloud-sdk-projectman` Python SDK source code on the official `huaweicloud` GitHub organization, but is absent from the public API Reference index [VERIFIED_FROM_SDK_SOURCE] [NOT_IN_PUBLIC_DOCS]
- ProjectMan's supported regions were confirmed from the SDK's region definition file, not from a generic Huawei Cloud region list [VERIFIED_FROM_SDK_SOURCE]
- No dedicated CodeArts/ProjectMan MCP exists [VERIFIED_FROM_PUBLIC_API_DOCS]
- All write operations require explicit approval [INFERRED]
- No cloud-side or CLI-side live test was executed; this authoring environment had no Huawei Cloud network access or credentials [NOT_LIVE_TESTED]
- Because of the above, this skill mandates a live capability probe (Step 4) before any workflow instance relies on `CreateProjectV4`, and ships a fully documented manual fallback for when the probe is negative
