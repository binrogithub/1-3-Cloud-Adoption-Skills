export function analyzePlan(planJson) {
  if (!planJson) {
    return {
      status: "NO_PLAN",
      summary: "No plan file found. Run RunTerraformPlan first.",
      resources: { create: [], modify: [], delete: [], no_op: [] },
      risks: [],
      nextAction: "Run RunTerraformPlan to generate a plan."
    };
  }

  const plannedValues = planJson.planned_values || {};
  const resourceChanges = planJson.resource_changes || [];
  const outputChanges = planJson.output_changes || {};

  const create = [];
  const modify = [];
  const delete_ = [];
  const noOp = [];

  for (const change of resourceChanges) {
    const action = change.change?.actions || [];
    const entry = {
      address: change.address,
      type: change.type,
      name: change.name,
      actions: action
    };

    if (action.includes("create")) create.push(entry);
    else if (action.includes("delete")) delete_.push(entry);
    else if (action.includes("update") || action.includes("create-before-destroy")) modify.push(entry);
    else if (action.every(a => a === "no-op")) noOp.push(entry);
  }

  const risks = [];

  if (delete_.length > 0) {
    risks.push({
      level: "CRITICAL",
      message: `${delete_.length} resource(s) will be DELETED. Review carefully before any apply.`,
      resources: delete_.map(r => r.address)
    });
  }

  if (modify.length > 0) {
    risks.push({
      level: "WARNING",
      message: `${modify.length} resource(s) will be MODIFIED. In-place updates may cause downtime.`,
      resources: modify.map(r => r.address)
    });
  }

  const ecsCreates = create.filter(r => r.type?.includes("compute_instance"));
  if (ecsCreates.length > 0) {
    risks.push({
      level: "INFO",
      message: `${ecsCreates.length} ECS instance(s) will be created. Ensure correct image and flavor.`,
      resources: ecsCreates.map(r => r.address)
    });
  }

  const eipCreates = create.filter(r => r.type?.includes("vpc_eip"));
  if (eipCreates.length > 0) {
    risks.push({
      level: "INFO",
      message: `${eipCreates.length} EIP(s) will be created. This will incur ongoing bandwidth charges.`,
      resources: eipCreates.map(r => r.address)
    });
  }

  const rdsCreates = create.filter(r => r.type?.includes("rds_instance"));
  if (rdsCreates.length > 0) {
    risks.push({
      level: "INFO",
      message: `${rdsCreates.length} RDS instance(s) will be created. This will incur ongoing database charges.`,
      resources: rdsCreates.map(r => r.address)
    });
  }

  const obsCreates = create.filter(r => r.type?.includes("obs_bucket"));
  if (obsCreates.length > 0) {
    risks.push({
      level: "INFO",
      message: `${obsCreates.length} OBS bucket(s) will be created. Storage usage will incur charges.`,
      resources: obsCreates.map(r => r.address)
    });
  }

  const totalResources = create.length + modify.length + delete_.length;
  let nextAction;
  if (totalResources === 0) {
    nextAction = "No changes detected. Infrastructure matches configuration.";
  } else if (delete_.length > 0) {
    nextAction = "BLOCKED: Plan includes deletions. Review risks before proceeding. ApplyTerraformPlan is not available in phase 2.";
  } else {
    nextAction = "Plan is ready for review. ApplyTerraformPlan is not available in phase 2. To apply, run terraform apply manually after review.";
  }

  return {
    status: "ANALYZED",
    summary: `Plan: ${create.length} to create, ${modify.length} to modify, ${delete_.length} to delete, ${noOp.length} unchanged.`,
    resources: { create, modify, delete: delete_, no_op: noOp },
    risks,
    nextAction,
    totalChanges: totalResources
  };
}

export function formatPlanSummary(analysis) {
  const lines = [];
  lines.push(`=== Terraform Plan Analysis ===`);
  lines.push(`Status: ${analysis.status}`);
  lines.push(`Summary: ${analysis.summary}`);
  lines.push("");

  if (analysis.resources.create.length > 0) {
    lines.push("Resources to CREATE:");
    for (const r of analysis.resources.create) {
      lines.push(`  + ${r.address}`);
    }
    lines.push("");
  }

  if (analysis.resources.modify.length > 0) {
    lines.push("Resources to MODIFY:");
    for (const r of analysis.resources.modify) {
      lines.push(`  ~ ${r.address}`);
    }
    lines.push("");
  }

  if (analysis.resources.delete.length > 0) {
    lines.push("Resources to DELETE:");
    for (const r of analysis.resources.delete) {
      lines.push(`  - ${r.address}`);
    }
    lines.push("");
  }

  if (analysis.risks.length > 0) {
    lines.push("Risks:");
    for (const risk of analysis.risks) {
      lines.push(`  [${risk.level}] ${risk.message}`);
    }
    lines.push("");
  }

  lines.push(`Next action: ${analysis.nextAction}`);

  return lines.join("\n");
}
