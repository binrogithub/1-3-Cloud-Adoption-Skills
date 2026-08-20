"use strict";
// RequestLifecycleController — per-request reliability control for the MaaS adapter.
//
// Implements the 11-state machine, active watchdogs (connect/idle/total),
// upstream AbortController, idempotent client-cancel propagation, strict SSE
// termination (finish-aware EOF), backpressure awareness, size accounting,
// and sanitized metrics. One instance per request. Exactly-once finalize.
//
// PRD: docs/PRD_MAAS_STREAM_RELIABILITY_PRODUCTION_CLOSURE_V2.md

const { EventEmitter } = require("node:events");
const crypto = require("node:crypto");

// ---------------------------------------------------------------------------
// Error codes (PRD §6)
// ---------------------------------------------------------------------------

const ErrorCodes = {
  CONNECT_TIMEOUT: "MAAS_CONNECT_TIMEOUT",
  IDLE_TIMEOUT: "MAAS_IDLE_TIMEOUT",
  TOTAL_TIMEOUT: "MAAS_TOTAL_TIMEOUT",
  UPSTREAM_HTTP: "MAAS_UPSTREAM_HTTP",
  STREAM_EOF: "MAAS_STREAM_EOF",
  STREAM_PROTOCOL: "MAAS_STREAM_PROTOCOL",
  TOOL_ARGS_TOO_LARGE: "MAAS_TOOL_ARGS_TOO_LARGE",
  CLIENT_ABORTED: "MAAS_CLIENT_ABORTED",
  OVER_CAPACITY: "MAAS_OVER_CAPACITY",
};

const RETRYABLE = new Set([
  ErrorCodes.CONNECT_TIMEOUT,
  ErrorCodes.IDLE_TIMEOUT,
  ErrorCodes.TOTAL_TIMEOUT,
  ErrorCodes.STREAM_EOF,
  ErrorCodes.OVER_CAPACITY,
]);

const HTTP_STATUS = {
  [ErrorCodes.CONNECT_TIMEOUT]: 504,
  [ErrorCodes.IDLE_TIMEOUT]: 504,
  [ErrorCodes.TOTAL_TIMEOUT]: 504,
  [ErrorCodes.UPSTREAM_HTTP]: 502,
  [ErrorCodes.STREAM_EOF]: 502,
  [ErrorCodes.STREAM_PROTOCOL]: 502,
  [ErrorCodes.TOOL_ARGS_TOO_LARGE]: 422,
  [ErrorCodes.CLIENT_ABORTED]: 499,
  [ErrorCodes.OVER_CAPACITY]: 503,
};

// ---------------------------------------------------------------------------
// States (PRD core state machine — 11 states)
// ---------------------------------------------------------------------------

const State = {
  ACCEPTED: "accepted",
  CONNECTING: "connecting",
  UPSTREAM_ACTIVE_HIDDEN: "upstream_active_hidden",
  VISIBLE_STREAMING: "visible_streaming",
  COMPLETING: "completing",
  COMPLETED: "completed",
  CLIENT_ABORTED: "client_aborted",
  CONNECT_TIMEOUT: "connect_timeout",
  IDLE_TIMEOUT: "idle_timeout",
  TOTAL_TIMEOUT: "total_timeout",
  UPSTREAM_FAILED: "upstream_failed",
};

const TERMINAL_STATES = new Set([
  State.COMPLETED,
  State.CLIENT_ABORTED,
  State.CONNECT_TIMEOUT,
  State.IDLE_TIMEOUT,
  State.TOTAL_TIMEOUT,
  State.UPSTREAM_FAILED,
]);

const TRUSTWORTHY_FINISH_REASONS = new Set([
  "end_turn", "stop_sequence", "tool_use", "max_tokens",
]);

// ---------------------------------------------------------------------------
// RequestLifecycleController
// ---------------------------------------------------------------------------

class RequestLifecycleController {
  constructor(opts = {}) {
    this.requestId = crypto.randomUUID();
    this.state = State.ACCEPTED;
    this.errorCode = null;
    this.finishReason = null;
    this.protocolError = false;

    // Timers (active watchdogs, not passive checks).
    this._connectTimer = null;
    this._idleTimer = null;
    this._totalTimer = null;
    this._connectTimeout = opts.connectTimeout ?? 60_000;
    this._idleTimeout = opts.idleTimeout ?? 180_000;
    this._totalTimeout = opts.totalTimeout ?? 600_000;

    // Upstream cancellation.
    this.abortController = new AbortController();

    // SSE block tracking.
    this._messageStartSent = false;
    this._messageStopSent = false;
    this._messageDeltaSent = false;
    this._openBlocks = new Map();   // index -> block type
    this._everOpened = new Set();   // all indices ever opened (once-only)

    // Metrics (sanitized — no content).
    this.metrics = {
      request_id: this.requestId,
      reasoning_chunks: 0,
      reasoning_bytes: 0,
      visible_text_bytes: 0,
      tool_calls: 0,
      outcome: null,
      error_code: null,
      retryable: null,
    };

    // Timing.
    this._startedAt = Date.now();
    this._connectedAt = null;
    this._lastActivityAt = null;
    this._finalized = false;

    // Callbacks for state changes and errors.
    this._onTimeout = opts.onTimeout || (() => {});
    this._onStateChange = opts.onStateChange || (() => {});
  }

  // --- State transitions ---

  _setState(s) {
    this.state = s;
    this._onStateChange(s);
  }

  isTerminal() {
    return TERMINAL_STATES.has(this.state);
  }

  // --- Timers ---

  startConnectTimer() {
    this._setState(State.CONNECTING);
    this._connectTimer = setTimeout(() => {
      if (this._connectedAt !== null) return;
      this._fail(ErrorCodes.CONNECT_TIMEOUT, State.CONNECT_TIMEOUT);
    }, this._connectTimeout);
  }

  markConnected() {
    if (this._connectTimer) { clearTimeout(this._connectTimer); this._connectTimer = null; }
    this._connectedAt = Date.now();
    this._lastActivityAt = Date.now();
    this._startIdleTimer();
    this._startTotalTimer();
  }

  _startIdleTimer() {
    this._refreshIdleTimer();
  }

  _refreshIdleTimer() {
    if (this._idleTimer) clearTimeout(this._idleTimer);
    this._lastActivityAt = Date.now();
    this._idleTimer = setTimeout(() => {
      this._fail(ErrorCodes.IDLE_TIMEOUT, State.IDLE_TIMEOUT);
    }, this._idleTimeout);
  }

  _startTotalTimer() {
    this._totalTimer = setTimeout(() => {
      this._fail(ErrorCodes.TOTAL_TIMEOUT, State.TOTAL_TIMEOUT);
    }, this._totalTimeout);
  }

  // --- Activity ---

  recordActivity(kind = "unknown") {
    if (this.isTerminal()) return;
    this._refreshIdleTimer();
    // Reasoning-only activity keeps us in hidden state.
    if (kind === "reasoning" && this.state === State.CONNECTING) {
      this._setState(State.UPSTREAM_ACTIVE_HIDDEN);
    }
  }

  recordReasoning(text) {
    if (this.isTerminal()) return;
    this.metrics.reasoning_chunks += 1;
    this.metrics.reasoning_bytes += Buffer.byteLength(text || "", "utf8");
    this.recordActivity("reasoning");
  }

  recordVisibleText(text) {
    if (this.isTerminal()) return;
    this.metrics.visible_text_bytes += Buffer.byteLength(text || "", "utf8");
    this.recordActivity("text");
    if (this.state !== State.COMPLETING) this._setState(State.VISIBLE_STREAMING);
  }

  recordToolCall() {
    if (this.isTerminal()) return;
    this.metrics.tool_calls += 1;
    this.recordActivity("tool");
    if (this.state !== State.COMPLETING) this._setState(State.VISIBLE_STREAMING);
  }

  // --- SSE termination state machine ---

  feedMessageStart() {
    if (this._messageStartSent || this.protocolError) return false;
    this._messageStartSent = true;
    return true;
  }

  feedBlockStart(index, blockType) {
    if (this.protocolError) return false;
    if (this._everOpened.has(index)) { this.protocolError = true; return false; }
    if (this._openBlocks.has(index)) { this.protocolError = true; return false; }
    this._everOpened.add(index);
    this._openBlocks.set(index, blockType);
    return true;
  }

  feedBlockDelta(index, deltaType) {
    if (this.protocolError) return false;
    const expected = this._openBlocks.get(index);
    if (expected === undefined) { this.protocolError = true; return false; }
    if (deltaType === "text_delta" && expected !== "text") { this.protocolError = true; return false; }
    if (deltaType === "input_json_delta" && expected !== "tool_use") { this.protocolError = true; return false; }
    if (deltaType === "thinking_delta" && expected !== "thinking") { this.protocolError = true; return false; }
    return true;
  }

  feedBlockStop(index) {
    if (this.protocolError) return false;
    if (!this._openBlocks.has(index)) { this.protocolError = true; return false; }
    this._openBlocks.delete(index);
    return true;
  }

  /**
   * Record a trustworthy finish reason seen on the upstream stream WITHOUT
   * consuming the message_delta slot. The terminal message_delta (stop_reason
   * + usage) is synthesized exactly once, in finalize(), so the client always
   * receives it. Repeat calls are idempotent.
   */
  recordFinishReason(stopReason) {
    if (this.protocolError) return false;
    if (TRUSTWORTHY_FINISH_REASONS.has(stopReason)) {
      this.finishReason = stopReason;
    }
    return true;
  }

  feedMessageDelta(stopReason) {
    if (this.protocolError) return false;
    if (this._messageDeltaSent) { this.protocolError = true; return false; }
    this._messageDeltaSent = true;
    if (TRUSTWORTHY_FINISH_REASONS.has(stopReason)) {
      this.finishReason = stopReason;
    }
    return true;
  }

  feedMessageStop() {
    if (this.protocolError) return false;
    if (this._messageStopSent) { this.protocolError = true; return false; }
    if (!this._messageStartSent) { this.protocolError = true; return false; }
    this._messageStopSent = true;
    return true;
  }

  /**
   * Finalize the stream. Returns events to synthesize, or null if failure.
   * Only synthesizes success if a trustworthy finish reason was observed.
   */
  finalize() {
    if (this._finalized) return null;
    this._finalized = true;
    this._cleanup();

    // If a protocol error occurred, never fake success.
    if (this.protocolError && !this._messageStopSent) {
      this._fail(ErrorCodes.STREAM_PROTOCOL, State.UPSTREAM_FAILED);
      return null;
    }

    // If already stopped, we're done.
    if (this._messageStopSent) {
      this._setState(State.COMPLETED);
      this.metrics.outcome = "completed";
      return null;
    }

    // No trustworthy finish reason → failure (never fake success).
    if (this.finishReason === null) {
      this._fail(ErrorCodes.STREAM_EOF, State.UPSTREAM_FAILED);
      return null;
    }

    // Synthesize terminal events in protocol order.
    const events = [];
    for (const index of [...this._openBlocks.keys()].sort((a, b) => a - b)) {
      events.push({ type: "content_block_stop", index });
    }
    this._openBlocks.clear();
    if (!this._messageDeltaSent) {
      events.push({ type: "message_delta", delta: { stop_reason: this.finishReason, stop_sequence: null } });
    }
    events.push({ type: "message_stop" });
    this._messageStopSent = true;
    this._setState(State.COMPLETED);
    this.metrics.outcome = "completed";
    return events;
  }

  // --- Cancellation ---

  abort() {
    if (this.isTerminal()) return;
    this._cleanup();
    try { this.abortController.abort(); } catch {}
    this._setState(State.CLIENT_ABORTED);
    this.metrics.outcome = "client_aborted";
    this.metrics.error_code = ErrorCodes.CLIENT_ABORTED;
    this.metrics.retryable = false;
  }

  // --- Failure ---

  _fail(code, state) {
    if (this.isTerminal()) return;
    this._cleanup();
    try { this.abortController.abort(); } catch {}
    this.errorCode = code;
    this._setState(state);
    this.metrics.outcome = state;
    this.metrics.error_code = code;
    this.metrics.retryable = RETRYABLE.has(code);
    this._onTimeout(code);
  }

  // --- Cleanup (exactly once) ---

  _cleanup() {
    if (this._connectTimer) { clearTimeout(this._connectTimer); this._connectTimer = null; }
    if (this._idleTimer) { clearTimeout(this._idleTimer); this._idleTimer = null; }
    if (this._totalTimer) { clearTimeout(this._totalTimer); this._totalTimer = null; }
  }

  // --- Status snapshot (sanitized) ---

  statusSnapshot() {
    return {
      request_id: this.requestId,
      state: this.state,
      error_code: this.errorCode,
      finish_reason: this.finishReason,
      age_ms: Date.now() - this._startedAt,
      ...this.metrics,
    };
  }
}

// ---------------------------------------------------------------------------
// Concurrency guard (atomic within the event loop)
// ---------------------------------------------------------------------------

class ConcurrencyGuard {
  constructor(max = 8) {
    this._max = max;
    this._active = 0;
    this._peak = 0;
  }

  get active() { return this._active; }
  get peak() { return this._peak; }

  tryAdmit() {
    if (this._active >= this._max) return false;
    this._active += 1;
    if (this._active > this._peak) this._peak = this._active;
    return true;
  }

  release() {
    if (this._active > 0) this._active -= 1;
  }
}

// ---------------------------------------------------------------------------
// Loopback check (fail-closed for unknown/missing)
// ---------------------------------------------------------------------------

const LOOPBACK_ADDRS = new Set(["127.0.0.1", "::1", "::ffff:127.0.0.1"]);

function isLoopback(remoteAddr) {
  if (!remoteAddr || typeof remoteAddr !== "string") return false;
  return LOOPBACK_ADDRS.has(remoteAddr);
}

module.exports = {
  ErrorCodes,
  RETRYABLE,
  HTTP_STATUS,
  State,
  TERMINAL_STATES,
  RequestLifecycleController,
  ConcurrencyGuard,
  isLoopback,
};
