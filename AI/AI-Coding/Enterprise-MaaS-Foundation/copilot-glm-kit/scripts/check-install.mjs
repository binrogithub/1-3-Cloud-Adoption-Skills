#!/usr/bin/env node
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import childProcess from "node:child_process";

function run(cmd, args) {
  try {
    return childProcess.execFileSync(cmd, args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
  } catch (error) {
    return error.stdout?.toString() || error.stderr?.toString() || "";
  }
}

function findCodeCommand() {
  if (process.platform === "darwin") {
    const macPath = "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code";
    if (fs.existsSync(macPath)) return macPath;
  }
  if (process.platform === "win32") {
    const local = process.env.LOCALAPPDATA;
    if (local) {
      const winPath = path.join(local, "Programs", "Microsoft VS Code", "bin", "code.cmd");
      if (fs.existsSync(winPath)) return winPath;
    }
  }
  return "code";
}

function codeRoots() {
  const home = os.homedir();
  if (process.platform === "win32") {
    const appData = process.env.APPDATA || path.join(home, "AppData", "Roaming");
    return [path.join(appData, "Code"), path.join(appData, "Code - Insiders"), path.join(appData, "VSCodium")];
  }
  if (process.platform === "darwin") {
    return [
      path.join(home, "Library", "Application Support", "Code"),
      path.join(home, "Library", "Application Support", "Code - Insiders"),
      path.join(home, "Library", "Application Support", "VSCodium"),
    ];
  }
  const config = process.env.XDG_CONFIG_HOME || path.join(home, ".config");
  return [path.join(config, "Code"), path.join(config, "Code - Insiders"), path.join(config, "VSCodium")];
}

console.log("Checking VS Code extension install...");
const codeCmd = findCodeCommand();
console.log(`Using code command: ${codeCmd}`);
const extensions = run(codeCmd, ["--list-extensions", "--show-versions"]);
const interesting = extensions
  .split(/\r?\n/)
  .filter((line) => /oai-compatible-copilot|github\.copilot/i.test(line));
console.log(interesting.join("\n") || "No matching extensions found from code CLI.");

console.log("\nChecking settings...");
for (const root of codeRoots()) {
  const settingsPath = path.join(root, "User", "settings.json");
  if (!fs.existsSync(settingsPath)) continue;
  const settings = JSON.parse(fs.readFileSync(settingsPath, "utf8"));
  console.log(`Settings: ${settingsPath}`);
  console.log(`  oaicopilot.baseUrl: ${settings["oaicopilot.baseUrl"] ? "set" : "missing"}`);
  console.log(`  oaicopilot.glmToolCallCompat: ${settings["oaicopilot.glmToolCallCompat"]}`);
  console.log(`  oaicopilot.models: ${Array.isArray(settings["oaicopilot.models"]) ? settings["oaicopilot.models"].map((m) => m.id).join(", ") : "missing"}`);
}

console.log("\nChecking OAI logs...");
const logDir = path.join(os.homedir(), ".copilot", "oaicopilot", "logs");
if (fs.existsSync(logDir)) {
  const logs = fs.readdirSync(logDir).filter((name) => name.endsWith(".log")).sort();
  console.log(logs.slice(-5).join("\n") || "No log files found.");
} else {
  console.log(`No OAI log directory found yet: ${logDir}`);
}
