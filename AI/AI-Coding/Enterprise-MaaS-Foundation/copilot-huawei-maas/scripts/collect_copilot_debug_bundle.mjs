#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import os from "node:os";

const args = process.argv.slice(2);

function argValue(name, fallback) {
	const idx = args.indexOf(name);
	if (idx >= 0 && args[idx + 1]) return args[idx + 1];
	return fallback;
}

const workspace = argValue("--workspace", process.cwd());
const outDir = argValue("--out", path.join(workspace, "copilot-debug-bundle"));
const home = os.homedir();
const oaiLogsDir = path.join(home, ".copilot", "oaicopilot", "logs");

function existingDirs(candidates) {
	return candidates.filter((candidate) => candidate && fs.existsSync(candidate));
}

function codeDataRoots() {
	if (process.platform === "win32") {
		const appData = process.env.APPDATA || path.join(home, "AppData", "Roaming");
		return existingDirs([
			path.join(appData, "Code"),
			path.join(appData, "Code - Insiders"),
			path.join(appData, "VSCodium"),
		]);
	}
	if (process.platform === "darwin") {
		return existingDirs([
			path.join(home, "Library", "Application Support", "Code"),
			path.join(home, "Library", "Application Support", "Code - Insiders"),
			path.join(home, "Library", "Application Support", "VSCodium"),
		]);
	}
	const config = process.env.XDG_CONFIG_HOME || path.join(home, ".config");
	return existingDirs([
		path.join(config, "Code"),
		path.join(config, "Code - Insiders"),
		path.join(config, "VSCodium"),
	]);
}

const codeRoots = codeDataRoots();

function mkdirp(p) {
	fs.mkdirSync(p, { recursive: true });
}

function copyFileIfExists(src, dst) {
	if (!fs.existsSync(src)) return false;
	mkdirp(path.dirname(dst));
	fs.copyFileSync(src, dst);
	return true;
}

function walk(dir, predicate, limit = 200) {
	const out = [];
	const stack = [dir];
	while (stack.length && out.length < limit) {
		const current = stack.pop();
		if (!current || !fs.existsSync(current)) continue;
		let entries = [];
		try {
			entries = fs.readdirSync(current, { withFileTypes: true });
		} catch {
			continue;
		}
		for (const entry of entries) {
			const full = path.join(current, entry.name);
			if (entry.isDirectory()) {
				stack.push(full);
			} else if (predicate(full)) {
				out.push(full);
				if (out.length >= limit) break;
			}
		}
	}
	return out;
}

fs.rmSync(outDir, { recursive: true, force: true });
mkdirp(outDir);

const copied = [];
function recordCopy(src, rel) {
	if (copyFileIfExists(src, path.join(outDir, rel))) copied.push(rel);
}

if (fs.existsSync(oaiLogsDir)) {
	for (const file of fs.readdirSync(oaiLogsDir).filter((x) => x.endsWith(".log"))) {
		recordCopy(path.join(oaiLogsDir, file), path.join("logs", file));
	}
}

for (const codeRoot of codeRoots) {
	const codeLogsDir = path.join(codeRoot, "logs");
	if (!fs.existsSync(codeLogsDir)) continue;
	const copilotLogs = walk(
		codeLogsDir,
		(file) => file.endsWith("GitHub Copilot Chat.log") || file.endsWith("GitHub Copilot.log"),
		50
	);
	for (const file of copilotLogs) {
		recordCopy(file, path.join("vscode-logs", path.basename(codeRoot), path.relative(codeLogsDir, file)));
	}
}

for (const codeRoot of codeRoots) {
	const codeUserDir = path.join(codeRoot, "User");
	const workspaceStorage = path.join(codeUserDir, "workspaceStorage");
	if (!fs.existsSync(workspaceStorage)) continue;
	const stateFiles = walk(workspaceStorage, (file) => file.endsWith(path.join("chatEditingSessions", "state.json")), 50);
	for (const file of stateFiles) {
		recordCopy(file, path.join("workspaceStorage", path.basename(codeRoot), path.relative(workspaceStorage, file)));
	}

	const debugFiles = walk(
		workspaceStorage,
		(file) => /GitHub\.copilot-chat[/\\]debug-logs[/\\].+[/\\](main\.jsonl|models\.json)$/.test(file),
		80
	);
	for (const file of debugFiles) {
		recordCopy(file, path.join("workspaceStorage", path.basename(codeRoot), path.relative(workspaceStorage, file)));
	}
}

for (const filename of ["app.py", "requirements.txt", "package.json", "pyproject.toml"]) {
	recordCopy(path.join(workspace, filename), path.join("workspace", filename));
}

for (const codeRoot of codeRoots) {
	const settingsPath = path.join(codeRoot, "User", "settings.json");
	if (!fs.existsSync(settingsPath)) continue;
	try {
		const settings = JSON.parse(fs.readFileSync(settingsPath, "utf8"));
		const redacted = {};
		for (const [key, value] of Object.entries(settings)) {
			if (key.startsWith("oaicopilot.") || key.startsWith("github.copilot.chat.")) {
				redacted[key] = value;
			}
		}
		if (redacted["oaicopilot.baseUrl"]) {
			redacted["oaicopilot.baseUrl"] = String(redacted["oaicopilot.baseUrl"]).replace(/(https?:\/\/)[^/]+/, "$1<host>");
		}
		mkdirp(path.join(outDir, "settings"));
		const rel = path.join("settings", `${path.basename(codeRoot)}-redacted-copilot-settings.json`);
		fs.writeFileSync(path.join(outDir, rel), JSON.stringify(redacted, null, 2));
		copied.push(rel);
	} catch {
		// Ignore malformed settings.
	}
}

fs.writeFileSync(
	path.join(outDir, "README.md"),
	`# Copilot Debug Bundle

Created: ${new Date().toISOString()}
Workspace: ${workspace}
Platform: ${process.platform}
VS Code data roots:
${codeRoots.map((x) => `- ${x}`).join("\n") || "- none found"}

This bundle may include prompts, local file paths, endpoint hosts, and tool-call payloads.
Review before sharing externally.

Copied files:
${copied.map((x) => `- ${x}`).join("\n")}
`
);

console.log(outDir);
