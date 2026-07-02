#!/usr/bin/env node
"use strict";

const http = require("node:http");
const fs = require("node:fs");

const ENV_FILE = process.env.ENV_FILE || "/root/LiteLLM/.env";
loadEnvFile(ENV_FILE);

const HOST = process.env.ADAPTER_HOST || "127.0.0.1";
const PORT = Number(process.env.ADAPTER_PORT || "4010");
const LITELLM_CHAT_URL =
  process.env.LITELLM_CHAT_URL || "http://127.0.0.1:4000/v1/chat/completions";
const DEFAULT_KEY = process.env.LITELLM_ANTHROPIC_KEY || process.env.LITELLM_CCR_KEY;
const DEFAULT_MODEL = process.env.ADAPTER_DEFAULT_MODEL || "claude-opus-4-6";

function loadEnvFile(path) {
  if (!fs.existsSync(path)) return;
  const lines = fs.readFileSync(path, "utf8").split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match || process.env[match[1]]) continue;
    let value = match[2].trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    process.env[match[1]] = value;
  }
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = "";
    req.setEncoding("utf8");
    req.on("data", (chunk) => {
      body += chunk;
      if (body.length > 50 * 1024 * 1024) {
        reject(new Error("request body too large"));
        req.destroy();
      }
    });
    req.on("end", () => resolve(body));
    req.on("error", reject);
  });
}

function sendJson(res, status, payload) {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(payload));
}

function getAuthKey(req) {
  const xApiKey = req.headers["x-api-key"];
  if (typeof xApiKey === "string" && xApiKey.trim() && !xApiKey.trim().startsWith("$")) {
    return xApiKey.trim();
  }
  const auth = req.headers.authorization || "";
  const match = String(auth).match(/^Bearer\s+(.+)$/i);
  if (match) {
    const key = match[1].trim();
    if (key && !key.startsWith("$")) return key;
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
  return content
    .filter((item) => item && item.type === "text" && typeof item.text === "string")
    .map((item) => item.text)
    .join("\n");
}

function normalizeToolResultContent(content) {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .map((item) => {
      if (!item) return "";
      if (item.type === "text" && typeof item.text === "string") return item.text;
      if (typeof item.content === "string") return item.content;
      return "";
    })
    .filter(Boolean)
    .join("\n");
}

function anthropicMessagesToOpenAI(messages = []) {
  const out = [];
  for (const message of messages) {
    if (!message || !message.role) continue;

    if (typeof message.content === "string") {
      out.push({ role: message.role, content: message.content });
      continue;
    }

    if (!Array.isArray(message.content)) {
      out.push({ role: message.role, content: "" });
      continue;
    }

    if (message.role === "user") {
      const textParts = [];
      for (const item of message.content) {
        if (!item) continue;
        if (item.type === "tool_result") {
          out.push({
            role: "tool",
            tool_call_id: item.tool_use_id,
            content: normalizeToolResultContent(item.content),
          });
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
        if (item.type === "text" && typeof item.text === "string") {
          textParts.push(item.text);
        } else if (item.type === "tool_use") {
          toolCalls.push({
            id: item.id,
            type: "function",
            function: {
              name: item.name,
              arguments: JSON.stringify(item.input || {}),
            },
          });
        }
      }
      const openaiMessage = {
        role: "assistant",
        content: textParts.join("\n") || null,
      };
      if (toolCalls.length) openaiMessage.tool_calls = toolCalls;
      out.push(openaiMessage);
    }
  }
  return out;
}

function anthropicToolsToOpenAI(tools = []) {
  if (!Array.isArray(tools)) return undefined;
  const converted = tools
    .filter((tool) => tool && tool.name)
    .map((tool) => ({
      type: "function",
      function: {
        name: tool.name,
        description: tool.description || "",
        parameters: tool.input_schema || {
          type: "object",
          properties: {},
          additionalProperties: true,
        },
      },
    }));
  return converted.length ? converted : undefined;
}

function toOpenAIRequest(body) {
  stripClaudeOnly(body);
  const openai = {
    model: body.model || DEFAULT_MODEL,
    messages: [],
    max_tokens: body.max_tokens,
    temperature: body.temperature,
    top_p: body.top_p,
    stream: body.stream === true,
  };

  if (body.system) {
    openai.messages.push({ role: "system", content: textFromContent(body.system) });
  }
  addToolUseGuardrails(openai.messages, body.tools);
  openai.messages.push(...anthropicMessagesToOpenAI(body.messages || []));

  const tools = anthropicToolsToOpenAI(body.tools);
  if (tools) {
    openai.tools = tools;
    if (body.tool_choice) openai.tool_choice = convertToolChoice(body.tool_choice);
  }

  for (const key of Object.keys(openai)) {
    if (openai[key] === undefined || openai[key] === null) delete openai[key];
  }
  return openai;
}

function addToolUseGuardrails(messages, tools) {
  if (!Array.isArray(tools) || !tools.length) return;
  const toolNames = new Set(tools.map((tool) => tool && tool.name).filter(Boolean));
  const parts = [];

  if (toolNames.has("Bash")) {
    parts.push(
      "When calling Bash, the function arguments must be a JSON object with a non-empty string field named command. Include the full shell command in command. Never call Bash with {}."
    );
  }
  if (toolNames.has("Read")) {
    parts.push(
      "When calling Read, the function arguments must include file_path as an absolute path string. Never call Read with {}."
    );
  }
  if (toolNames.has("Write")) {
    parts.push(
      "When calling Write, the function arguments must include file_path and content strings. Never call Write with {}."
    );
  }
  if (toolNames.has("Edit")) {
    parts.push(
      "When calling Edit, the function arguments must include file_path, old_string, and new_string strings. Never call Edit with {}."
    );
  }
  if (!parts.length) return;

  messages.push({
    role: "system",
    content: [
      "Tool-call argument rules:",
      ...parts,
      "If you do not know the exact required arguments, ask a short question or explain the next step in text instead of calling the tool.",
    ].join("\n"),
  });
}

function convertToolChoice(toolChoice) {
  if (toolChoice === "auto" || toolChoice?.type === "auto") return "auto";
  if (toolChoice?.type === "any") return "required";
  if (toolChoice?.type === "tool" && toolChoice.name) {
    return { type: "function", function: { name: toolChoice.name } };
  }
  return "auto";
}

function toolUseBlocks(toolCalls = []) {
  return toolCalls.map((call) => {
    let input = {};
    try {
      input = JSON.parse(call.function?.arguments || "{}");
    } catch {
      input = {};
    }
    return {
      type: "tool_use",
      id: call.id,
      name: call.function?.name || "",
      input,
    };
  });
}

function toAnthropicResponse(openai, model) {
  const choice = openai.choices?.[0] || {};
  const message = choice.message || {};
  const content = [];
  if (typeof message.content === "string" && message.content) {
    content.push({ type: "text", text: message.content });
  }
  if (Array.isArray(message.tool_calls)) {
    content.push(...toolUseBlocks(message.tool_calls));
  }
  return {
    id: openai.id || `msg_${Date.now()}`,
    type: "message",
    role: "assistant",
    model: openai.model || model,
    content,
    stop_reason: convertStopReason(choice.finish_reason),
    stop_sequence: null,
    usage: {
      input_tokens: openai.usage?.prompt_tokens || 0,
      output_tokens: openai.usage?.completion_tokens || 0,
    },
  };
}

function convertStopReason(reason) {
  if (reason === "tool_calls") return "tool_use";
  if (reason === "length") return "max_tokens";
  if (reason === "stop") return "end_turn";
  return reason || "end_turn";
}

function sse(res, event, data) {
  res.write(`event: ${event}\n`);
  res.write(`data: ${JSON.stringify(data)}\n\n`);
}

function makeContentBlock(index, text = "") {
  return { type: "content_block_start", index, content_block: { type: "text", text } };
}

async function proxyNonStreaming(res, key, openaiReq) {
  const upstream = await fetch(LITELLM_CHAT_URL, {
    method: "POST",
    headers: {
      authorization: `Bearer ${key}`,
      "content-type": "application/json",
    },
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

async function proxyStreaming(res, key, openaiReq) {
  const upstream = await fetch(LITELLM_CHAT_URL, {
    method: "POST",
    headers: {
      authorization: `Bearer ${key}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({
      ...openaiReq,
      stream: true,
      stream_options: { include_usage: true },
    }),
  });

  if (!upstream.ok || !upstream.body) {
    const text = await upstream.text();
    res.writeHead(upstream.status, { "content-type": "application/json" });
    res.end(text);
    return;
  }

  res.writeHead(200, {
    "content-type": "text/event-stream",
    "cache-control": "no-cache",
    connection: "keep-alive",
  });

  const messageId = `msg_${Date.now()}`;
  sse(res, "message_start", {
    type: "message_start",
    message: {
      id: messageId,
      type: "message",
      role: "assistant",
      content: [],
      model: openaiReq.model,
      stop_reason: null,
      stop_sequence: null,
      usage: { input_tokens: 0, output_tokens: 0 },
    },
  });

  let buffer = "";
  let textStarted = false;
  let textIndex = 0;
  let toolIndex = 1;
  let finishReason = "end_turn";
  let usage = { input_tokens: 0, output_tokens: 0 };
  const toolCalls = new Map();
  const decoder = new TextDecoder();

  const handleData = (payload) => {
    if (!payload || payload === "[DONE]") return;
    let chunk;
    try {
      chunk = JSON.parse(payload);
    } catch {
      return;
    }

    if (chunk.usage) {
      usage = {
        input_tokens: chunk.usage.prompt_tokens || usage.input_tokens,
        output_tokens: chunk.usage.completion_tokens || usage.output_tokens,
      };
    }

    const choice = chunk.choices?.[0];
    if (!choice) return;
    if (choice.finish_reason) finishReason = convertStopReason(choice.finish_reason);

    const delta = choice.delta || {};
    if (typeof delta.content === "string" && delta.content) {
      if (!textStarted) {
        sse(res, "content_block_start", makeContentBlock(textIndex));
        textStarted = true;
      }
      sse(res, "content_block_delta", {
        type: "content_block_delta",
        index: textIndex,
        delta: { type: "text_delta", text: delta.content },
      });
    }

    if (Array.isArray(delta.tool_calls)) {
      for (const call of delta.tool_calls) {
        const key = call.index ?? toolCalls.size;
        const existing = toolCalls.get(key) || {
          id: "",
          name: "",
          arguments: "",
        };
        if (call.id) existing.id = call.id;
        if (call.function?.name) existing.name += call.function.name;
        if (call.function?.arguments) existing.arguments += call.function.arguments;
        toolCalls.set(key, existing);
      }
    }
  };

  for await (const chunk of upstream.body) {
    buffer += decoder.decode(chunk, { stream: true });
    const events = buffer.split(/\r?\n\r?\n/);
    buffer = events.pop() || "";
    for (const event of events) {
      for (const line of event.split(/\r?\n/)) {
        if (line.startsWith("data:")) handleData(line.slice(5).trimStart());
      }
    }
  }

  if (textStarted) {
    sse(res, "content_block_stop", { type: "content_block_stop", index: textIndex });
  }
  for (const call of toolCalls.values()) {
    let input = {};
    try {
      input = call.arguments ? JSON.parse(call.arguments) : {};
    } catch {
      input = {};
    }
    sse(res, "content_block_start", {
      type: "content_block_start",
      index: toolIndex,
      content_block: {
        type: "tool_use",
        id: call.id || `toolu_${toolIndex}`,
        name: call.name,
        input: {},
      },
    });
    sse(res, "content_block_delta", {
      type: "content_block_delta",
      index: toolIndex,
      delta: {
        type: "input_json_delta",
        partial_json: JSON.stringify(input),
      },
    });
    sse(res, "content_block_stop", {
      type: "content_block_stop",
      index: toolIndex,
    });
    toolIndex += 1;
  }
  sse(res, "message_delta", {
    type: "message_delta",
    delta: { stop_reason: finishReason, stop_sequence: null },
    usage,
  });
  sse(res, "message_stop", { type: "message_stop" });
  res.end();
}

async function handleMessages(req, res) {
  const key = getAuthKey(req);
  if (!key) {
    sendJson(res, 401, {
      type: "error",
      error: { type: "authentication_error", message: "missing API key" },
    });
    return;
  }

  let body;
  try {
    body = JSON.parse(await readBody(req) || "{}");
  } catch {
    sendJson(res, 400, {
      type: "error",
      error: { type: "invalid_request_error", message: "invalid JSON body" },
    });
    return;
  }

  const openaiReq = toOpenAIRequest(body);
  try {
    if (body.stream === true) {
      await proxyStreaming(res, key, openaiReq);
    } else {
      await proxyNonStreaming(res, key, openaiReq);
    }
  } catch (err) {
    sendJson(res, 502, {
      type: "error",
      error: {
        type: "api_error",
        message: err && err.message ? err.message : "upstream error",
      },
    });
  }
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || `${HOST}:${PORT}`}`);
  if (req.method === "GET" && (url.pathname === "/" || url.pathname === "/health")) {
    sendJson(res, 200, { status: "ok", upstream: LITELLM_CHAT_URL });
    return;
  }
  if (req.method === "POST" && url.pathname === "/v1/messages") {
    await handleMessages(req, res);
    return;
  }
  sendJson(res, 404, { error: "not found" });
});

server.listen(PORT, HOST, () => {
  console.log(`litellm anthropic adapter listening on http://${HOST}:${PORT}`);
});
