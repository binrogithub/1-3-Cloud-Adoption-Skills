const { runShellCommand } = require("../core/command-runner");
const { scrubSecrets } = require("../core/secret-scrubber");

const COMMAND_ALLOWLIST = [
  "which hcloud",
  "hcloud --help",
  "hcloud version",
  "hcloud --version",
  "hcloud configure list",
  "hcloud configure test",
];

function isCommandAllowed(cmd) {
  const normalized = cmd.trim();
  return COMMAND_ALLOWLIST.includes(normalized);
}

function detectKooCli(options = {}) {
  const commandRunner = options.commandRunner || runShellCommand;
  const warnings = [];
  const errors = [];

  const result = {
    installed: false,
    executable: "hcloud",
    version: null,
    configure_test: {
      attempted: false,
      success: false,
      exit_code: null,
      output_summary: null,
    },
    configure_list: {
      attempted: false,
      success: false,
      exit_code: null,
      output_summary: null,
    },
    warnings,
    errors,
  };

  const whichResult = commandRunner({
    step: 0,
    name: "detect-hcloud",
    cmd: "which hcloud",
  });

  if (whichResult.exit_code !== 0) {
    errors.push("KooCLI executable hcloud not found");
    return result;
  }

  result.installed = true;

  const versionResult = commandRunner({
    step: 1,
    name: "hcloud-version",
    cmd: "hcloud --version",
  });

  if (versionResult.exit_code === 0 && versionResult.outputTail) {
    result.version = scrubSecrets(versionResult.outputTail.trim());
  } else {
    const altVersionResult = commandRunner({
      step: 2,
      name: "hcloud-version-alt",
      cmd: "hcloud version",
    });

    if (altVersionResult.exit_code === 0 && altVersionResult.outputTail) {
      result.version = scrubSecrets(altVersionResult.outputTail.trim());
    } else {
      warnings.push("Could not determine KooCLI version");
    }
  }

  result.configure_test.attempted = true;
  const configTestResult = commandRunner({
    step: 3,
    name: "hcloud-configure-test",
    cmd: "hcloud configure test",
  });

  result.configure_test.exit_code = configTestResult.exit_code;
  result.configure_test.success = configTestResult.exit_code === 0;
  result.configure_test.output_summary = scrubSecrets(
    configTestResult.outputTail ? configTestResult.outputTail.slice(-200) : ""
  ) || null;

  if (!result.configure_test.success) {
    warnings.push("hcloud configure test returned non-zero exit code");
  }

  result.configure_list.attempted = true;
  const configListResult = commandRunner({
    step: 4,
    name: "hcloud-configure-list",
    cmd: "hcloud configure list",
  });

  result.configure_list.exit_code = configListResult.exit_code;
  result.configure_list.success = configListResult.exit_code === 0;
  result.configure_list.output_summary = scrubSecrets(
    configListResult.outputTail ? configListResult.outputTail.slice(-200) : ""
  ) || null;

  if (!result.configure_list.success) {
    warnings.push("hcloud configure list returned non-zero exit code");
  }

  return result;
}

function runKooCliCommand(commandSpec, options = {}) {
  const commandRunner = options.commandRunner || runShellCommand;
  const cmd = typeof commandSpec === "string" ? commandSpec : commandSpec.cmd;

  if (!isCommandAllowed(cmd)) {
    return {
      step: commandSpec.step ?? null,
      name: commandSpec.name ?? cmd,
      command: cmd,
      exit_code: null,
      success: false,
      outputTail: null,
      rejected: true,
      rejection_reason: `Command not in allowlist: ${cmd}`,
    };
  }

  const spec = typeof commandSpec === "string"
    ? { step: 0, name: cmd, cmd }
    : commandSpec;

  const rawResult = commandRunner(spec);

  return {
    step: rawResult.step,
    name: rawResult.name,
    command: rawResult.command,
    exit_code: rawResult.exit_code,
    success: rawResult.success,
    outputTail: rawResult.outputTail,
    rejected: false,
  };
}

function buildKooCliFutureCommandPlan(options = {}) {
  const {
    migrationId = "unknown",
    jobName = "unknown",
    dliQueue = "default",
    runtimeArtifactsDir = "unknown",
  } = options;

  const categories = [
    {
      category: "inspect_workspace",
      description: "Inspect DataArts workspace configuration and status",
      commands: [
        {
          cmd: `hcloud DataArtsStudio listWorkspaces --cli-region="REGION"`,
          purpose: "List available DataArts workspaces",
          implementation_status: "PLANNED_NOT_IMPLEMENTED",
        },
      ],
    },
    {
      category: "create_job",
      description: "Create DataArts Factory job from migration package",
      commands: [
        {
          cmd: `hcloud DataArtsStudio createJob --cli-region="REGION" --workspace_id="WS_ID" --job_name="${jobName}"`,
          purpose: "Create DataArts Factory ETL job",
          implementation_status: "PLANNED_NOT_IMPLEMENTED",
        },
      ],
    },
    {
      category: "verify_job",
      description: "Verify DataArts job was created correctly",
      commands: [
        {
          cmd: `hcloud DataArtsStudio showJob --cli-region="REGION" --workspace_id="WS_ID" --job_name="${jobName}"`,
          purpose: "Verify job definition in DataArts Factory",
          implementation_status: "PLANNED_NOT_IMPLEMENTED",
        },
      ],
    },
    {
      category: "trigger_run",
      description: "Trigger immediate job execution (run-immediate equivalent)",
      commands: [
        {
          cmd: `hcloud DataArtsStudio createJobInstance --cli-region="REGION" --workspace_id="WS_ID" --job_name="${jobName}"`,
          purpose: "Trigger immediate job run",
          implementation_status: "PLANNED_NOT_IMPLEMENTED",
        },
      ],
    },
    {
      category: "query_instance",
      description: "Query job instance status",
      commands: [
        {
          cmd: `hcloud DataArtsStudio showJobInstance --cli-region="REGION" --workspace_id="WS_ID" --job_name="${jobName}" --instance_id="INSTANCE_ID"`,
          purpose: "Query job instance execution status",
          implementation_status: "PLANNED_NOT_IMPLEMENTED",
        },
      ],
    },
    {
      category: "query_logs",
      description: "Query job execution logs and evidence",
      commands: [
        {
          cmd: `hcloud DataArtsStudio showJobInstanceLog --cli-region="REGION" --workspace_id="WS_ID" --instance_id="INSTANCE_ID"`,
          purpose: "Retrieve job execution logs",
          implementation_status: "PLANNED_NOT_IMPLEMENTED",
        },
      ],
    },
    {
      category: "validate_output",
      description: "Validate runtime output and equivalence",
      commands: [
        {
          cmd: `hcloud DLI runSql --cli-region="REGION" --queue="${dliQueue}" --sql="SELECT COUNT(*) FROM validation_table"`,
          purpose: "Run validation SQL query via DLI",
          implementation_status: "PLANNED_NOT_IMPLEMENTED",
        },
      ],
    },
  ];

  return {
    migration_id: migrationId,
    job_name: jobName,
    dli_queue: dliQueue,
    runtime_artifacts_dir: runtimeArtifactsDir,
    plan_note: "All commands are PLANNED_NOT_IMPLEMENTED. No service API calls are made.",
    categories,
    generated_at: new Date().toISOString(),
  };
}

module.exports = {
  detectKooCli,
  runKooCliCommand,
  buildKooCliFutureCommandPlan,
  isCommandAllowed,
  COMMAND_ALLOWLIST,
};
