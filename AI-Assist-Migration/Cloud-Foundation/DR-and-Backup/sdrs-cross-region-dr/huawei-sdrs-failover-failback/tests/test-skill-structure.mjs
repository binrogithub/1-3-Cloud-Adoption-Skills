import { readFileSync, existsSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const skillDir = join(__dirname, "..");
const scenarioDir = join(__dirname, "..", "..");

const errors = [];

function assert(condition, message) {
  if (!condition) errors.push(message);
}

function readSkillMd() {
  const path = join(skillDir, "SKILL.md");
  assert(existsSync(path), "SKILL.md must exist");
  return readFileSync(path, "utf8");
}

const skillMd = readSkillMd();

assert(skillMd.includes("name: huawei-sdrs-failover-failback"), "SKILL.md frontmatter name must be huawei-sdrs-failover-failback");
assert(skillMd.includes("status: EXPERIMENTAL"), "SKILL.md status must be EXPERIMENTAL");
assert(skillMd.includes("risk_level: critical"), "SKILL.md risk_level must be critical");
assert(skillMd.includes("requires_explicit_approval: true"), "SKILL.md must require explicit approval");
assert(skillMd.includes("failover_and_failback_only"), "SKILL.md must declare failover_and_failback_only scope");
assert(skillMd.includes("CRITICAL") && skillMd.includes("MANDATORY_EXPLICIT_APPROVAL"), "SKILL.md must require CRITICAL approval");
assert(skillMd.includes("split brain") || skillMd.includes("split-brain"), "SKILL.md must include split-brain protection");
assert(skillMd.includes("Reverse reprotection") && skillMd.includes("NOT equivalent to failback") || skillMd.includes("NOT failback"), "SKILL.md must distinguish reverse reprotection from failback");
assert(skillMd.includes("planned") && skillMd.includes("unplanned"), "SKILL.md must distinguish planned vs unplanned failover");
assert(skillMd.includes("separate approval") || skillMd.includes("separate plan"), "SKILL.md must require separate approval for failback");
assert(skillMd.includes("GAP-SDR-003"), "SKILL.md must document GAP-SDR-003");
assert(skillMd.includes("# Rules"), "SKILL.md must have Rules section");
assert(skillMd.includes("# Prerequisites"), "SKILL.md must have Prerequisites section");
assert(skillMd.includes("# Troubleshooting"), "SKILL.md must have Troubleshooting section");

assert(existsSync(join(skillDir, "assets", "metadata", "skill.yaml")), "skill.yaml must exist");
assert(existsSync(join(skillDir, "assets", "metadata", "mcp-dependencies.yaml")), "mcp-dependencies.yaml must exist");

const mcpDeps = readFileSync(join(skillDir, "assets", "metadata", "mcp-dependencies.yaml"), "utf8");
assert(mcpDeps.includes("shared/mcps/"), "mcp-dependencies.yaml must use shared/mcps paths");

if (errors.length > 0) {
  console.error("FAILURES:");
  errors.forEach((e) => console.error("  - " + e));
  process.exit(1);
}

console.log("PASS: huawei-sdrs-failover-failback structure test (" + errors.length + " errors)");
