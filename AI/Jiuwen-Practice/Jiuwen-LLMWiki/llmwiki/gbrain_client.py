"""Persistent gbrain MCP stdio client (PRD V6).

gbrain's recommended pattern for local agents is a long-lived `gbrain serve`
child speaking MCP over stdio — one handshake, then `tools/call` at ~10-25x the
CLI's per-call speed (the CLI pays ~0.55 s of bun+DB cold start every call).

Shapes replayed/verified against gbrain 0.53.0.0 on 247 (2026-09-24 probe):
  tools/call search    -> content[0].text = JSON array [{slug, title, type, chunk_text}]
  tools/call get_page  -> content[0].text = JSON object {slug, title, compiled_truth, ...}
  tools/call list_pages-> content[0].text = JSON array of page records
  tools/call put_page  -> content[0].text = receipt JSON
"""
from __future__ import annotations

import atexit
import json
import os
import select
import subprocess
import threading
import time


class MCPError(RuntimeError):
    pass


class GBrainMCP:
    """One `gbrain serve` child, shared by all threads; lazy respawn."""

    def __init__(self, bin_: str = "gbrain", env: dict | None = None, timeout_s: int = 60):
        self.bin = bin_
        self.env = env or {}
        self.timeout_s = timeout_s
        self._lock = threading.RLock()   # re-entrant: _ensure handshakes inside a locked call
        self._proc: subprocess.Popen | None = None
        self._id = 0
        atexit.register(self.close)

    # ---- process ---------------------------------------------------------
    def _ensure(self) -> subprocess.Popen:
        if self._proc is not None and self._proc.poll() is None:
            return self._proc
        env = dict(os.environ)
        for k, v in self.env.items():
            env[k] = v if not (k.endswith(("_DIR", "_HOME")) and not os.path.isabs(str(v))) else v
        p = subprocess.Popen([self.bin, "serve"], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             text=True, bufsize=1, env=env)
        self._proc = p
        self._rpc("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "llmwiki-glue", "version": "0.1"}})
        self._notify("notifications/initialized")
        return p

    def close(self) -> None:
        p, self._proc = self._proc, None
        if p is not None:
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass

    # ---- jsonrpc ---------------------------------------------------------
    def _send(self, obj: dict) -> None:
        p = self._proc
        p.stdin.write(json.dumps(obj) + "\n")
        p.stdin.flush()

    def _recv(self, want_id: int) -> dict:
        p = self._proc
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            r, _, _ = select.select([p.stdout], [], [], 1.0)
            if not r:
                continue
            line = p.stdout.readline()
            if not line:
                raise MCPError("gbrain serve closed the stream")
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == want_id:
                if "error" in msg:
                    raise MCPError(str(msg["error"])[:300])
                return msg.get("result", {})
        raise MCPError(f"gbrain serve timed out after {self.timeout_s}s")

    def _rpc(self, method: str, params: dict) -> dict:
        with self._lock:
            self._ensure()
            self._id += 1
            rid = self._id
            self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
            return self._recv(rid)

    def _notify(self, method: str) -> None:
        self._send({"jsonrpc": "2.0", "method": method})

    # ---- ops -------------------------------------------------------------
    def call(self, tool: str, arguments: dict) -> str:
        """tools/call -> the first text content block. A dead child (stream closed
        or broken pipe between calls) is respawned and the call retried once."""
        for attempt in (1, 2):
            with self._lock:
                self._ensure()
                self._id += 1
                rid = self._id
                try:
                    self._send({"jsonrpc": "2.0", "id": rid, "method": "tools/call",
                                "params": {"name": tool, "arguments": arguments}})
                    res = self._recv(rid)
                except (MCPError, BrokenPipeError, OSError) as e:
                    if attempt == 2 or "timed out" in str(e):
                        raise
                    self.close()          # child died between calls: respawn + retry
                    continue
            if res.get("isError"):
                raise MCPError(f"{tool} failed: {json.dumps(res)[:300]}")
            for block in res.get("content", []):
                if block.get("type") == "text":
                    return block.get("text", "")
            raise MCPError(f"{tool} returned no text content")
        raise MCPError(f"{tool}: unreachable")

    def search(self, query: str, limit: int = 6) -> list[str]:
        text = self.call("search", {"query": query, "limit": limit})
        try:
            items = json.loads(text)
        except json.JSONDecodeError:
            return []
        return [it.get("slug", "") for it in items if isinstance(it, dict) and it.get("slug")]

    def get_page(self, slug: str) -> dict | None:
        text = self.call("get_page", {"slug": slug})
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def list_pages(self, limit: int = 10000) -> list[dict]:
        text = self.call("list_pages", {"limit": limit})
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else data.get("pages", [])

    def put_page(self, slug: str, markdown: str) -> dict:
        # force=true: the glue is the sole writer and merges read-modify-write on
        # its side, mirroring the CLI template's --force (E0-S5 finding).
        text = self.call("put_page", {"slug": slug, "content": markdown, "force": True})
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text[:200]}
