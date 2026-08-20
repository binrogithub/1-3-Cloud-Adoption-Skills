"use strict";
// fake_upstream.js — deterministic MaaS-shaped upstream for adapter contract tests.
//
// Listens on loopback. Accepts POST /v1/chat/completions and produces scripted
// SSE streams based on the "scenario" query param or a request header.
// Supports the full fault matrix from PRD §Testing B.

const http = require("node:http");

const argv = process.argv.slice(2);
let port = 0;
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === "--port" && argv[i + 1]) port = Number(argv[i + 1]);
}
if (!port) { console.error("fake_upstream: --port required"); process.exit(1); }

function sseChunk(event, data) {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

// OpenAI-style SSE chunk.
function openaiChunk(opts) {
  const chunk = { id: "chatcmpl-test", object: "chat.completion.chunk", created: 1, model: "glm-5.2", choices: [{ index: 0, delta: {}, finish_reason: null }] };
  if (opts.delta) chunk.choices[0].delta = opts.delta;
  if (opts.finish_reason) chunk.choices[0].finish_reason = opts.finish_reason;
  if (opts.usage) chunk.usage = opts.usage;
  return `data: ${JSON.stringify(chunk)}\n\n`;
}

const scenarios = {
  // Normal reasoning then text then finish.
  reasoning_then_text(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    res.write(openaiChunk({ delta: { reasoning_content: "thinking step 1" } }));
    res.write(openaiChunk({ delta: { reasoning_content: "thinking step 2" } }));
    res.write(openaiChunk({ delta: { content: "Hello" } }));
    res.write(openaiChunk({ finish_reason: "stop", usage: { prompt_tokens: 10, completion_tokens: 5 } }));
    res.end("data: [DONE]\n\n");
  },

  // Long reasoning (12 chunks) with high-entropy canary, then text.
  // Used by C2/C3 tests: enough chunks to cross the heartbeat interval,
  // and the canary must NEVER appear in client SSE (zero leakage).
  reasoning_long(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    // High-entropy canary injected into reasoning_content. If the adapter
    // leaks reasoning, this string will appear in the client SSE body.
    const canary = "CANARY-7f3a9c2e1b8d4f60-xyzzy-plugh";
    for (let i = 0; i < 12; i++) {
      res.write(openaiChunk({ delta: { reasoning_content: `${canary} step ${i + 1}` } }));
    }
    res.write(openaiChunk({ delta: { content: "Done." } }));
    res.write(openaiChunk({ finish_reason: "stop", usage: { prompt_tokens: 10, completion_tokens: 5 } }));
    res.end("data: [DONE]\n\n");
  },

  // Reasoning with a 300ms upstream first-byte delay. Used by C4 test to
  // measure adapter overhead relative to upstream first byte (not absolute).
  reasoning_delayed(res) {
    setTimeout(() => {
      res.writeHead(200, { "content-type": "text/event-stream" });
      res.write(openaiChunk({ delta: { reasoning_content: "delayed thinking" } }));
      res.write(openaiChunk({ delta: { content: "OK" } }));
      res.write(openaiChunk({ finish_reason: "stop", usage: { prompt_tokens: 5, completion_tokens: 2 } }));
      res.end("data: [DONE]\n\n");
    }, 300);
  },

  // Headers then permanent silence (never ends the stream).
  silence(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    // Write nothing; never end. The adapter must idle-timeout.
  },

  // Continuous reasoning past total timeout.
  continuous_reasoning(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    const iv = setInterval(() => {
      try { res.write(openaiChunk({ delta: { reasoning_content: "thinking..." } })); } catch {}
    }, 20);
    res.on("close", () => clearInterval(iv));
  },

  // EOF before any finish reason (premature).
  eof_no_finish(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    res.write(openaiChunk({ delta: { content: "partial" } }));
    res.end(); // no finish_reason, no [DONE]
  },

  // Finish reason but missing local terminal events (adapter must synthesize).
  finish_missing_terminals(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    res.write(openaiChunk({ delta: { content: "Hi" } }));
    res.write(openaiChunk({ finish_reason: "stop" }));
    res.end(); // no [DONE] — adapter finalizes
  },

  // Tool call with valid args.
  tool_valid(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    res.write(openaiChunk({ delta: { tool_calls: [{ index: 0, id: "call_1", function: { name: "get_weather", arguments: '{"city":"Tokyo"}' } }] } }));
    res.write(openaiChunk({ finish_reason: "tool_calls" }));
    res.end("data: [DONE]\n\n");
  },

  // Tool call with malformed JSON args (must NOT degrade to {}).
  tool_malformed(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    res.write(openaiChunk({ delta: { tool_calls: [{ index: 0, id: "call_1", function: { name: "get_weather", arguments: '{"city":' } }] } }));
    res.write(openaiChunk({ finish_reason: "tool_calls" }));
    res.end("data: [DONE]\n\n");
  },

  // Upstream HTTP error.
  http_error(res, status) {
    res.writeHead(status || 500, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: { message: "upstream error" } }));
  },

  // 429 with Retry-After.
  rate_limited(res) {
    res.writeHead(429, { "content-type": "application/json", "retry-after": "30" });
    res.end(JSON.stringify({ error: { message: "rate limited" } }));
  },

  // Usage/ping only activity.
  usage_only(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    res.write(openaiChunk({ usage: { prompt_tokens: 10, completion_tokens: 0 } }));
    res.write(openaiChunk({ finish_reason: "stop", usage: { prompt_tokens: 10, completion_tokens: 0 } }));
    res.end("data: [DONE]\n\n");
  },

  // Oversized tool args.
  tool_oversized(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    const big = "x".repeat(300000);
    res.write(openaiChunk({ delta: { tool_calls: [{ index: 0, id: "call_1", function: { name: "f", arguments: big } }] } }));
    res.write(openaiChunk({ finish_reason: "tool_calls" }));
    res.end("data: [DONE]\n\n");
  },

  // Accepts TCP but never returns headers.
  no_headers(res) {
    // Do nothing — never writeHead. The adapter must connect-timeout.
  },

  // Hold the stream open for ~500ms then finish normally (for concurrency release tests).
  hold_then_finish(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    setTimeout(() => {
      try {
        res.write(openaiChunk({ delta: { content: "done" } }));
        res.write(openaiChunk({ finish_reason: "stop", usage: { prompt_tokens: 5, completion_tokens: 1 } }));
        res.end("data: [DONE]\n\n");
      } catch {}
    }, 500);
  },

  // Normal non-streaming response.
  nonstream_text(res) {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({
      id: "chatcmpl-1", model: "glm-5.2",
      choices: [{ index: 0, message: { role: "assistant", content: "OK" }, finish_reason: "stop" }],
      usage: { prompt_tokens: 5, completion_tokens: 1 },
    }));
  },
};

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${port}`);
  if (req.method !== "POST" || url.pathname !== "/v1/chat/completions") {
    res.writeHead(404); res.end(); return;
  }
  let body = "";
  for await (const chunk of req) body += chunk;
  let parsed = {};
  try { parsed = JSON.parse(body); } catch {}

  // Determine scenario from header, query, or first user message content
  // (prefix "scenario:NAME"). The message-content path works through adapters
  // that do not forward custom headers (e.g. the frozen legacy artifact).
  let scenario = req.headers["x-fake-scenario"] || url.searchParams.get("scenario") || "";
  if (!scenario) {
    const msgs = Array.isArray(parsed.messages) ? parsed.messages : [];
    const firstUser = msgs.find((m) => m && m.role === "user");
    const text = typeof firstUser?.content === "string" ? firstUser.content : "";
    const m = /^scenario:([\w_]+)/.exec(text);
    if (m) scenario = m[1];
  }
  if (!scenario) scenario = "reasoning_then_text";
  const handler = scenarios[scenario];
  if (!handler) { res.writeHead(400, { "content-type": "application/json" }); res.end(JSON.stringify({ error: `unknown scenario: ${scenario}` })); return; }

  // http_error and rate_limited have special signatures.
  if (scenario === "http_error") { handler(res, 500); return; }
  handler(res);
});

server.listen(port, "127.0.0.1", () => {
  console.log(JSON.stringify({ ready: true, port: port }));
});
