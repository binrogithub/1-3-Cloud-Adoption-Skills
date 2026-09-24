"""Access control (PRD GL-S1/S2): roles reader/contributor/curator/admin, hashed tokens.

No demo credentials live in source or bundles: tokens are created by
`deploy/gen_token.py`, stored as sha256 hashes in runtime/auth/tokens.json (gitignored),
and presented via the `X-LLMWiki-Token` header by the web API. The CLI records a
`--by <name>` actor for audit instead of authenticating (it runs as the operator).
"""
from __future__ import annotations

import hashlib
import json
import secrets
import threading
from datetime import datetime
from pathlib import Path

from .config import ROLE_ADMIN, ROLE_CONTRIBUTOR, ROLE_CURATOR, ROLE_READER, ROLE_RANK, Config

# action -> minimum role rank
PERMISSIONS = {
    "ask": ROLE_READER,
    "browse": ROLE_READER,
    "search": ROLE_READER,
    "sources": ROLE_CONTRIBUTOR,
    "lint": ROLE_CONTRIBUTOR,
    "review": ROLE_CONTRIBUTOR,
    "ingest": ROLE_CONTRIBUTOR,
    "compile": ROLE_CONTRIBUTOR,
    "edit": ROLE_CONTRIBUTOR,            # PRD V9: manual web edits of wiki pages
    "fileback": ROLE_CONTRIBUTOR,
    "reverify": ROLE_CONTRIBUTOR,
    "approve": ROLE_CURATOR,
    "reject": ROLE_CURATOR,
    "tokens": ROLE_ADMIN,
    "export": ROLE_ADMIN,
}

_lock = threading.Lock()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class TokenStore:
    def __init__(self, path: Path):
        self.path = path
        self._cache: dict | None = None
        self._mtime = 0.0

    def _load(self) -> dict:
        with _lock:
            if self.path.exists():
                mtime = self.path.stat().st_mtime
                if self._cache is None or mtime != self._mtime:
                    self._cache = json.loads(self.path.read_text(encoding="utf-8"))
                    self._mtime = mtime
                return self._cache
            return {}

    def role_for(self, token: str | None) -> tuple[str, str] | None:
        """(name, role) for a valid token, else None."""
        if not token:
            return None
        entry = self._load().get(hash_token(token.strip()))
        if not entry:
            return None
        return entry.get("name", "?"), entry.get("role", ROLE_READER)

    def create(self, role: str, name: str, cfg: Config) -> str:
        if role not in ROLE_RANK:
            raise ValueError(f"role must be one of {sorted(ROLE_RANK)}")
        token = "llmwiki_" + secrets.token_urlsafe(30)
        data = self._load() if self.path.exists() else {}
        data[hash_token(token)] = {"role": role, "name": name,
                                   "created": datetime.now().isoformat(timespec="seconds")}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self.path.chmod(0o600)
        with _lock:
            self._cache, self._mtime = data, self.path.stat().st_mtime
        return token

    def revoke(self, token: str) -> bool:
        data = self._load()
        if hash_token(token.strip()) in data:
            del data[hash_token(token.strip())]
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            with _lock:
                self._cache, self._mtime = data, self.path.stat().st_mtime
            return True
        return False


def allowed(role: str, action: str) -> bool:
    need = PERMISSIONS.get(action)
    if need is None:
        return False
    return ROLE_RANK.get(role, -1) >= ROLE_RANK[need]


def open_tokens(cfg: Config) -> TokenStore:
    return TokenStore(cfg.path(cfg.web.tokens_file))
