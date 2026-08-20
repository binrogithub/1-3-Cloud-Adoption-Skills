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
const IDLE_TIMEOUT = Number(process.env.MAAS_IDLE_TIMEOUT || "180") * 1000;
const TOTAL_TIMEOUT = Number(process.env.MAAS_TOTAL_TIMEOUT || "600") * 1000;
const MAX_CONCURRENCY = Number(process.env.MAAS_MAX_CONCURRENCY || "8");
const MAX_TOOL_ARGS_BYTES = Number(process.env.MAAS_MAX_TOOL_ARGS_BYTES || "262144");
const MAX_SSE_EVENT_BYTES = Number(process.env.MAAS_MAX_SSE_EVENT_BYTES || "1048576");
const MAX_REQUEST_BODY_BYTES = Number(process.env.MAAS_MAX_REQUEST_BODY_BYTES || "10485760");
const ADAPTER_VERSION = "stream-reliability-v2";

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
const startedAt = Date.now();

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

async function proxyStreaming(req, res, key, openaiReq) {
  const ctrl = new RequestLifecycleController({
    connectTimeout: CONNECT_TIMEOUT,
    idleTimeout: IDLE_TIMEOUT,
    totalTimeout: TOTAL_TIMEOUT,
    onTimeout: (code) => {
      lastErrorCode = code;
      sendSseError(res, code);
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
  };
  res.on("close", onClose);

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
    if (ctrl.isTerminal()) { cleanup(ctrl); return; }
    if (err && err.name === "AbortError") { cleanup(ctrl); return; }
    ctrl._fail(ErrorCodes.CONNECT_TIMEOUT, State.CONNECT_TIMEOUT);
    lastErrorCode = ErrorCodes.CONNECT_TIMEOUT;
    sendError(res, ErrorCodes.CONNECT_TIMEOUT);
    cleanup(ctrl);
    return;
  }

  if (!upstream.ok || !upstream.body) {
    ctrl._fail(ErrorCodes.UPSTREAM_HTTP, State.UPSTREAM_FAILED);
    lastErrorCode = ErrorCodes.UPSTREAM_HTTP;
    const status = upstream.status || 502;
    const tmpl = { type: "api_error", message: "upstream http error" };
    sendJson(res, status, { type: "error", error: { ...tmpl, code: ErrorCodes.UPSTREAM_HTTP } });
    cleanup(ctrl);
    return;
  }

  ctrl.markConnected();

  res.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-cache", connection: "keep-alive" });

  const messageId = `msg_${Date.now()}`;
  if (ctrl.feedMessageStart()) {
    sse(res, "message_start", {
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
      ctrl.protocolError = true;
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
          sse(res, "content_block_start", {
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
          sse(res, "content_block_delta", {
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
          sse(res, "content_block_stop", { type: "content_block_stop", index: thinkingIndex });
          thinkingClosed = true;
        }
      }
      if (!textStarted) {
        if (ctrl.feedBlockStart(textIndex, "text")) {
          sse(res, "content_block_start", makeContentBlock(textIndex));
          textStarted = true;
        }
      }
      if (ctrl.feedBlockDelta(textIndex, "text_delta")) {
        sse(res, "content_block_delta", { type: "content_block_delta", index: textIndex, delta: { type: "text_delta", text: delta.content } });
      }
      ctrl.recordVisibleText(delta.content);
    }

    if (Array.isArray(delta.tool_calls)) {
      for (const call of delta.tool_calls) {
        const k = call.index ?? toolCalls.size;
        const existing = toolCalls.get(k) || { id: "", name: "", arguments: "" };
        if (call.id) existing.id = call.id;
        if (call.function?.name) existing.name += call.function.name;
        if (call.function?.arguments) {
          existing.arguments += call.function.arguments;
          // Size limit on aggregate tool args.
          if (Buffer.byteLength(existing.arguments, "utf8") > MAX_TOOL_ARGS_BYTES) {
            ctrl.protocolError = true;
          }
        }
        toolCalls.set(k, existing);
        ctrl.recordToolCall();
      }
    }
  };

  try {
    for await (const chunk of upstream.body) {
      if (ctrl.isTerminal()) break;
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

  if (ctrl.isTerminal()) { cleanup(ctrl); return; }

  // Close synthetic thinking block if still open (e.g. reasoning → tool_use
  // with no visible text, or reasoning → finish).
  if (!THINKING_DISABLED && thinkingStarted && !thinkingClosed && ctrl.feedBlockStop(thinkingIndex)) {
    sse(res, "content_block_stop", { type: "content_block_stop", index: thinkingIndex });
    thinkingClosed = true;
  }

  // Close text block.
  if (textStarted && ctrl.feedBlockStop(textIndex)) {
    sse(res, "content_block_stop", { type: "content_block_stop", index: textIndex });
  }

  // Emit tool blocks — parse args safely (never degrade to {}).
  for (const call of toolCalls.values()) {
    let input;
    try {
      input = call.arguments ? JSON.parse(call.arguments) : {};
    } catch {
      // Malformed tool args — protocol error, never execute {}.
      ctrl.protocolError = true;
      break;
    }
    if (ctrl.protocolError) break;
    if (ctrl.feedBlockStart(toolIndex, "tool_use")) {
      sse(res, "content_block_start", { type: "content_block_start", index: toolIndex, content_block: { type: "tool_use", id: call.id || `toolu_${toolIndex}`, name: call.name, input: {} } });
      if (ctrl.feedBlockDelta(toolIndex, "input_json_delta")) {
        sse(res, "content_block_delta", { type: "content_block_delta", index: toolIndex, delta: { type: "input_json_delta", partial_json: JSON.stringify(input) } });
      }
      if (ctrl.feedBlockStop(toolIndex)) {
        sse(res, "content_block_stop", { type: "content_block_stop", index: toolIndex });
      }
      toolIndex += 1;
    }
  }

  // Finalize — synthesize terminals only if a trustworthy finish reason exists.
  const extra = ctrl.finalize();
  if (extra) {
    for (const evt of extra) {
      if (evt.type === "content_block_stop") sse(res, "content_block_stop", { type: "content_block_stop", index: evt.index });
      else if (evt.type === "message_delta") sse(res, "message_delta", { type: "message_delta", delta: evt.delta, usage });
      else if (evt.type === "message_stop") sse(res, "message_stop", { type: "message_stop" });
    }
  }

  if (ctrl.state === State.COMPLETED) {
    lastSuccessAt = Date.now();
  } else if (ctrl.errorCode) {
    lastErrorCode = ctrl.errorCode;
    if (!res.writableEnded) sendSseError(res, ctrl.errorCode);
  }

  if (!res.writableEnded) res.end();
  cleanup(ctrl);

  function cleanup(c) {
    concurrencyGuard.release();
    activeControllers.delete(c.requestId);
    res.removeListener("close", onClose);
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
