#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import readline from "node:readline";

const args = process.argv.slice(2);

function usage() {
	console.error("Usage: node glm_toolcall_log_summary.mjs /path/to/oaicopilot-YYYYMMDD.log");
	console.error("   or: node glm_toolcall_log_summary.mjs --latest");
	process.exit(1);
}

function latestLogPath() {
	const dir = path.join(os.homedir(), ".copilot", "oaicopilot", "logs");
	if (!fs.existsSync(dir)) return undefined;
	const files = fs
		.readdirSync(dir)
		.filter((name) => /^oaicopilot-\d{8}\.log$/.test(name))
		.map((name) => path.join(dir, name))
		.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs);
	return files[0];
}

const logPath = args[0] === "--latest" ? latestLogPath() : args[0];
if (!logPath) usage();
if (!fs.existsSync(logPath)) {
	console.error(`Log file not found: ${logPath}`);
	process.exit(1);
}

const stats = new Map();

function getStat(id) {
	if (!stats.has(id)) {
		stats.set(id, {
			model: "",
			chunks: 0,
			toolCallChunks: 0,
			argumentChars: 0,
			names: new Set(),
			finishReasons: new Set(),
			completionTokens: "",
			promptTokens: "",
		});
	}
	return stats.get(id);
}

const rl = readline.createInterface({
	input: fs.createReadStream(logPath, "utf8"),
	crlfDelay: Infinity,
});

for await (const line of rl) {
	if (!line.trim()) continue;

	let outer;
	try {
		outer = JSON.parse(line);
	} catch {
		continue;
	}

	if (outer.tag !== "openai.stream.chunk") continue;

	const raw = outer.data?.data;
	if (typeof raw !== "string" || raw === "[DONE]") continue;

	let chunk;
	try {
		chunk = JSON.parse(raw);
	} catch {
		continue;
	}

	const id = chunk.id ?? "unknown";
	const stat = getStat(id);
	stat.model = chunk.model ?? stat.model;
	stat.chunks += 1;

	if (chunk.usage) {
		stat.completionTokens = String(chunk.usage.completion_tokens ?? "");
		stat.promptTokens = String(chunk.usage.prompt_tokens ?? "");
	}

	const choice = chunk.choices?.[0];
	if (choice?.finish_reason) {
		stat.finishReasons.add(choice.finish_reason);
	}

	const toolCalls = choice?.delta?.tool_calls;
	if (!Array.isArray(toolCalls)) continue;

	stat.toolCallChunks += 1;
	for (const tc of toolCalls) {
		if (typeof tc.function?.name === "string") {
			stat.names.add(tc.function.name);
		}
		if (typeof tc.function?.arguments === "string") {
			stat.argumentChars += tc.function.arguments.length;
		}
	}
}

const rows = [...stats.entries()]
	.map(([id, stat]) => ({
		id,
		model: stat.model,
		chunks: stat.chunks,
		toolCallChunks: stat.toolCallChunks,
		argumentChars: stat.argumentChars,
		names: [...stat.names].join(","),
		finishReasons: [...stat.finishReasons].join(","),
		completionTokens: stat.completionTokens,
		promptTokens: stat.promptTokens,
	}))
	.filter((row) => row.toolCallChunks > 0 || row.completionTokens)
	.sort((a, b) => b.argumentChars - a.argumentChars);

console.table(rows);
