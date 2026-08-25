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

  // Tool call with truncated-but-closeable JSON args + clean finish.
  // '{"city":"Beijing"' is missing the closing } but the last token is a
  // complete value.  Repair should close it to {"city":"Beijing"}.
  tool_truncated_closeable(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    res.write(openaiChunk({ delta: { tool_calls: [{ index: 0, id: "call_1", function: { name: "get_weather", arguments: '{"city":"Beijing"' } }] } }));
    res.write(openaiChunk({ finish_reason: "tool_calls" }));
    res.end("data: [DONE]\n\n");
  },

  // Tool call with mid-string truncation — NOT repairable (gate 2).
  // '{"city":"Beij' has an unterminated string; closing it would silently
  // drop characters.
  tool_truncated_midstring(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    res.write(openaiChunk({ delta: { tool_calls: [{ index: 0, id: "call_1", function: { name: "get_weather", arguments: '{"city":"Beij' } }] } }));
    res.write(openaiChunk({ finish_reason: "tool_calls" }));
    res.end("data: [DONE]\n\n");
  },

  // Tool call with closeable JSON but finish_reason=length (gate 1).
  // The args look repairable but the model was cut off by max_tokens —
  // the params are genuinely incomplete, repair would be fabrication.
  tool_truncated_by_length(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    res.write(openaiChunk({ delta: { tool_calls: [{ index: 0, id: "call_1", function: { name: "get_weather", arguments: '{"city":"Beijing"' } }] } }));
    res.write(openaiChunk({ finish_reason: "length" }));
    res.end("data: [DONE]\n\n");
  },

  // Tool call with single-quote dialect (Python dict style) — NOT valid JSON.
  // JSON.parse → "Expected property name or '}'" → dialect_property_name.
  tool_single_quote(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    res.write(openaiChunk({ delta: { tool_calls: [{ index: 0, id: "call_1", function: { name: "get_weather", arguments: "{'city':'Beijing'}" } }] } }));
    res.write(openaiChunk({ finish_reason: "tool_calls" }));
    res.end("data: [DONE]\n\n");
  },

  // Tool call with non-JSON args (function-call syntax) — NOT valid JSON.
  // JSON.parse → "Unexpected token 'g'..." → not_json.
  tool_not_json(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    res.write(openaiChunk({ delta: { tool_calls: [{ index: 0, id: "call_1", function: { name: "get_weather", arguments: "get_weather(city=Beijing)" } }] } }));
    res.write(openaiChunk({ finish_reason: "tool_calls" }));
    res.end("data: [DONE]\n\n");
  },

  // Tool call with trailing comma — NOT valid JSON.
  // JSON.parse → "Expected double-quoted property name" → expected_quoted_name.
  tool_trailing_comma(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    res.write(openaiChunk({ delta: { tool_calls: [{ index: 0, id: "call_1", function: { name: "get_weather", arguments: '{"a":1,' } }] } }));
    res.write(openaiChunk({ finish_reason: "tool_calls" }));
    res.end("data: [DONE]\n\n");
  },

  // Tool call with canary in non-JSON args — for leak gate testing.
  // The canary must NEVER appear in adapter stderr (structured log).
  tool_not_json_canary(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    const canary = "CANARY-7f3a9c2e1b8d4f60-xyzzy-plugh";
    res.write(openaiChunk({ delta: { tool_calls: [{ index: 0, id: "call_1", function: { name: "get_weather", arguments: `get_weather(${canary})` } }] } }));
    res.write(openaiChunk({ finish_reason: "tool_calls" }));
    res.end("data: [DONE]\n\n");
  },

  // Tool call with raw markup as arguments — NOT valid JSON.
  // The model emitted markup text instead of structured tool calls.
  // X2: must be classified as "tool_markup_as_args", not "tool_args_malformed".
  tool_markup_args(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    const lt = String.fromCharCode(0x3C);
    const gt = String.fromCharCode(0x3E);
    const markup = lt + "tool_call" + gt + '\n' + JSON.stringify({name: "get_weather", arguments: {city: "Beijing"}}) + '\n' + lt + "/tool_call" + gt;
    res.write(openaiChunk({ delta: { tool_calls: [{ index: 0, id: "call_1", function: { name: "get_weather", arguments: markup } }] } }));
    res.write(openaiChunk({ finish_reason: "tool_calls" }));
    res.end("data: [DONE]\n\n");
  },

  // Tool call with arguments split across 3 chunks, NO index in any delta.
  // First chunk carries id + name; subsequent chunks carry only arguments.
  // Fragments concatenate to {"city":"Beijing"}.
  // Reproduces the V5 defect: index absent → toolCalls.size increments per
  // fragment → one call split into three → JSON.parse fails on each fragment.
  tool_fragments_no_index(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    res.write(openaiChunk({ delta: { tool_calls: [{ id: "call_1", function: { name: "get_weather", arguments: '{"city"' } }] } }));
    res.write(openaiChunk({ delta: { tool_calls: [{ function: { arguments: ': "Beij' } }] } }));
    res.write(openaiChunk({ delta: { tool_calls: [{ function: { arguments: 'ing"}' } }] } }));
    res.write(openaiChunk({ finish_reason: "tool_calls" }));
    res.end("data: [DONE]\n\n");
  },

  // Two tool calls, NO index in any delta.  Each call's first chunk carries
  // id + name; continuation chunks carry only arguments.
  // Call 1: {"city":"Tokyo"}  Call 2: {"zone":"JST"}
  tool_two_calls_no_index(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    // Call 1, fragment 1 (id + name + first args fragment)
    res.write(openaiChunk({ delta: { tool_calls: [{ id: "call_1", function: { name: "get_weather", arguments: '{"city":' } }] } }));
    // Call 1, fragment 2 (args only)
    res.write(openaiChunk({ delta: { tool_calls: [{ function: { arguments: '"Tokyo"}' } }] } }));
    // Call 2, fragment 1 (id + name + first args fragment)
    res.write(openaiChunk({ delta: { tool_calls: [{ id: "call_2", function: { name: "get_time", arguments: '{"zone":' } }] } }));
    // Call 2, fragment 2 (args only)
    res.write(openaiChunk({ delta: { tool_calls: [{ function: { arguments: '"JST"}' } }] } }));
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

  // Non-streaming response with a valid tool call — used by L1-A retry tests.
  // The adapter's retryToolCallArgs sends stream:false with tool_choice.
  nonstream_tool_valid(res) {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({
      id: "chatcmpl-retry", model: "glm-5.2",
      choices: [{ index: 0, message: { role: "assistant", content: null,
        tool_calls: [{ id: "call_retry", function: { name: "get_weather", arguments: '{"city":"Beijing"}' } }] },
        finish_reason: "tool_calls" }],
      usage: { prompt_tokens: 5, completion_tokens: 1 },
    }));
  },

  // Non-streaming response with STILL-malformed tool args — retry fails.
  nonstream_tool_malformed(res) {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({
      id: "chatcmpl-retry", model: "glm-5.2",
      choices: [{ index: 0, message: { role: "assistant", content: null,
        tool_calls: [{ id: "call_retry", function: { name: "get_weather", arguments: '{"city":' } }] },
        finish_reason: "tool_calls" }],
      usage: { prompt_tokens: 5, completion_tokens: 1 },
    }));
  },

  // Two tool calls in one stream: first malformed, second valid.
  // G2 (PRD LOOP_CONTINUITY_V1): the second valid call must NOT be dropped.
  tool_malformed_then_valid(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    res.write(openaiChunk({ delta: { tool_calls: [{ index: 0, id: "call_1", function: { name: "get_weather", arguments: '{"city":' } }] } }));
    res.write(openaiChunk({ delta: { tool_calls: [{ index: 1, id: "call_2", function: { name: "get_time", arguments: '{"zone":"UTC"}' } }] } }));
    res.write(openaiChunk({ finish_reason: "tool_calls" }));
    res.end("data: [DONE]\n\n");
  },

  // Visible text THEN a malformed tool call in the same stream.
  // M3-G (PRD LOOP_CONTINUITY_V2): the adapter's non-streaming retry must not
  // cause the already-streamed text to appear twice on the client.
  text_then_malformed_tool(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    res.write(openaiChunk({ delta: { content: "Let me check the weather." } }));
    res.write(openaiChunk({ delta: { tool_calls: [{ index: 0, id: "call_1", function: { name: "get_weather", arguments: '{"city":' } }] } }));
    res.write(openaiChunk({ finish_reason: "tool_calls" }));
    res.end("data: [DONE]\n\n");
  },

  // Slow reasoning: initial usage chunk (so fetch() resolves), then 1
  // reasoning chunk every 10s for a few rounds, then text + finish.
  // Used by time-driven keepalive reverse gate (PRD TIME_DRIVEN_KEEPALIVE §4.1).
  // Without keepalive, client gaps ≈10s. With keepalive (2s), gaps ≤3s.
  slow_reasoning(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    // Initial usage chunk so fetch() resolves the response immediately.
    res.write(openaiChunk({ usage: { prompt_tokens: 10, completion_tokens: 0 } }));
    let count = 0;
    const iv = setInterval(() => {
      try {
        if (count < 3) {
          res.write(openaiChunk({ delta: { reasoning_content: `slow step ${count + 1}` } }));
          count += 1;
        } else {
          clearInterval(iv);
          res.write(openaiChunk({ delta: { content: "Done." } }));
          res.write(openaiChunk({ finish_reason: "stop", usage: { prompt_tokens: 10, completion_tokens: 5 } }));
          res.end("data: [DONE]\n\n");
        }
      } catch { clearInterval(iv); }
    }, 10000); // 10s between reasoning chunks
    res.on("close", () => clearInterval(iv));
  },

  // Usage-only trickle: initial chunk, then 1 usage chunk every 10s,
  // no content or reasoning. Used by keepalive reverse gate (§4.2).
  usage_only_trickle(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    // Initial usage chunk so fetch() resolves.
    res.write(openaiChunk({ usage: { prompt_tokens: 10, completion_tokens: 0 } }));
    let count = 0;
    const iv = setInterval(() => {
      try {
        if (count < 3) {
          res.write(openaiChunk({ usage: { prompt_tokens: 10, completion_tokens: count + 1 } }));
          count += 1;
        } else {
          clearInterval(iv);
          res.write(openaiChunk({ finish_reason: "stop", usage: { prompt_tokens: 10, completion_tokens: 4 } }));
          res.end("data: [DONE]\n\n");
        }
      } catch { clearInterval(iv); }
    }, 10000); // 10s between usage chunks
    res.on("close", () => clearInterval(iv));
  },

  // Slow reasoning with high-entropy canary for zero-leakage test (§4.5).
  // Initial usage chunk, then 1 canary-bearing reasoning chunk every 5s.
  slow_reasoning_canary(res) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    res.write(openaiChunk({ usage: { prompt_tokens: 10, completion_tokens: 0 } }));
    const canary = "CANARY-7f3a9c2e1b8d4f60-xyzzy-plugh";
    let count = 0;
    const iv = setInterval(() => {
      try {
        if (count < 3) {
          res.write(openaiChunk({ delta: { reasoning_content: `${canary} slow step ${count + 1}` } }));
          count += 1;
        } else {
          clearInterval(iv);
          res.write(openaiChunk({ delta: { content: "Done." } }));
          res.write(openaiChunk({ finish_reason: "stop", usage: { prompt_tokens: 10, completion_tokens: 5 } }));
          res.end("data: [DONE]\n\n");
        }
      } catch { clearInterval(iv); }
    }, 5000); // 5s between reasoning chunks
    res.on("close", () => clearInterval(iv));
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

  // L1-A retry detection (PRD LOOP_CONTINUITY_V1): the adapter sends a
  // non-streaming request (stream:false) with tool_choice when retrying
  // malformed tool args.  Route these to a valid non-streaming tool response
  // so the retry succeeds.  The "retry_fail" scenario still returns malformed.
  if (parsed.stream === false && parsed.tool_choice) {
    if (scenario === "retry_fail") {
      scenarios.nonstream_tool_malformed(res);
    } else {
      scenarios.nonstream_tool_valid(res);
    }
    return;
  }

  const handler = scenarios[scenario];
  if (!handler) { res.writeHead(400, { "content-type": "application/json" }); res.end(JSON.stringify({ error: `unknown scenario: ${scenario}` })); return; }

  // http_error and rate_limited have special signatures.
  if (scenario === "http_error") { handler(res, 500); return; }
  handler(res);
});

server.listen(port, "127.0.0.1", () => {
  console.log(JSON.stringify({ ready: true, port: port }));
});
