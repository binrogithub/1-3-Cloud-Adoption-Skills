#!/usr/bin/env node
"use strict";

// Claude Code MaaS protocol adapter — Anthropic <-> Huawei MaaS OpenAI-compatible.
//
// Loopback-only, single-model (glm-5.2), no routing/fallback/Sidecar. Each
// streaming request is governed by a RequestLifecycleController (active
// watchdogs, cancellation, finish-aware EOF, backpressure, concurrency).
//
// PRD: docs/PRD_MAAS_STREAM_RELIABILITY_PRODUCTION_CLOSURE_V2.md

const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const {
  ErrorCodes,
  HTTP_STATUS,
  State,
  RequestLifecycleController,
  ConcurrencyGuard,
  isLoopback,
} = require(path.join(__dirname, "lifecycle.js"));

const ENV_FILE = process.env.ENV_FILE || "/etc/claude-code-proxy/maas.env";
loadEnvFile(ENV_FILE);

const HOST = process.env.PROXY_HOST || "127.0.0.1";
const PORT = Number(process.env.PROXY_PORT || "3000");
const MAAS_CHAT_URL =
  process.env.ANTHROPIC_PROXY_BASE_URL
  || "https://api-ap-southeast-1.modelarts-maas.com/openai/v1/chat/completions";
const DEFAULT_KEY =
  process.env.CLAUDE_CODE_PROXY_API_KEY
  || process.env.HUAWEI_MAAS_API_KEY
  || process.env.MAAS_API_KEY;
const DEFAULT_MODEL = process.env.COMPLETION_MODEL || "glm-5.2";

// Reliability config (env-overridable, validated at startup).
const CONNECT_TIMEOUT = Number(process.env.MAAS_CONNECT_TIMEOUT || "60") * 1000;
const IDLE_TIMEOUT = Number(process.env.MAAS_IDLE_TIMEOUT || "150") * 1000;
const TOTAL_TIMEOUT = Number(process.env.MAAS_TOTAL_TIMEOUT || "600") * 1000;
const MAX_CONCURRENCY = Number(process.env.MAAS_MAX_CONCURRENCY || "8");
const MAX_TOOL_ARGS_BYTES = Number(process.env.MAAS_MAX_TOOL_ARGS_BYTES || "262144");
const MAX_SSE_EVENT_BYTES = Number(process.env.MAAS_MAX_SSE_EVENT_BYTES || "1048576");
const MAX_REQUEST_BODY_BYTES = Number(process.env.MAAS_MAX_REQUEST_BODY_BYTES || "10485760");
const ADAPTER_VERSION = "stream-reliability-v2";

// X1 (PRD RELEASE_V7): safe degradation text for unresolvable tool args.
// Replaces the tool_use block with a text block; the tool is NOT executed.
const SAFE_DEGRADATION_TEXT = "所请求的工具调用未被执行：模型生成的参数不符合该工具的接口约定。可以用修正后的参数重试。";

// Validate timeouts at startup (fail before accepting traffic).
for (const [name, val] of [["connect", CONNECT_TIMEOUT], ["idle", IDLE_TIMEOUT], ["total", TOTAL_TIMEOUT]]) {
  if (!(val > 0)) { console.error(`adapter: invalid ${name} timeout: ${val}`); process.exit(1); }
}
if (TOTAL_TIMEOUT < CONNECT_TIMEOUT) { console.error("adapter: total < connect timeout"); process.exit(1); }
// Verify loopback bind at startup.
if (HOST !== "127.0.0.1" && HOST !== "localhost" && HOST !== "::1") {
  console.error(`adapter: refusing non-loopback bind: ${HOST}`); process.exit(1);
}

// Global concurrency guard + status registry.
const concurrencyGuard = new ConcurrencyGuard(MAX_CONCURRENCY);
const activeControllers = new Map(); // requestId -> controller
let lastSuccessAt = null;
let lastErrorCode = null;
let clientAbortCount = 0;
const startedAt = Date.now();

// D3 (PRD RELEASE_CLOSURE_V2): structured error tracking for /status.
const errorCounts = {};          // error code -> cumulative count
const recentErrors = [];         // ring buffer, max 20: {ts, code, request_id}
const RECENT_ERRORS_MAX = 20;
let reapedCount = 0;
let _testThrowCounter = 0;  // test hook counter (MAAS_TEST_THROW_AFTER_N)
// D2 (PRD RELEASE_CLOSURE_V3): tool args repair metrics.
let toolArgsRepaired = 0;
const toolArgsRepairRejected = {};  // gate name -> count
const toolArgsRejectClasses = {};   // D2 V4: parse-error class -> count
let toolMarkupSeen = 0;             // X2 V7: raw <tool_call markup as args count
let toolArgsDegraded = 0;           // D3 V8: requests where enforce emitted safe-degradation text

// D4 (PRD RELEASE_CLOSURE_V4): idempotent by requestId — _fail() fires
// _onTimeout which records, then the terminal path records again.  First
// call wins; subsequent calls for the same code+requestId are no-ops.
const _recordedErrors = new Set();  // "code:requestId" keys
function recordError(code, requestId) {
  if (!code) return;
  const key = `${code}:${requestId || ""}`;
  if (_recordedErrors.has(key)) return;
  _recordedErrors.add(key);
  // Cap growth: if set exceeds 1000 entries, keep the most recent 500.
  if (_recordedErrors.size > 1000) {
    const keep = [..._recordedErrors].slice(-500);
    _recordedErrors.clear();
    keep.forEach(k => _recordedErrors.add(k));
  }
  errorCounts[code] = (errorCounts[code] || 0) + 1;
  recentErrors.push({ ts: new Date().toISOString(), code, request_id: requestId || null });
  if (recentErrors.length > RECENT_ERRORS_MAX) recentErrors.shift();
}

function loadEnvFile(p) {
  if (!fs.existsSync(p)) return;
  const lines = fs.readFileSync(p, "utf8").split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match || process.env[match[1]]) continue;
    let value = match[2].trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    process.env[match[1]] = value;
  }
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on("data", (chunk) => {
      size += chunk.length;
      if (size > MAX_REQUEST_BODY_BYTES) {
        reject(new Error("request body too large"));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

function sendJson(res, status, payload) {
  if (res.headersSent || res.writableEnded) return;
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(payload));
}

// Sanitized error templates — never forward raw upstream bodies or exception text.
const ERROR_TEMPLATES = {
  [ErrorCodes.CONNECT_TIMEOUT]: { type: "api_error", message: "upstream connect timeout" },
  [ErrorCodes.IDLE_TIMEOUT]: { type: "api_error", message: "upstream idle timeout" },
  [ErrorCodes.TOTAL_TIMEOUT]: { type: "api_error", message: "upstream total timeout" },
  [ErrorCodes.UPSTREAM_HTTP]: { type: "api_error", message: "upstream http error" },
  [ErrorCodes.STREAM_EOF]: { type: "api_error", message: "upstream stream ended prematurely" },
  [ErrorCodes.STREAM_PROTOCOL]: { type: "invalid_request_error", message: "stream protocol error" },
  [ErrorCodes.TOOL_ARGS_TOO_LARGE]: { type: "invalid_request_error", message: "tool arguments too large" },
  [ErrorCodes.OVER_CAPACITY]: { type: "api_error", message: "adapter at capacity" },
};

function sendError(res, code) {
  const status = HTTP_STATUS[code] || 502;
  const tmpl = ERROR_TEMPLATES[code] || { type: "api_error", message: "upstream error" };
  sendJson(res, status, { type: "error", error: { ...tmpl, code } });
}

function sendSseError(res, code) {
  if (res.headersSent) {
    const tmpl = ERROR_TEMPLATES[code] || { type: "api_error", message: "upstream error" };
    res.write(`event: error\ndata: ${JSON.stringify({ type: "error", error: { ...tmpl, code } })}\n\n`);
    res.end();
  } else {
    sendError(res, code);
  }
}

function getAuthKey(req) {
  const xApiKey = req.headers["x-api-key"];
  if (typeof xApiKey === "string" && xApiKey.trim() && !xApiKey.trim().startsWith("$") && xApiKey.trim() !== "maas-local-proxy") {
    return xApiKey.trim();
  }
  const auth = req.headers.authorization || "";
  const match = String(auth).match(/^Bearer\s+(.+)$/i);
  if (match) {
    const key = match[1].trim();
    if (key && !key.startsWith("$") && key !== "maas-local-proxy") return key;
  }
  return DEFAULT_KEY;
}

function stripClaudeOnly(body) {
  delete body.thinking;
  delete body.context_management;
  if (body.output_config && typeof body.output_config === "object") {
    delete body.output_config.effort;
    if (Object.keys(body.output_config).length === 0) delete body.output_config;
  }
}

function textFromContent(content) {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content.filter((i) => i && i.type === "text" && typeof i.text === "string").map((i) => i.text).join("\n");
}

function normalizeToolResultContent(content) {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content.map((i) => (i && i.type === "text" && typeof i.text === "string") ? i.text : (i && typeof i.content === "string" ? i.content : "")).filter(Boolean).join("\n");
}

function anthropicMessagesToOpenAI(messages = []) {
  const out = [];
  for (const message of messages) {
    if (!message || !message.role) continue;
    if (typeof message.content === "string") { out.push({ role: message.role, content: message.content }); continue; }
    if (!Array.isArray(message.content)) { out.push({ role: message.role, content: "" }); continue; }
    if (message.role === "user") {
      const textParts = [];
      for (const item of message.content) {
        if (!item) continue;
        if (item.type === "tool_result") {
          out.push({ role: "tool", tool_call_id: item.tool_use_id, content: normalizeToolResultContent(item.content) });
        } else if (item.type === "text" && typeof item.text === "string") {
          textParts.push(item.text);
        }
      }
      if (textParts.length) out.push({ role: "user", content: textParts.join("\n") });
      continue;
    }
    if (message.role === "assistant") {
      const textParts = [];
      const toolCalls = [];
      for (const item of message.content) {
        if (!item) continue;
        // Strip thinking/redacted_thinking blocks — never forward to MaaS
        // (PRD THINKING_WAIT_VISIBILITY §3: inbound thinking must be dropped
        // or the second turn breaks).
        if (item.type === "thinking" || item.type === "redacted_thinking") continue;
        if (item.type === "text" && typeof item.text === "string") textParts.push(item.text);
        else if (item.type === "tool_use") toolCalls.push({ id: item.id, type: "function", function: { name: item.name, arguments: JSON.stringify(item.input || {}) } });
      }
      const openaiMessage = { role: "assistant", content: textParts.join("\n") || null };
      if (toolCalls.length) openaiMessage.tool_calls = toolCalls;
      out.push(openaiMessage);
    }
  }
  return out;
}

function anthropicToolsToOpenAI(tools = []) {
  if (!Array.isArray(tools)) return undefined;
  const converted = tools.filter((t) => t && t.name).map((t) => ({ type: "function", function: { name: t.name, description: t.description || "", parameters: t.input_schema || { type: "object", properties: {}, additionalProperties: true } } }));
  return converted.length ? converted : undefined;
}

function toOpenAIRequest(body) {
  stripClaudeOnly(body);
  const openai = { model: DEFAULT_MODEL, messages: [], max_tokens: body.max_tokens, temperature: body.temperature, top_p: body.top_p, stream: body.stream === true };
  if (body.system) openai.messages.push({ role: "system", content: textFromContent(body.system) });
  addToolUseGuardrails(openai.messages, body.tools);
  openai.messages.push(...anthropicMessagesToOpenAI(body.messages || []));
  const tools = anthropicToolsToOpenAI(body.tools);
  if (tools) { openai.tools = tools; if (body.tool_choice) openai.tool_choice = convertToolChoice(body.tool_choice); }
  for (const key of Object.keys(openai)) { if (openai[key] === undefined || openai[key] === null) delete openai[key]; }
  return openai;
}

function addToolUseGuardrails(messages, tools) {
  if (!Array.isArray(tools) || !tools.length) return;
  const toolNames = new Set(tools.map((t) => t && t.name).filter(Boolean));
  const parts = [];
  if (toolNames.has("Bash")) parts.push("When calling Bash, the function arguments must be a JSON object with a non-empty string field named command. Include the full shell command in command. Never call Bash with {}.");
  if (toolNames.has("Read")) parts.push("When calling Read, the function arguments must include file_path as an absolute path string. Never call Read with {}.");
  if (toolNames.has("Write")) parts.push("When calling Write, the function arguments must include file_path and content strings. Never call Write with {}.");
  if (toolNames.has("Edit")) parts.push("When calling Edit, the function arguments must include file_path, old_string, and new_string strings. Never call Edit with {}.");
  if (!parts.length) return;
  messages.push({ role: "system", content: ["Tool-call argument rules:", ...parts, "If you do not know the exact required arguments, ask a short question or explain the next step in text instead of calling the tool."].join("\n") });
}

function convertToolChoice(toolChoice) {
  if (toolChoice === "auto" || toolChoice?.type === "auto") return "auto";
  if (toolChoice?.type === "any") return "required";
  if (toolChoice?.type === "tool" && toolChoice.name) return { type: "function", function: { name: toolChoice.name } };
  return "auto";
}

function convertStopReason(reason) {
  if (reason === "tool_calls") return "tool_use";
  if (reason === "length") return "max_tokens";
  if (reason === "stop") return "end_turn";
  return reason || "end_turn";
}

// D1 (PRD RELEASE_CLOSURE_V3): three-gate tool args repair.
// Attempts structural completion of truncated tool-call JSON only when
// evidence authorizes it.  Returns { input, gate, schema } on success,
// or { rejected: gate } on failure.
//
// Gate 1 (source): only attempt when the upstream gave a clean tool-call
//   termination (finishReason is tool_use or end_turn).  max_tokens means

// D2 (PRD RELEASE_CLOSURE_V4): classify JSON.parse rejection by message prefix
// into a constant enum.  NEVER log err.message directly — the "not_json" class
// embeds a 10-char payload excerpt that would leak tool args into the log.
function classifyParseError(message) {
  if (typeof message !== "string") return "other";
  if (message.startsWith("Unexpected end of JSON input")) return "end_of_input";
  if (message.startsWith("Unterminated string in JSON")) return "unterminated_string";
  if (message.startsWith("Expected ',' or '}'") || message.startsWith("Expected ',' or ']'")) return "expected_comma_or_close";
  if (message.startsWith("Expected property name or '}'")) return "dialect_property_name";
  if (message.startsWith("Expected double-quoted property name")) return "expected_quoted_name";
  if (message.startsWith("Unexpected token")) return "not_json";
  return "other";
}

// D1 (PRD RELEASE_CLOSURE_V6): minimal shape diagnostics for bad tool args.
// Pure structure — a single code point (integer) + punctuation counts.
// Never logs any character of the args; the code point is a number, not text.
function computeShapeDiagnostics(args) {
  const s = (args || "").trimStart();
  const firstCharCode = s.length > 0 ? s.codePointAt(0) : null;
  const counts = { brace_open: 0, brace_close: 0, bracket_open: 0, bracket_close: 0,
                   double_quote: 0, single_quote: 0, backslash: 0, lt: 0, gt: 0 };
  for (const ch of (args || "")) {
    switch (ch) {
      case "{": counts.brace_open++; break;
      case "}": counts.brace_close++; break;
      case "[": counts.bracket_open++; break;
      case "]": counts.bracket_close++; break;
      case '"': counts.double_quote++; break;
      case "'": counts.single_quote++; break;
      case "\\": counts.backslash++; break;
      case "<": counts.lt++; break;
      case ">": counts.gt++; break;
    }
  }
  return { first_char_code: firstCharCode, char_class_counts: counts };
}

// Gate 1 (source): only attempt when the upstream gave a clean tool-call
//   termination (finishReason is tool_use or end_turn).  max_tokens means
//   the params are genuinely incomplete — repair would be fabrication.
// Gate 2 (structure): only close unclosed { / [ with } / ], and only when
//   the last token is a complete value.  Reject unterminated strings, keys
//   without values, trailing commas.
// Gate 3 (semantic): if a schema is available, validate required fields
//   are present and top-level type matches.
function tryRepairToolArgs(args, finishReason, schema) {
  const result = { attempted: false, applied: false, gate: null, schema: schema ? "present" : "absent" };

  // Gate 1 — source authorization.
  if (finishReason !== "tool_use" && finishReason !== "end_turn") {
    result.attempted = true;
    result.gate = "gate1_finish";
    return { rejected: "gate1_finish", result };
  }
  result.attempted = true;

  // Gate 2 — structural closure.
  const trimmed = args.trimEnd();
  // Must not be empty or already valid.
  if (!trimmed) {
    result.gate = "gate2_struct";
    return { rejected: "gate2_struct", result };
  }
  // If it already parses, no repair needed.
  try {
    const parsed = JSON.parse(trimmed);
    result.applied = false;
    result.gate = "none";
    return { input: parsed, result };
  } catch { /* fall through to repair attempt */ }

  const closed = closeJsonBrackets(trimmed);
  if (closed === null) {
    result.gate = "gate2_struct";
    return { rejected: "gate2_struct", result };
  }

  let input;
  try {
    input = JSON.parse(closed);
  } catch {
    result.gate = "gate2_struct";
    return { rejected: "gate2_struct", result };
  }

  // Absolutely never repair to {}.
  if (Object.keys(input).length === 0) {
    result.gate = "gate2_struct";
    return { rejected: "gate2_struct", result };
  }

  // Gate 3 — semantic validation against schema.
  if (schema) {
    if (!validateAgainstSchema(input, schema)) {
      result.gate = "gate3_schema";
      return { rejected: "gate3_schema", result };
    }
  }

  result.applied = true;
  result.gate = "repaired";
  return { input, result };
}

// Structural closure: append } / ] for unclosed brackets, but ONLY if the
// last meaningful token is a complete value.  Returns the closed string or
// null if the structure is not safely closeable.
function closeJsonBrackets(str) {
  // Track bracket depth and string state.
  let inString = false;
  let escape = false;
  const stack = [];
  for (let i = 0; i < str.length; i++) {
    const ch = str[i];
    if (escape) { escape = false; continue; }
    if (ch === "\\") { escape = true; continue; }
    if (ch === '"') { inString = !inString; continue; }
    if (inString) continue;
    if (ch === "{" || ch === "[") stack.push(ch);
    if (ch === "}" || ch === "]") stack.pop();
  }

  // If we're inside a string, the string is unterminated — not closeable.
  if (inString) return null;

  // Check the last non-whitespace character to ensure we're not ending
  // mid-token (key without value, trailing comma, trailing colon).
  const lastChar = str.trimEnd().slice(-1);
  if (lastChar === ":" || lastChar === ",") return null;
  // If last char is a quote, we need to check it's a closed string value.
  // The inString check above handles unterminated strings.  A terminated
  // string as the last token (e.g. {"city":"Beijing") is fine.

  // Close all open brackets in reverse order.
  let closed = str.trimEnd();
  while (stack.length > 0) {
    const open = stack.pop();
    closed += (open === "{") ? "}" : "]";
  }
  return closed;
}

// Minimal schema validation: check required fields exist and top-level type.
function validateAgainstSchema(input, schema) {
  if (!schema || typeof schema !== "object") return true;  // no schema = skip
  // Top-level type check.
  if (schema.type === "object" && (typeof input !== "object" || input === null || Array.isArray(input))) return false;
  if (schema.type === "array" && !Array.isArray(input)) return false;
  // Required fields.
  if (Array.isArray(schema.required)) {
    for (const field of schema.required) {
      if (!(field in input)) return false;
    }
  }
  return true;
}

// X3 (PRD RELEASE_V7): deterministic normalization whitelist.
// Each rule is schema-directed, idempotent, and applied one at a time.
// After all rules, the result is re-validated with validateAgainstSchema.
// If re-validation fails, returns null (caller reverts to pre-normalization).
// Ported from the reference implementation's tool_argument_guard, adapted to JS.
function normalizeToolArgs(input, schema) {
  if (!schema || typeof schema !== "object") return input;
  let args = input;

  // R1-wrapper: unwrap {"input": {...}} when input is sole field and inner validates.
  if (args && typeof args === "object" && !Array.isArray(args)) {
    const keys = Object.keys(args);
    if (keys.length === 1 && keys[0] === "input") {
      const inner = args.input;
      if (inner && typeof inner === "object" && !Array.isArray(inner)) {
        if (validateAgainstSchema(inner, schema)) {
          args = inner;
        }
      }
    }
  }

  // R5-remove-unknown: remove fields not in schema.properties when additionalProperties is false.
  if (args && typeof args === "object" && !Array.isArray(args) && schema.additionalProperties === false) {
    const props = schema.properties || {};
    const known = new Set(Object.keys(props));
    for (const key of Object.keys(args)) {
      if (!known.has(key)) {
        delete args[key];
      }
    }
  }

  // R6-null-empty: null → {} when schema type is object and no required fields.
  if (args === null) {
    if (schema.type === "object" && (!Array.isArray(schema.required) || schema.required.length === 0)) {
      args = {};
    }
  }

  // Re-validate after normalization.
  if (!validateAgainstSchema(args, schema)) {
    return null;  // normalization made it worse — caller reverts
  }
  return args;
}

function sse(res, event, data) {
  return res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
}

function makeContentBlock(index, text = "") {
  return { type: "content_block_start", index, content_block: { type: "text", text } };
}

function upstreamHeaders(key, req) {
  const h = { authorization: `Bearer ${key}`, "content-type": "application/json" };
  // Forward test-harness scenario headers to the fake upstream. The real MaaS
  // endpoint ignores unknown headers; this only affects the contract test path.
  const scenario = req && req.headers["x-fake-scenario"];
  if (scenario) h["x-fake-scenario"] = scenario;
  return h;
}

async function proxyNonStreaming(req, res, key, openaiReq) {
  const upstream = await fetch(MAAS_CHAT_URL, {
    method: "POST",
    headers: upstreamHeaders(key, req),
    body: JSON.stringify({ ...openaiReq, stream: false }),
  });
  const text = await upstream.text();
  if (!upstream.ok) {
    res.writeHead(upstream.status, { "content-type": "application/json" });
    res.end(text);
    return;
  }
  sendJson(res, 200, toAnthropicResponse(JSON.parse(text), openaiReq.model));
}

// D1 reaper (PRD RELEASE_CLOSURE_V2): safety net for leaked slots.  Scans
// activeControllers every 30s for entries older than TOTAL_TIMEOUT + 60s.
// Force-fails the controller, releases the slot, and logs MAAS_SLOT_REAPED.
// This is a safety net — the structural fix (try/finally) is the primary
// guarantee.  .unref() so it doesn't block process exit.
const REAPER_INTERVAL_MS = Math.max(1, Number(process.env.MAAS_REAPER_INTERVAL || "30")) * 1000;
const reaperTimer = setInterval(() => {
  const maxAge = TOTAL_TIMEOUT + 60_000;
  const now = Date.now();
  for (const [id, c] of activeControllers) {
    const age = now - c._startedAt;
    if (age > maxAge) {
      if (!c.isTerminal()) {
        c._fail(ErrorCodes.TOTAL_TIMEOUT, State.TOTAL_TIMEOUT);
      }
      activeControllers.delete(id);
      concurrencyGuard.release();
      reapedCount += 1;
      recordError("MAAS_SLOT_REAPED", id);
      console.log(JSON.stringify({
        type: "slot_reaped", request_id: id, age_ms: age,
        code: "MAAS_SLOT_REAPED", ts: new Date().toISOString(),
      }));
    }
  }
}, REAPER_INTERVAL_MS);
reaperTimer.unref();

async function proxyStreaming(req, res, key, openaiReq) {
  // D1 (PRD RELEASE_CLOSURE_V2): cleanup is declared before ctrl so that
  // onTimeout/onClose closures can call it.  It is idempotent (_slotReleased
  // guard) so double-calling from onClose/watchdog + finally is safe.
  let _slotReleased = false;
  let keepaliveTimer = null;  // forward-declared for cleanup; assigned later
  let ctrl = null;
  function cleanup(c) {
    if (keepaliveTimer) { clearTimeout(keepaliveTimer); keepaliveTimer = null; }
    // D4 test hook: skip release AND activeControllers.delete to create an
    // orphan slot for reaper testing.  Only when MAAS_TEST_SKIP_CLEANUP=1.
    // Production never sets this.
    if (process.env.MAAS_TEST_SKIP_CLEANUP === "1") {
      _slotReleased = true;
      if (c) res.removeListener("close", onClose);
      return;
    }
    if (!_slotReleased) { _slotReleased = true; concurrencyGuard.release(); }
    if (c) activeControllers.delete(c.requestId);
    if (c) res.removeListener("close", onClose);
  }

  // D1 (PRD RELEASE_CLOSURE_V3): build a schema map from the request tools
  // for gate-3 semantic validation of repaired tool args.
  // X4 (PRD RELEASE_V7): three-state mode replaces the old boolean kill switch.
  //   off:     no repair, no normalization, hard failure
  //   observe: run full pipeline + record metrics, but still hard-fail (default)
  //   enforce: apply repair, normalization, and safe degradation
  const TOOL_ARG_MODE = process.env.MAAS_TOOL_ARG_MODE || "observe";
  const TOOL_ARG_REPAIR_ENABLED = TOOL_ARG_MODE === "enforce" || TOOL_ARG_MODE === "observe";
  const toolSchemaMap = new Map();
  if (Array.isArray(openaiReq.tools)) {
    for (const t of openaiReq.tools) {
      if (t && t.function && t.function.name) {
        toolSchemaMap.set(t.function.name, t.function.parameters || null);
      }
    }
  }

  ctrl = new RequestLifecycleController({
    connectTimeout: CONNECT_TIMEOUT,
    idleTimeout: IDLE_TIMEOUT,
    totalTimeout: TOTAL_TIMEOUT,
    onTimeout: (code) => {
      lastErrorCode = code;
      recordError(code, ctrl ? ctrl.requestId : null);
      sendSseError(res, code);
      cleanup(ctrl);  // D1: watchdog terminal path releases the slot
    },
    onStateChange: () => {},
  });
  activeControllers.set(ctrl.requestId, ctrl);

  // Concurrency admission — fail before upstream fetch.
  if (!concurrencyGuard.tryAdmit()) {
    activeControllers.delete(ctrl.requestId);
    sendError(res, ErrorCodes.OVER_CAPACITY);
    return;
  }

  // Client disconnect -> abort upstream.
  let clientClosed = false;
  const onClose = () => {
    if (clientClosed) return;
    clientClosed = true;
    ctrl.abort();
    // D3: client abort must leave a trace — record the error code and count.
    clientAbortCount += 1;
    lastErrorCode = ErrorCodes.CLIENT_ABORTED;
    recordError(ErrorCodes.CLIENT_ABORTED, ctrl.requestId);
    cleanup(ctrl);  // D1: client disconnect releases the slot
  };
  res.on("close", onClose);

  // D3: tracking vars for structured terminal log (declared outside try so
  // the finally block can read them).
  let upstreamChunksReceived = 0;
  let clientBytesWritten = 0;
  let lastRepairInfo = null;  // D2: repair metrics for structured log
  let requestDegraded = false;  // D3 V8: true if enforce emitted safe-degradation text this request
  let toolCallIndexAbsent = false;  // D3 V5: upstream omitted index on tool_calls delta
  let toolCallFragments = 0;        // D3 V5: total tool_calls delta fragments received

  try {  // D1: entire body in try/finally — cleanup guaranteed on any path
  ctrl.startConnectTimer();

  let upstream;
  try {
    upstream = await fetch(MAAS_CHAT_URL, {
      method: "POST",
      headers: upstreamHeaders(key, req),
      body: JSON.stringify({ ...openaiReq, stream: true, stream_options: { include_usage: true } }),
      signal: ctrl.abortController.signal,
    });
  } catch (err) {
    if (ctrl.isTerminal()) { return; }
    if (err && err.name === "AbortError") { return; }
    ctrl._fail(ErrorCodes.CONNECT_TIMEOUT, State.CONNECT_TIMEOUT);
    lastErrorCode = ErrorCodes.CONNECT_TIMEOUT;
    recordError(ErrorCodes.CONNECT_TIMEOUT, ctrl.requestId);
    sendError(res, ErrorCodes.CONNECT_TIMEOUT);
    return;
  }

  if (!upstream.ok || !upstream.body) {
    ctrl._fail(ErrorCodes.UPSTREAM_HTTP, State.UPSTREAM_FAILED);
    lastErrorCode = ErrorCodes.UPSTREAM_HTTP;
    recordError(ErrorCodes.UPSTREAM_HTTP, ctrl.requestId);
    const status = upstream.status || 502;
    const tmpl = { type: "api_error", message: "upstream http error" };
    sendJson(res, status, { type: "error", error: { ...tmpl, code: ErrorCodes.UPSTREAM_HTTP } });
    return;
  }

  ctrl.markConnected();

  res.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-cache", connection: "keep-alive" });

  // Time-driven keepalive (PRD TIME_DRIVEN_KEEPALIVE D1).
  // Guarantees a client-visible byte at least every KEEPALIVE_INTERVAL ms,
  // regardless of upstream chunk rate. The block-count heartbeat is an
  // overlay that may fire sooner; this is the floor guarantee.
  const KEEPALIVE_INTERVAL = Math.max(1, Number(process.env.MAAS_KEEPALIVE_INTERVAL || "15")) * 1000;
  const CLIENT_STARVATION_LIMIT = Math.max(1, Number(process.env.MAAS_CLIENT_STARVATION_LIMIT || "60")) * 1000;
  let lastClientByteAt = Date.now();

  // Time-driven keepalive timer (PRD TIME_DRIVEN_KEEPALIVE D1).
  // Self-rescheduling setTimeout: fires exactly KEEPALIVE_INTERVAL after the
  // last client byte.  Every clientWrite() cancels the pending timer and
  // starts a fresh one, so the worst-case gap is INTERVAL + one timer jitter,
  // not 2× INTERVAL as with the old fixed setInterval + elapsed guard.
  //
  // Declared before clientWrite so rescheduleKeepalive is initialized before
  // the first clientWrite call (message_start) — avoids temporal dead zone.
  let keepaliveTimer = null;
  const scheduleKeepalive = () => {
    if (keepaliveTimer) clearTimeout(keepaliveTimer);
    // Indirect reference so the tick resolves at fire time, not schedule time —
    // keepaliveTick is reassigned from a no-op to the real body below.
    keepaliveTimer = setTimeout(() => keepaliveTick(), KEEPALIVE_INTERVAL);
  };
  // keepaliveTick is assigned below (after clientWrite/thinking state exists);
  // scheduleKeepalive only invokes it via setTimeout, so the TDZ is cleared by
  // the time any tick fires.
  let keepaliveTick = () => {};

  // Wrapper around sse() that tracks client byte time for keepalive + starvation.
  // Defined before any use (const is in TDZ before initialization).
  // On every client write it reschedules the keepalive timer so the timer
  // always fires exactly KEEPALIVE_INTERVAL after the last client byte —
  // eliminating the 2× INTERVAL worst-case gap of the old setInterval+guard.
  const clientWrite = (event, data) => {
    lastClientByteAt = Date.now();
    scheduleKeepalive();
    const payload = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
    clientBytesWritten += Buffer.byteLength(payload, "utf8");
    return res.write(payload);
  };

  const messageId = `msg_${Date.now()}`;
  if (ctrl.feedMessageStart()) {
    clientWrite("message_start", {
      type: "message_start",
      message: { id: messageId, type: "message", role: "assistant", content: [], model: openaiReq.model, stop_reason: null, stop_sequence: null, usage: { input_tokens: 0, output_tokens: 0 } },
    });
  }

  let buffer = "";
  let textStarted = false;
  let textIndex = 0;
  let toolIndex = 1;
  let usage = { input_tokens: 0, output_tokens: 0 };
  const toolCalls = new Map();
  let currentToolKey = null;  // D1 V5: key of the call currently being assembled
  const decoder = new TextDecoder();

  // Synthetic thinking block state (PRD THINKING_WAIT_VISIBILITY §2 D1-C).
  // When upstream sends reasoning_content, we emit a synthetic thinking block
  // with placeholder deltas so Claude Code shows "thinking" UI instead of
  // "Waiting for API response". The actual reasoning text is NEVER forwarded.
  //
  // MAAS_THINKING_HEARTBEAT_INTERVAL: emit a delta every N reasoning chunks
  //   (default 3; env-overridable for test tightening — PRD closure D2).
  // MAAS_THINKING_DISABLED: kill switch for mutation testing (PRD closure C2).
  //   When "1", no synthetic thinking blocks are emitted — the adapter reverts
  //   to pre-fix silence. Production must never set this.
  const THINKING_DISABLED = process.env.MAAS_THINKING_DISABLED === "1";
  const THINKING_HEARTBEAT_INTERVAL = Math.max(1, Number(process.env.MAAS_THINKING_HEARTBEAT_INTERVAL || "3"));
  const THINKING_PLACEHOLDER = "·";       // placeholder char (never model text)
  let thinkingStarted = false;
  let thinkingClosed = false;
  let thinkingIndex = 0;
  let reasoningChunkCount = 0;

  const handleData = (payload) => {
    if (!payload || payload === "[DONE]") return;
    // Size limit on a single SSE event.
    if (Buffer.byteLength(payload, "utf8") > MAX_SSE_EVENT_BYTES) {
      ctrl._setProtocolError("sse_event_oversized");
      return;
    }
    let chunk;
    try { chunk = JSON.parse(payload); } catch { return; }

    if (chunk.usage) {
      usage = { input_tokens: chunk.usage.prompt_tokens || usage.input_tokens, output_tokens: chunk.usage.completion_tokens || usage.output_tokens };
      ctrl.recordActivity("usage");
    }

    const choice = chunk.choices?.[0];
    if (!choice) return;
    if (choice.finish_reason) ctrl.recordFinishReason(convertStopReason(choice.finish_reason));

    const delta = choice.delta || {};

    // Reasoning content — count + refresh activity, emit synthetic thinking block.
    if (typeof delta.reasoning_content === "string" && delta.reasoning_content) {
      ctrl.recordReasoning(delta.reasoning_content);

      // Emit synthetic thinking block (PRD D1-C: zero reasoning leakage).
      // Guarded by THINKING_DISABLED for mutation testing (PRD closure C2).
      if (!THINKING_DISABLED && !thinkingStarted) {
        // Assign indices: thinking=0, text=1, tool=2 when thinking present.
        thinkingIndex = 0;
        textIndex = 1;
        toolIndex = 2;
        if (ctrl.feedBlockStart(thinkingIndex, "thinking")) {
          clientWrite("content_block_start", {
            type: "content_block_start",
            index: thinkingIndex,
            content_block: { type: "thinking", thinking: "" },
          });
          thinkingStarted = true;
        }
      }

      // Emit periodic heartbeat thinking_delta (placeholder, not model text).
      reasoningChunkCount += 1;
      if (!THINKING_DISABLED && reasoningChunkCount % THINKING_HEARTBEAT_INTERVAL === 0) {
        if (ctrl.feedBlockDelta(thinkingIndex, "thinking_delta")) {
          clientWrite("content_block_delta", {
            type: "content_block_delta",
            index: thinkingIndex,
            delta: { type: "thinking_delta", thinking: THINKING_PLACEHOLDER },
          });
        }
      }
    }

    if (typeof delta.content === "string" && delta.content) {
      // Close synthetic thinking block before first visible text.
      if (!THINKING_DISABLED && thinkingStarted && !thinkingClosed) {
        if (ctrl.feedBlockStop(thinkingIndex)) {
          clientWrite("content_block_stop", { type: "content_block_stop", index: thinkingIndex });
          thinkingClosed = true;
        }
      }
      if (!textStarted) {
        if (ctrl.feedBlockStart(textIndex, "text")) {
          clientWrite("content_block_start", makeContentBlock(textIndex));
          textStarted = true;
        }
      }
      if (ctrl.feedBlockDelta(textIndex, "text_delta")) {
        clientWrite("content_block_delta", { type: "content_block_delta", index: textIndex, delta: { type: "text_delta", text: delta.content } });
      }
      ctrl.recordVisibleText(delta.content);
    }

    if (Array.isArray(delta.tool_calls)) {
      for (const call of delta.tool_calls) {
        // D3 V5: track whether upstream omits index (root-cause evidence).
        toolCallFragments += 1;
        if (call.index === undefined || call.index === null) toolCallIndexAbsent = true;
        // D1 (PRD RELEASE_CLOSURE_V5): OpenAI streaming semantics.
        // Explicit index wins; a delta with id/name starts a new call;
        // a delta with only arguments continues the current call.
        // The old `call.index ?? toolCalls.size` split one call into N
        // entries when index was absent (size increments per fragment).
        let k;
        if (call.index !== undefined && call.index !== null) {
          k = call.index;
        } else if (call.id || call.function?.name) {
          k = toolCalls.size;              // new call starts
        } else {
          k = currentToolKey;              // continuation of current call
        }
        currentToolKey = k;
        const existing = toolCalls.get(k) || { id: "", name: "", arguments: "" };
        if (call.id) existing.id = call.id;
        if (call.function?.name) existing.name += call.function.name;
        if (call.function?.arguments) {
          existing.arguments += call.function.arguments;
          // Size limit on aggregate tool args.
          if (Buffer.byteLength(existing.arguments, "utf8") > MAX_TOOL_ARGS_BYTES) {
            ctrl._setProtocolError("tool_args_oversized");
          }
        }
        toolCalls.set(k, existing);
        ctrl.recordToolCall();
      }
    }
  };

  // Time-driven keepalive tick body (PRD TIME_DRIVEN_KEEPALIVE D1).
  // Now that thinking state and clientWrite exist, assign the real tick.
  keepaliveTick = () => {
    if (ctrl.isTerminal()) return;
    if (!THINKING_DISABLED && thinkingStarted && !thinkingClosed) {
      if (ctrl.feedBlockDelta(thinkingIndex, "thinking_delta")) {
        clientWrite("content_block_delta", {
          type: "content_block_delta",
          index: thinkingIndex,
          delta: { type: "thinking_delta", thinking: THINKING_PLACEHOLDER },
        });
      }
    } else {
      const pingPayload = 'event: ping\ndata: {"type":"ping"}\n\n';
      res.write(pingPayload);
      clientBytesWritten += Buffer.byteLength(pingPayload, "utf8");
      lastClientByteAt = Date.now();
    }
    // D2: check starvation — if client has been waiting too long even with
    // keepalive, transition to client_starving state for /status visibility.
    if (ctrl.checkStarvation(CLIENT_STARVATION_LIMIT)) {
      ctrl.markStarving();
    }
    // Re-arm for the next window (unless a clientWrite already rescheduled).
    scheduleKeepalive();
  };

  try {
    for await (const chunk of upstream.body) {
      if (ctrl.isTerminal()) break;
      upstreamChunksReceived += 1;
      buffer += decoder.decode(chunk, { stream: true });
      const events = buffer.split(/\r?\n\r?\n/);
      buffer = events.pop() || "";
      for (const event of events) {
        for (const line of event.split(/\r?\n/)) {
          if (line.startsWith("data:")) handleData(line.slice(5).trimStart());
        }
      }
    }
  } catch (err) {
    // Upstream body read error or abort.
  }

  // Test hook (PRD RELEASE_CLOSURE_V2 D2): simulate a throw in the post-stream
  // code path that would skip the sequential cleanup().  This exercises the
  // capacity-leak defect (R1) — the throw is caught by handleMessages' outer
  // catch, but cleanup() is never reached.  Production never sets this.
  // MAAS_TEST_THROW_AFTER_N limits the throw to the first N requests (so
  // saturation tests can leak N slots then send a normal request).
  if (process.env.MAAS_TEST_THROW_AFTER === "for_await") {
    const maxThrows = Number(process.env.MAAS_TEST_THROW_AFTER_N || "999");
    _testThrowCounter += 1;
    if (_testThrowCounter <= maxThrows) {
      throw new Error("test-injected throw after for-await");
    }
  }

  if (ctrl.isTerminal()) { return; }

  // Close synthetic thinking block if still open (e.g. reasoning → tool_use
  // with no visible text, or reasoning → finish).
  if (!THINKING_DISABLED && thinkingStarted && !thinkingClosed && ctrl.feedBlockStop(thinkingIndex)) {
    clientWrite("content_block_stop", { type: "content_block_stop", index: thinkingIndex });
    thinkingClosed = true;
  }

  // Close text block.
  if (textStarted && ctrl.feedBlockStop(textIndex)) {
    clientWrite("content_block_stop", { type: "content_block_stop", index: textIndex });
  }

  // X1 (PRD RELEASE_V7): emit a text block in place of a failed tool call.
  // The tool is NOT executed; the stream continues with stop_reason: end_turn.
  const emitSafeDegradation = (index, toolName) => {
    requestDegraded = true;  // D3 V8: mark this request as degraded for the structured log
    toolArgsDegraded += 1;   // D3 V8: cumulative /status counter
    if (ctrl.feedBlockStart(index, "text")) {
      clientWrite("content_block_start", { type: "content_block_start", index, content_block: { type: "text", text: "" } });
      if (ctrl.feedBlockDelta(index, "text_delta")) {
        clientWrite("content_block_delta", { type: "content_block_delta", index, delta: { type: "text_delta", text: SAFE_DEGRADATION_TEXT } });
      }
      if (ctrl.feedBlockStop(index)) {
        clientWrite("content_block_stop", { type: "content_block_stop", index });
      }
    }
  };

  // Emit tool blocks — parse args safely (never degrade to {}).
  for (const call of toolCalls.values()) {
    let input;
    let repairInfo = null;
    try {
      input = call.arguments ? JSON.parse(call.arguments) : {};
    } catch (err) {
      // D2 (PRD RELEASE_CLOSURE_V4): classify the parse error for diagnostics.
      // NEVER log err.message — the "not_json" class embeds a payload excerpt.
      const rejectClass = classifyParseError(err.message);
      const argsLen = Buffer.byteLength(call.arguments || "", "utf8");
      const shape = computeShapeDiagnostics(call.arguments || "");
      toolArgsRejectClasses[rejectClass] = (toolArgsRejectClasses[rejectClass] || 0) + 1;

      // X2 (PRD RELEASE_V7): detect raw <tool_call markup as args.
      // Classified separately from generic tool_args_malformed.
      const isMarkup = (call.arguments || "").trimStart().startsWith("<tool_call");
      const protocolReason = isMarkup ? "tool_markup_as_args" : "tool_args_malformed";
      if (isMarkup) toolMarkupSeen += 1;

      // X4 (PRD RELEASE_V7): three-state mode.
      // off:     hard-fail immediately, no repair.
      // observe: run repair pipeline + record metrics, but still hard-fail.
      // enforce: apply repair; if repair fails, safe-degrade (X1).
      if (TOOL_ARG_MODE === "off") {
        lastRepairInfo = { attempted: false, gate: null, schema: "absent", reject_class: rejectClass, args_len: argsLen, first_char_code: shape.first_char_code, char_class_counts: shape.char_class_counts, mode: "off" };
        ctrl._setProtocolError(protocolReason);
        break;
      }

      // observe or enforce: run the repair pipeline.
      const schema = toolSchemaMap.get(call.name) || null;
      const repair = tryRepairToolArgs(call.arguments || "", ctrl.finishReason, schema);
      repairInfo = repair.result;
      repairInfo.reject_class = rejectClass;
      repairInfo.args_len = argsLen;
      repairInfo.first_char_code = shape.first_char_code;
      repairInfo.char_class_counts = shape.char_class_counts;
      repairInfo.mode = TOOL_ARG_MODE;
      repairInfo.is_markup = isMarkup;
      lastRepairInfo = repairInfo;

      if (repair.input !== undefined && !repair.rejected) {
        // Repair succeeded.
        if (TOOL_ARG_MODE === "enforce") {
          input = repair.input;
          toolArgsRepaired += 1;
          // Continue to tool_use emission below.
        } else {
          // observe: record that repair WOULD have worked, but still hard-fail.
          toolArgsRepairRejected["observe_would_repair"] = (toolArgsRepairRejected["observe_would_repair"] || 0) + 1;
          ctrl._setProtocolError(protocolReason);
          break;
        }
      } else {
        // Repair rejected.
        toolArgsRepairRejected[repair.rejected] = (toolArgsRepairRejected[repair.rejected] || 0) + 1;
        if (TOOL_ARG_MODE === "enforce") {
          // X1: safe degradation — emit a text block, don't fail the stream.
          emitSafeDegradation(toolIndex, call.name);
          toolIndex += 1;
          // Override stop_reason: no tool was executed, so end_turn not tool_use.
          ctrl.finishReason = "end_turn";
          // Don't set protocolError — the stream continues normally.
          // Record the degradation for metrics.
          toolArgsRepairRejected["degraded"] = (toolArgsRepairRejected["degraded"] || 0) + 1;
        } else {
          // observe: hard-fail as before.
          ctrl._setProtocolError(protocolReason);
        }
        break;
      }
    }
    if (ctrl.protocolError) break;
    // X3 (PRD RELEASE_V7): normalize parsed input against schema.
    // If normalization makes it invalid, revert and degrade (enforce) or fail (observe).
    if (TOOL_ARG_MODE === "enforce" || TOOL_ARG_MODE === "observe") {
      const schema = toolSchemaMap.get(call.name) || null;
      if (schema && input !== undefined) {
        const normalized = normalizeToolArgs(input, schema);
        if (normalized === null) {
          // Normalization failed re-validation.
          if (TOOL_ARG_MODE === "enforce") {
            emitSafeDegradation(toolIndex, call.name);
            toolIndex += 1;
            ctrl.finishReason = "end_turn";
            toolArgsRepairRejected["normalize_failed"] = (toolArgsRepairRejected["normalize_failed"] || 0) + 1;
            break;
          } else {
            ctrl._setProtocolError(protocolReason);
            break;
          }
        }
        if (TOOL_ARG_MODE === "enforce") {
          input = normalized;
        }
      }
    }
    if (ctrl.feedBlockStart(toolIndex, "tool_use")) {
      clientWrite("content_block_start", { type: "content_block_start", index: toolIndex, content_block: { type: "tool_use", id: call.id || `toolu_${toolIndex}`, name: call.name, input: {} } });
      if (ctrl.feedBlockDelta(toolIndex, "input_json_delta")) {
        clientWrite("content_block_delta", { type: "content_block_delta", index: toolIndex, delta: { type: "input_json_delta", partial_json: JSON.stringify(input) } });
      }
      if (ctrl.feedBlockStop(toolIndex)) {
        clientWrite("content_block_stop", { type: "content_block_stop", index: toolIndex });
      }
      toolIndex += 1;
    }
  }

  // Finalize — synthesize terminals only if a trustworthy finish reason exists.
  const extra = ctrl.finalize();
  if (extra) {
    for (const evt of extra) {
      if (evt.type === "content_block_stop") clientWrite("content_block_stop", { type: "content_block_stop", index: evt.index });
      else if (evt.type === "message_delta") clientWrite("message_delta", { type: "message_delta", delta: evt.delta, usage });
      else if (evt.type === "message_stop") clientWrite("message_stop", { type: "message_stop" });
    }
  }

  if (ctrl.state === State.COMPLETED) {
    lastSuccessAt = Date.now();
  } else if (ctrl.errorCode) {
    lastErrorCode = ctrl.errorCode;
    recordError(ctrl.errorCode, ctrl.requestId);
    if (!res.writableEnded) sendSseError(res, ctrl.errorCode);
  }

  if (!res.writableEnded) res.end();
  } finally {  // D1: cleanup always runs, even on throw or early return
    // D3: structured terminal log (journald captures stdout+stderr).
    // fs.writeSync(2, ...) bypasses Node's stream buffering — the line
    // appears immediately in the pipe, not only on process exit.
    fs.writeSync(2, JSON.stringify({
      type: "request_end",
      request_id: ctrl.requestId,
      state: ctrl.state,
      error_code: ctrl.errorCode || null,
      protocol_error_reason: ctrl.protocolErrorReason || null,
      duration_ms: Date.now() - ctrl._startedAt,
      outcome: ctrl.metrics.outcome || null,
      upstream_chunks: upstreamChunksReceived || 0,
      client_bytes: clientBytesWritten || 0,
      tool_call_index_absent: toolCallIndexAbsent,
      tool_call_fragments: toolCallFragments,
      degraded: requestDegraded,  // D3 V8: true iff enforce emitted safe-degradation text
      repair: lastRepairInfo,
    }) + "\n");
    cleanup(ctrl);
  }
}

function toAnthropicResponse(openai, model) {
  const choice = openai.choices?.[0] || {};
  const message = choice.message || {};
  const content = [];
  if (typeof message.content === "string" && message.content) content.push({ type: "text", text: message.content });
  if (Array.isArray(message.tool_calls)) {
    for (const call of message.tool_calls) {
      let input = {};
      try { input = JSON.parse(call.function?.arguments || "{}"); } catch { input = {}; }
      content.push({ type: "tool_use", id: call.id, name: call.function?.name || "", input });
    }
  }
  return {
    id: openai.id || `msg_${Date.now()}`,
    type: "message",
    role: "assistant",
    model: openai.model || model,
    content,
    stop_reason: convertStopReason(choice.finish_reason),
    stop_sequence: null,
    usage: { input_tokens: openai.usage?.prompt_tokens || 0, output_tokens: openai.usage?.completion_tokens || 0 },
  };
}

async function handleMessages(req, res) {
  const key = getAuthKey(req);
  if (!key) {
    sendJson(res, 401, { type: "error", error: { type: "authentication_error", message: "missing API key" } });
    return;
  }
  let body;
  try { body = JSON.parse(await readBody(req) || "{}"); } catch {
    sendJson(res, 400, { type: "error", error: { type: "invalid_request_error", message: "invalid JSON body" } });
    return;
  }
  const openaiReq = toOpenAIRequest(body);
  try {
    if (body.stream === true) {
      await proxyStreaming(req, res, key, openaiReq);
    } else {
      await proxyNonStreaming(req, res, key, openaiReq);
    }
  } catch (err) {
    if (!res.headersSent) sendError(res, ErrorCodes.UPSTREAM_HTTP);
  }
}

function statusSnapshot() {
  const stateCounts = {};
  let oldestAge = 0;
  for (const ctrl of activeControllers.values()) {
    stateCounts[ctrl.state] = (stateCounts[ctrl.state] || 0) + 1;
    const age = Date.now() - ctrl._startedAt;
    if (age > oldestAge) oldestAge = age;
  }
  return {
    version: ADAPTER_VERSION,
    uptime_ms: Date.now() - startedAt,
    active_requests: activeControllers.size,
    peak_concurrency: concurrencyGuard.peak,
    state_counts: stateCounts,
    oldest_active_age_ms: oldestAge,
    last_success_at: lastSuccessAt,
    last_error_code: lastErrorCode,
    client_aborts: clientAbortCount,
    error_counts: errorCounts,
    recent_errors: recentErrors.slice(),   // copy, newest last
    reaped_slots: reapedCount,
    tool_args_repaired: toolArgsRepaired,
    tool_args_repair_rejected: { ...toolArgsRepairRejected },
    tool_args_reject_classes: { ...toolArgsRejectClasses },
    tool_args_degraded: toolArgsDegraded,  // D3 V8: requests degraded by enforce safe-degradation
    tool_markup_seen: toolMarkupSeen,
    timeout_config: { connect_ms: CONNECT_TIMEOUT, idle_ms: IDLE_TIMEOUT, total_ms: TOTAL_TIMEOUT },
    capacity: MAX_CONCURRENCY,
    thinking_visibility: process.env.MAAS_THINKING_DISABLED === "1" ? "disabled" : "enabled",
  };
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || `${HOST}:${PORT}`}`);
  if (req.method === "GET" && (url.pathname === "/" || url.pathname === "/health")) {
    sendJson(res, 200, { status: "ok", model: DEFAULT_MODEL });
    return;
  }
  if (req.method === "GET" && url.pathname === "/status") {
    // Loopback-only, fail-closed for unknown/missing peer.
    if (!isLoopback(req.socket.remoteAddress)) {
      sendJson(res, 403, { error: "forbidden" });
      return;
    }
    sendJson(res, 200, statusSnapshot());
    return;
  }
  if (req.method === "POST" && url.pathname === "/v1/messages") {
    await handleMessages(req, res);
    return;
  }
  sendJson(res, 404, { error: "not found" });
});

server.listen(PORT, HOST, () => {
  console.log(`claude-code-maas adapter listening on http://${HOST}:${PORT} -> ${MAAS_CHAT_URL} (model: ${DEFAULT_MODEL})`);
  if (process.env.MAAS_THINKING_DISABLED === "1") {
    console.log("WARNING: MAAS_THINKING_DISABLED=1 — synthetic thinking blocks are suppressed (test/kill-switch mode; production must never set this)");
  }
});
