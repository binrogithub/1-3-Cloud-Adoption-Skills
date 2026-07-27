import { writeFile, readFile, mkdir, access, rm } from "node:fs/promises";
import { join, resolve } from "node:path";
import { existsSync } from "node:fs";

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  ListToolsRequestSchema,
  CallToolRequestSchema
} from "@modelcontextprotocol/sdk/types.js";

import { validateArchitecture, SUPPORTED, PHASE1, PHASE2 } from "./architecture-validator.mjs";
import { generateTerraform } from "./terraform-generator.mjs";
import {
  runTerraformCommand,
  ensureWorkdir,
  writeTerraformFiles,
  readTerraformPlan,
  FORBIDDEN_COMMANDS
} from "./terraform-executor.mjs";
import { analyzePlan, formatPlanSummary } from "./plan-analyzer.mjs";

const WORKSPACE_BASE = process.env.DEPLOY_WORKSPACE_BASE || join(process.cwd(), "workspaces");

function buildTerraformWorkspaceOutput(workdir) {
  const absoluteWorkdir = resolve(workdir);

  return {
    terraform_workspace_path: absoluteWorkdir,
    terraform_files: {
      versions_tf: join(absoluteWorkdir, "versions.tf"),
      providers_tf: join(absoluteWorkdir, "providers.tf"),
      variables_tf: join(absoluteWorkdir, "variables.tf"),
      main_tf: join(absoluteWorkdir, "main.tf"),
      outputs_tf: join(absoluteWorkdir, "outputs.tf"),
      tfvars_example: join(absoluteWorkdir, "terraform.tfvars.example")
    },
    next_steps: [
      `cd ${absoluteWorkdir}`,
      "terraform init",
      "terraform plan"
    ],
    backup_hint: `Backup this directory to preserve the generated Terraform source: ${absoluteWorkdir}`
  };
}


const server = new Server(
  {
    name: "huaweicloud-deploy",
    version: "0.2.0"
  },
  {
    capabilities: {
      tools: {}
    }
  }
);

const TOOLS = [
  {
    name: "GenerateTerraformFromArchitecture",
    description:
      "Generate Terraform files from an approved architecture JSON. " +
      "Creates versions.tf, providers.tf, variables.tf, main.tf, outputs.tf, and terraform.tfvars.example. " +
      "Does NOT create cloud resources. Does NOT include secrets.",
    inputSchema: {
      type: "object",
      properties: {
        architecture: {
          type: "object",
          description: "Approved architecture definition",
          properties: {
            architecture_id: { type: "string", description: "Unique identifier for this architecture" },
            region: { type: "string", description: "Huawei Cloud region code" },
            deployment_mode: { type: "string", enum: ["terraform"], description: "Deployment mode" },
            components: {
              type: "array",
              description: "Architecture components",
              items: {
                type: "object",
                properties: {
                  service: { type: "string", description: "Service type (vpc, subnet, security_group, ecs, elb, eip, elb_backend_attachment, rds_mysql, obs)" },
                  name: { type: "string", description: "Resource name" },
                  cidr: { type: "string", description: "CIDR block (for VPC/subnet)" },
                  gateway_ip: { type: "string", description: "Gateway IP (for subnet)" },
                  quantity: { type: "number", description: "Number of instances (for ECS)" },
                  flavor: { type: "string", description: "Flavor ID (for ECS/RDS)" },
                  image_name: { type: "string", description: "Image name (for ECS)" },
                  system_disk_type: { type: "string", description: "System disk type (GPSSD, SSD, ESSD)" },
                  system_disk_size_gb: { type: "number", description: "System disk size in GB" },
                  type: { type: "string", description: "ELB type (shared or dedicated)" },
                  listener_port: { type: "number", description: "ELB listener port" },
                  backend_port: { type: "number", description: "ELB backend port" },
                  bandwidth_mbps: { type: "number", description: "EIP bandwidth in Mbps" },
                  engine: { type: "string", description: "Database engine (for RDS)" },
                  engine_version: { type: "string", description: "Engine version (for RDS)" },
                  availability_zone: { type: "string", description: "Availability zone override" },
                  db_port: { type: "number", description: "Database port (for RDS)" },
                  database_name: { type: "string", description: "Database name (for RDS)" },
                  username: { type: "string", description: "Admin username (for RDS)" },
                  storage_type: { type: "string", description: "Storage type (for RDS)" },
                  storage_gb: { type: "number", description: "Storage size in GB (for RDS)" },
                  bucket_name: { type: "string", description: "OBS bucket name (for OBS)" },
                  storage_class: { type: "string", description: "Storage class (for OBS)" },
                  acl: { type: "string", description: "ACL (for OBS)" },
                  elb_name: { type: "string", description: "ELB name to attach to (for elb_backend_attachment)" },
                  rules: {
                    type: "array",
                    description: "Security group rules",
                    items: {
                      type: "object",
                      properties: {
                        direction: { type: "string", enum: ["ingress", "egress"] },
                        protocol: { type: "string" },
                        port: { type: "number" },
                        remote_ip_prefix: { type: "string" }
                      }
                    }
                  }
                },
                required: ["service", "name"]
              }
            }
          },
          required: ["architecture_id", "region", "deployment_mode", "components"]
        }
      },
      required: ["architecture"]
    }
  },
  {
    name: "ValidateTerraformConfiguration",
    description:
      "Validate previously generated Terraform configuration. " +
      "Runs terraform fmt, terraform init, and terraform validate. " +
      "Does NOT create cloud resources.",
    inputSchema: {
      type: "object",
      properties: {
        architecture_id: { type: "string", description: "Architecture ID (matches workspace directory)" }
      },
      required: ["architecture_id"]
    }
  },
  {
    name: "RunTerraformPlan",
    description:
      "Run terraform plan to preview changes. " +
      "Does NOT apply changes. Does NOT create cloud resources. " +
      "Returns plan summary for review.",
    inputSchema: {
      type: "object",
      properties: {
        architecture_id: { type: "string", description: "Architecture ID (matches workspace directory)" },
        var_file: { type: "string", description: "Optional path to terraform.tfvars file" }
      },
      required: ["architecture_id"]
    }
  },
  {
    name: "ExplainTerraformPlan",
    description:
      "Analyze and explain the most recent terraform plan. " +
      "Summarizes resources to create/modify/delete, identifies risks, and recommends next action. " +
      "Does NOT apply changes.",
    inputSchema: {
      type: "object",
      properties: {
        architecture_id: { type: "string", description: "Architecture ID (matches workspace directory)" }
      },
      required: ["architecture_id"]
    }
  }
];

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOLS
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case "GenerateTerraformFromArchitecture":
        return await handleGenerateTerraform(args);
      case "ValidateTerraformConfiguration":
        return await handleValidateTerraform(args);
      case "RunTerraformPlan":
        return await handleRunTerraformPlan(args);
      case "ExplainTerraformPlan":
        return await handleExplainTerraformPlan(args);
      default:
        return {
          content: [{ type: "text", text: `Unknown tool: ${name}` }],
          isError: true
        };
    }
  } catch (error) {
    return {
      content: [{ type: "text", text: `Error: ${error.message}` }],
      isError: true
    };
  }
});

async function handleGenerateTerraform(args) {
  const architecture = args.architecture;

  const validation = validateArchitecture(architecture);
  if (!validation.valid) {
    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          status: "REJECTED",
          errors: validation.errors,
          warnings: validation.warnings,
          componentStatus: validation.componentStatus
        }, null, 2)
      }]
    };
  }

  const workdir = await ensureWorkdir(WORKSPACE_BASE, architecture.architecture_id);
  const files = generateTerraform(architecture);
  const writtenPaths = await writeTerraformFiles(workdir, files);

  const workspaceOutput = buildTerraformWorkspaceOutput(workdir);

  const result = {
    status: "GENERATED",
    architecture_id: architecture.architecture_id,
    region: architecture.region,

    // Backward-compatible field.
    workspace: workspaceOutput.terraform_workspace_path,

    // Explicit public contract: always show where Terraform was generated.
    terraform_workspace_path: workspaceOutput.terraform_workspace_path,
    terraform_files: workspaceOutput.terraform_files,
    next_steps: workspaceOutput.next_steps,
    backup_hint: workspaceOutput.backup_hint,

    files: Object.keys(files),
    file_paths: writtenPaths,
    message: `Terraform files generated successfully at: ${workspaceOutput.terraform_workspace_path}`,
    warnings: validation.warnings,
    componentStatus: validation.componentStatus,
    safety: {
      secrets_included: false,
      apply_available: false,
      destroy_available: false,
      phase: 2
    }
  };

  return {
    content: [{ type: "text", text: JSON.stringify(result, null, 2) }]
  };
}

async function handleValidateTerraform(args) {
  const { architecture_id } = args;
  const workdir = join(WORKSPACE_BASE, architecture_id.replace(/[^a-zA-Z0-9_-]/g, "_"));

  try {
    await access(join(workdir, "main.tf"));
  } catch {
    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          status: "ERROR",
          message: `No Terraform files found for architecture "${architecture_id}". Run GenerateTerraformFromArchitecture first.`
        }, null, 2)
      }]
    };
  }

  const steps = [];

  const fmtResult = await runTerraformCommand(["fmt", "-check"], workdir);
  steps.push({
    step: "terraform fmt -check",
    passed: fmtResult.success,
    output: fmtResult.success ? "Formatting OK" : fmtResult.stderr || fmtResult.stdout
  });

  const initResult = await runTerraformCommand(["init", "-backend=false"], workdir);
  steps.push({
    step: "terraform init -backend=false",
    passed: initResult.success,
    output: initResult.success ? "Init OK" : initResult.stderr
  });

  let validateResult = { success: false, stderr: "Skipped: init failed" };
  if (initResult.success) {
    validateResult = await runTerraformCommand(["validate"], workdir);
  }
  steps.push({
    step: "terraform validate",
    passed: validateResult.success,
    output: validateResult.success ? "Validation OK" : validateResult.stderr
  });

  const allPassed = steps.every(s => s.passed);

  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        status: allPassed ? "VALID" : "INVALID",
        architecture_id,
        workspace: workdir,
        steps,
        overall: allPassed ? "PASS" : "FAIL"
      }, null, 2)
    }]
  };
}

async function handleRunTerraformPlan(args) {
  const { architecture_id, var_file } = args;
  const workdir = join(WORKSPACE_BASE, architecture_id.replace(/[^a-zA-Z0-9_-]/g, "_"));

  try {
    await access(join(workdir, "main.tf"));
  } catch {
    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          status: "ERROR",
          message: `No Terraform files found for architecture "${architecture_id}". Run GenerateTerraformFromArchitecture first.`
        }, null, 2)
      }]
    };
  }

  const planArgs = ["plan", "-out=tfplan"];
  if (var_file) {
    planArgs.push(`-var-file=${var_file}`);
  }

  const result = await runTerraformCommand(planArgs, workdir);

  const summary = {
    status: result.success ? "PLAN_READY" : "PLAN_FAILED",
    architecture_id,
    workspace: workdir,
    exitCode: result.exitCode,
    output: result.success ? extractPlanSummary(result.stdout) : result.stderr,
    safety: {
      applied: false,
      apply_available: false,
      phase: 2
    },
    audit: result.audit
  };

  return {
    content: [{ type: "text", text: JSON.stringify(summary, null, 2) }]
  };
}

async function handleExplainTerraformPlan(args) {
  const { architecture_id } = args;
  const workdir = join(WORKSPACE_BASE, architecture_id.replace(/[^a-zA-Z0-9_-]/g, "_"));

  const planJson = await readTerraformPlan(workdir);
  const analysis = analyzePlan(planJson);
  const formatted = formatPlanSummary(analysis);

  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        architecture_id,
        workspace: workdir,
        analysis,
        formatted
      }, null, 2)
    }]
  };
}

function extractPlanSummary(stdout) {
  const lines = stdout.split("\n");
  const summaryLines = [];
  let capturing = false;
  for (const line of lines) {
    if (line.includes("Plan:") || line.includes("No changes")) {
      capturing = true;
    }
    if (capturing) {
      summaryLines.push(line);
    }
  }
  return summaryLines.length > 0 ? summaryLines.join("\n").trim() : "Plan output available (run ExplainTerraformPlan for details)";
}

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((error) => {
  console.error("Server failed to start:", error);
  process.exit(1);
});
