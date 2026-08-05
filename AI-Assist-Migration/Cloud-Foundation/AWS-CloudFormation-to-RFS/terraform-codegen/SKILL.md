---
name: terraform-codegen
description: Terraform MCP workflows for IaC code generation, registry discovery, workspace management, run execution, and variable configuration. Use when generating Terraform code, discovering provider/module versions, managing HCP Terraform workspaces, or executing runs. Prefix: terraform_.
---

# Terraform Code Generation for OpenCode

Terraform registry integration and HCP Terraform/Enterprise automation via `terraform-mcp-server` (46 tools, prefix `terraform_`).

## Architecture

```
opencode ──MCP──→ terraform-mcp-server ──→ Terraform Registry + HCP Terraform API
                     ├── Registry (providers, modules, policies)
                     ├── Workspaces (CRUD, variables, tags)
                     ├── Runs (create, plan, apply, monitor)
                     ├── Variable Sets (cross-workspace sharing)
                     └── Projects & Organizations
```

**BEFORE generating any Terraform code**: Query registries for latest versions and documentation.

## Tool Catalog

### Registry Discovery (Always Available)

| Tool | Purpose |
|------|---------|
| `terraform_get_latest_provider_version` | Latest provider version (e.g., hashicorp/aws) |
| `terraform_get_provider_capabilities` | Resources, data sources, functions, guides |
| `terraform_get_provider_details` | Full provider documentation |
| `terraform_search_providers` | Search provider docs by service slug |
| `terraform_get_latest_module_version` | Latest module version |
| `terraform_search_modules` | Search public module registry |
| `terraform_get_module_details` | Full module documentation |
| `terraform_search_policies` | Search policy registry |
| `terraform_get_policy_details` | Full policy documentation |

### Private Registry (Requires Token)

| Tool | Purpose |
|------|---------|
| `terraform_search_private_providers` | Search private providers |
| `terraform_get_private_provider_details` | Private provider details |
| `terraform_search_private_modules` | Search private modules |
| `terraform_get_private_module_details` | Private module details |

### Workspaces

| Tool | Purpose |
|------|---------|
| `terraform_list_workspaces` | Search/list workspaces |
| `terraform_get_workspace_details` | Full workspace details |
| `terraform_create_workspace` | Create new workspace |
| `terraform_update_workspace` | Update workspace config |
| `terraform_create_workspace_tags` | Add tags |
| `terraform_read_workspace_tags` | Read tags |
| `terraform_list_workspace_variables` | List workspace variables |
| `terraform_create_workspace_variable` | Create variable |
| `terraform_update_workspace_variable` | Update variable |
| `terraform_list_workspace_policy_sets` | Policy sets attached to workspace |

### Runs

| Tool | Purpose |
|------|---------|
| `terraform_create_run` | Create run (plan_and_apply, plan_only, etc.) |
| `terraform_list_runs` | List/search runs |
| `terraform_get_run_details` | Run details |
| `terraform_get_plan_details` | Plan details |
| `terraform_get_plan_logs` | Plan logs |
| `terraform_get_plan_json_output` | Structured plan JSON |
| `terraform_get_apply_details` | Apply details |
| `terraform_get_apply_logs` | Apply logs |

### Variable Sets

| Tool | Purpose |
|------|---------|
| `terraform_list_variable_sets` | List all variable sets |
| `terraform_create_variable_set` | Create variable set |
| `terraform_create_variable_in_variable_set` | Add variable to set |
| `terraform_update_variable_in_variable_set` | Update variable in set |
| `terraform_delete_variable_in_variable_set` | Delete variable from set |
| `terraform_attach_variable_set_to_workspaces` | Attach to workspaces |
| `terraform_detach_variable_set_from_workspaces` | Detach from workspaces |

### Projects & Organizations

| Tool | Purpose |
|------|---------|
| `terraform_list_terraform_orgs` | List organizations |
| `terraform_list_terraform_projects` | List projects |
| `terraform_get_token_permissions` | Token permissions for org |
| `terraform_list_stacks` | List Stacks |
| `terraform_get_stack_details` | Stack details |

### No-Code Workspaces

| Tool | Purpose |
|------|---------|
| `terraform_create_no_code_workspace` | Create no-code module workspace |

## Workflows

### Workflow 1: Generate Terraform Code (Provider Resource)

```
1. terraform_get_latest_provider_version(namespace="hashicorp", name="aws")
   → e.g., "5.80.0"
2. terraform_search_providers(
     provider_name="aws",
     provider_namespace="hashicorp",
     service_slug="s3_bucket",
     provider_document_type="resources"
   )  → get provider_doc_id
3. terraform_get_provider_details(provider_doc_id="8894603")
   → full resource documentation with examples
4. Generate code using discovered constraints:
   terraform {
     required_providers {
       aws = { source = "hashicorp/aws", version = "~> 5.80" }
     }
   }
```

### Workflow 2: Generate Terraform Code (Module)

```
1. terraform_search_modules(module_query="vpc aws")
   → list of matching modules with module_id
2. terraform_get_module_details(module_id="terraform-aws-modules/vpc/aws/5.8.1")
   → inputs, outputs, examples
3. terraform_get_latest_module_version(
     module_publisher="terraform-aws-modules",
     module_name="vpc",
     module_provider="aws"
   )  → confirm latest version
4. Generate code:
   module "vpc" {
     source  = "terraform-aws-modules/vpc/aws"
     version = "5.8.1"
     # ... inputs from module details
   }
```

### Workflow 3: Discover Provider Capabilities

```
1. terraform_get_provider_capabilities(
     namespace="hashicorp",
     name="aws",
     version="5.80.0"
   )  → resources, data-sources, functions, guides counts + examples
```

### Workflow 4: Workspace Management

```
1. terraform_list_workspaces(terraform_org_name="my-org")
2. terraform_get_workspace_details(
     terraform_org_name="my-org",
     workspace_name="production"
   )  → config, variables, state
3. terraform_create_workspace(
     terraform_org_name="my-org",
     workspace_name="staging",
     auto_apply="false",
     execution_mode="remote",
     vcs_repo_identifier="myorg/infra",
     vcs_repo_oauth_token_id="ot-xxx"
   )
```

### Workflow 5: Variable Management

```
# Workspace variables
1. terraform_list_workspace_variables(
     terraform_org_name="my-org",
     workspace_name="production"
   )
2. terraform_create_workspace_variable(
     terraform_org_name="my-org",
     workspace_name="production",
     key="instance_count",
     value="3",
     category="terraform",
     description="Number of instances",
     sensitive=false
   )

# Variable sets (share across workspaces)
3. terraform_create_variable_set(
     terraform_org_name="my-org",
     name="common-vars",
     description="Shared variables",
     global=false
   )  → returns variable_set_id
4. terraform_create_variable_in_variable_set(
     variable_set_id="vs-xxx",
     key="region",
     value="us-east-1",
     category="terraform"
   )
5. terraform_attach_variable_set_to_workspaces(
     variable_set_id="vs-xxx",
     workspace_ids="ws-aaa,ws-bbb"
   )
```

### Workflow 6: Run Execution

```
1. terraform_create_run(
     terraform_org_name="my-org",
     workspace_name="production",
     run_type="plan_only",
     message="Planning infra changes for Q3"
   )  → returns run_id
2. terraform_get_run_details(run_id="run-xxx")  → check status
3. terraform_get_plan_details(plan_id="plan-xxx")
4. terraform_get_plan_logs(plan_id="plan-xxx")  → human-readable
   # OR
   terraform_get_plan_json_output(plan_id="plan-xxx")  → structured JSON
5. # If plan looks good:
   terraform_create_run(
     terraform_org_name="my-org",
     workspace_name="production",
     run_type="plan_and_apply"
   )
6. terraform_get_apply_details(apply_id="apply-xxx")
7. terraform_get_apply_logs(apply_id="apply-xxx")
```

**Run types**: `plan_and_apply`, `plan_only`, `refresh_state`, `allow_empty_apply`

### Workflow 7: Monitor Runs

```
1. terraform_list_runs(
     terraform_org_name="my-org",
     workspace_name="production",
     status=["planning", "applying", "errored"]
   )
2. terraform_get_run_details(run_id="run-xxx")
   → status: pending → planning → planned → applying → applied
```

### Run Status Flow

```
pending → fetching → fetching_completed → pre_plan_running → pre_plan_completed
→ queuing → plan_queued → planning → planned → cost_estimating → cost_estimated
→ policy_checking → policy_checked → confirmed → post_plan_running → post_plan_completed
→ planned_and_finished → apply_queued → applying → applied
```

Error states: `errored`, `canceled`, `force_canceled`, `discarded`

### Workflow 8: Policy Discovery

```
1. terraform_search_policies(policy_query="CIS AWS")
2. terraform_get_policy_details(terraform_policy_id="policies/hashicorp/CIS-Policy-Set-for-AWS-Terraform/1.0.1")
```

## Quick Reference

### Provider Namespaces

| Namespace | Provider |
|-----------|----------|
| `hashicorp` | aws, azurerm, google, null, random, tls |
| `aws-ia` | terraform-aws-iam, terraform-aws-vpc |
| `Azure` | terraform-azurerm-* |
| `terraform-google-modules` | terraform-google-* |

### `search_providers` Document Types

| Type | Use |
|------|-----|
| `overview` | General provider overview |
| `resources` | Deploy resources |
| `data-sources` | Read existing resources |
| `functions` | Provider functions |
| `guides` | Upgrade guides, custom config |
| `actions` | Terraform actions |
| `list-resources` | List resources (Terraform Search) |

### Workspace Execution Modes

| Mode | Description |
|------|-------------|
| `remote` | Run in HCP Terraform (default) |
| `local` | Run locally, state in HCP |
| `agent` | Run via agent |

### Variable Categories

| Category | Use |
|----------|-----|
| `terraform` | Terraform variables (var.xxx) |
| `env` | Environment variables |

### `search_modules` Selection Criteria

When choosing from multiple results:
1. Name similarity to query
2. Description relevance
3. Verification status (verified badge)
4. Download counts (popularity)

## Code Generation Best Practices

1. **Always pin versions**: Use `~> X.Y` for minor version constraints
2. **Check provider consistency**: All modules must use compatible provider versions
3. **Use variables**: No hardcoded values — define variables with descriptions
4. **Validate after generation**: Run `terraform validate` immediately
5. **Format**: Run `terraform fmt` after generation
6. **Private registry first**: When token present, check private before public

## Troubleshooting

### "Module not found"
- Try different `module_query` terms
- Check if it's a private module (use `search_private_modules`)
- Verify namespace/provider combination

### "Provider version not found"
- Check namespace (e.g., `hashicorp` not `aws`)
- Verify provider name spelling
- Use `get_latest_provider_version` to confirm

### Run fails
- Check `get_run_details` for error status
- Review `get_plan_logs` / `get_apply_logs` for error messages
- Use `get_plan_json_output` for structured error analysis
- Common causes: missing variables, invalid config, state conflicts

### Variable conflicts
- Use `list_workspace_variables` before creating to avoid duplicates
- Variable sets override workspace variables — check both
- Sensitive variables cannot be read back after creation

### Token/permission issues
- Use `get_token_permissions` to verify access
- Private registry tools require a valid Terraform token
- Some operations need org admin or workspace admin permissions
