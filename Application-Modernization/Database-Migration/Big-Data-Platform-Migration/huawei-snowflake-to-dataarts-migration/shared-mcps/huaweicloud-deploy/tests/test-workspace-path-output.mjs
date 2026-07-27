import assert from "node:assert";
import { readFile } from "node:fs/promises";

console.log("Test: MCP generation response must expose Terraform workspace path");

const serverSource = await readFile("server.mjs", "utf-8");

assert(
  serverSource.includes("function buildTerraformWorkspaceOutput(workdir)"),
  "server.mjs must define buildTerraformWorkspaceOutput"
);

assert(
  serverSource.includes("terraform_workspace_path"),
  "generation response must include terraform_workspace_path"
);

assert(
  serverSource.includes("terraform_files"),
  "generation response must include terraform_files"
);

assert(
  serverSource.includes("next_steps"),
  "generation response must include next_steps"
);

assert(
  serverSource.includes("backup_hint"),
  "generation response must include backup_hint"
);

assert(
  serverSource.includes("Terraform files generated successfully at:"),
  "generation response must include a visible generated-path message"
);

console.log("PASS: Terraform workspace path output is exposed by the MCP response");
