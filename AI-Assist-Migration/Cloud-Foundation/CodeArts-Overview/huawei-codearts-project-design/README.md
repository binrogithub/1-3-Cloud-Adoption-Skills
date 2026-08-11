# huawei-codearts-project-design

## Purpose

Design and create Huawei Cloud CodeArts Req (ProjectMan) projects using hcloud CLI: discover, validate naming, create (or reuse), and configure basic design (description, members). Scope ends at project design/creation — CodeArts Repo, Build, Check, Deploy, Pipeline, and Release are out of scope.

## Important finding: CreateProjectV4 exists, but is undocumented

While re-verifying whether CodeArts project creation could be done via CLI (it was previously assumed to require the console), the official `huaweicloud-sdk-projectman` SDK source code (published by Huawei on GitHub) was found to contain a fully defined `CreateProjectV4` operation:

- **Method/Path**: `POST /v4/project` (singular — note this differs from the plural `/v4/projects/...` used by every other ProjectMan v4 operation)
- **Request body**: `project_name` (required), `project_type` (required: `scrum`, `xboard`, `basic`, `phoenix`), `description`, `source`, `enterprise_id`, `template_id` (all optional)
- **Response**: `project_num_id`, `project_id`, `project_name`, `description`, `project_type`, `user_num_id`

This operation is **not** listed in the public CodeArts Req API Reference "Project Information" section, which only documents List/Check/Show/Update/Delete for projects. This is treated as a **documentation gap**, not proof the operation is unavailable — but it also was **not live-tested** against hcloud CLI or a real tenant in this authoring environment (no Huawei Cloud network access or credentials were available). See `SKILL.md` → "Capability gap handling" for how this skill handles that uncertainty: it probes the capability live (`hcloud ProjectMan CreateProjectV4 --help`) before relying on it, and falls back to the manual console procedure (documented in the companion Word guide) if the probe is negative.

## Supported scope

- CodeArts Req projects: Scrum, Kanban (`xboard`), Normal (`basic`), Phoenix (`phoenix`)
- Project design attributes: name, description, enterprise project association, members and roles

## Architecture

```
Design Intent
┌──────────────────────┐
│ project_name          │
│ project_type           │
│ description (opt)      │
│ members (opt)          │
└──────────┬────────────┘
           │
   CheckProjectNameV4 / ListProjectsV4  (discover before create)
           │
   Probe: hcloud ProjectMan CreateProjectV4 --help
           │
   ┌───────┴────────┐
   │                │
 AVAILABLE     NOT_AVAILABLE
   │                │
CreateProjectV4   Manual console
(hcloud CLI)      "Create Project"
   │                │
   └───────┬────────┘
           │
   ListProjectsV4 / ShowProjectInfoV4  (resolve + verify project_id)
           │
   UpdateProjectV4 (description) + AddMemberV4 (members)
           │
   ShowProjectInfoV4 + ListProjectMembersV4  (final verification)
```

## Rules summary

1. Service name in KooCLI is `ProjectMan`, not `CodeArts`
2. `CreateProjectV4` must be probed live before use; never assumed
3. Manual console fallback exists and must be used if the probe is negative — never invent a workaround command
4. DISCOVER BEFORE CREATE: resolve names to IDs, never hardcode
5. VERIFY AFTER EVERY WRITE
6. Every write operation requires explicit approval
7. ProjectMan is only confirmed in 9 specific regions — do not assume others work
8. Never include secrets in commands, examples, or logs
9. Scope stops at project design; Repo/Build/Deploy/Pipeline are out of scope

## Required tools

| Tool | Purpose |
|---|---|
| hcloud CLI (KooCLI) | All ProjectMan operations |
| Huawei Cloud auth (AK/SK) | API access |
| Target region (ProjectMan-supported) | Project region/endpoint |

## Workflow summary

1. Parse Intent → 2. Discover Auth/Region/Service → 3. Discover Existing & Validate Name → 4. Probe Create Capability → 5. Plan Project → 6. Create or Reuse Project (CLI or manual) → 7. Verify Project Created → 8. Configure Project Design → 9. Verify Design Configuration → 10. Closure

## Automation level by phase

| Phase | Automation | Mechanism |
|---|---|---|
| Parse intent | AUTOMATED | Logic |
| Discovery | ASSISTED | hcloud CLI read-only |
| Name validation | ASSISTED | hcloud CLI read-only |
| Capability probe | ASSISTED | hcloud CLI read-only (`--help`) |
| Planning | AUTOMATED | Logic |
| Creation | ASSISTED | hcloud CLI + approval, OR manual console + approval |
| Post-creation verification | ASSISTED | hcloud CLI read-only |
| Design configuration | ASSISTED | hcloud CLI + approval |
| Design verification | ASSISTED | hcloud CLI read-only |
| Closure | AUTOMATED | Logic |

## hcloud / verification status

- Verified from: official public CodeArts Req API Reference + official `huaweicloud-sdk-projectman` SDK source
- Live CLI test performed: **No** (no Huawei Cloud network access/credentials in the authoring environment)
- Confirmed ProjectMan regions: `cn-north-4`, `cn-north-1`, `cn-east-2`, `cn-south-1`, `cn-southwest-2`, `cn-east-3`, `ap-southeast-3`, `la-north-2`, `sa-brazil-1`

## MCP dependencies

| MCP | Required | Purpose |
|---|---|---|
| huaweicloud-ticket | No | Support escalation if the create-capability probe is negative and manual creation is also blocked |

No dedicated CodeArts or ProjectMan MCP exists. All operations via hcloud CLI.

## Approval gates

- Project creation (CLI or manual)
- Reuse of an existing project instead of creating one
- Project name/description update
- Adding a member to the project
- Any deletion (rollback-only, never part of normal workflow)

## Outputs

- artifacts/codearts-intent.json
- artifacts/codearts-auth-discovery.json
- artifacts/codearts-existing-projects.json
- artifacts/codearts-create-capability-probe.json
- artifacts/codearts-project-plan.md
- artifacts/codearts-project-result.json
- artifacts/codearts-project-verification.json
- artifacts/codearts-design-config-result.json
- artifacts/codearts-design-verification-report.md
- artifacts/codearts-final-report.md

## Known limitations

- `CreateProjectV4` is undocumented publicly; availability must be probed per tenant/CLI version
- No operation exists to list global project-creation templates
- Only 9 regions confirmed for ProjectMan
- Manual console fallback cannot be automated by this skill
- No live hcloud CLI or tenant test was performed during authoring

## Troubleshooting

See `SKILL.md` → "Troubleshooting" for the full table.

| Symptom | Action |
|---|---|
| `CreateProjectV4` missing from `--help` | Use manual console fallback |
| `CreateProjectV4` rejected (403) | Request permission, or use manual console fallback |
| Region rejected | Use a confirmed ProjectMan region (for example `ap-southeast-3`) |
| Name check ambiguous | Present to approval owner, do not auto-select |

## Maturity status

**READY_WITH_WARNINGS**

Documented ProjectMan operations (List/Check/Show/Update/Delete/AddMember/ListMembers) are verified from public API docs. `CreateProjectV4` is verified from official SDK source but not from public docs and not from a live test. Write operations require approval. The skill self-probes the create capability and has a manual fallback.

## Evidence

| Evidence | Type |
|---|---|
| ListProjectsV4, CheckProjectNameV4, ShowProjectInfoV4, UpdateProjectV4, DeleteProjectV4, AddMemberV4, ListProjectMembersV4 documented | VERIFIED_FROM_PUBLIC_API_DOCS |
| CreateProjectV4 fully defined in official SDK source (request/response models, HTTP method, path) | VERIFIED_FROM_SDK_SOURCE |
| CreateProjectV4 absent from public API Reference index | NOT_IN_PUBLIC_DOCS |
| ProjectMan regions confirmed from SDK region file | VERIFIED_FROM_SDK_SOURCE |
| No dedicated CodeArts/ProjectMan MCP exists | VERIFIED_FROM_PUBLIC_API_DOCS |
| Live hcloud CLI / tenant execution | NOT_LIVE_TESTED |
