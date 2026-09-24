"""Load llmwiki.toml. Stdlib only (Python 3.11+ tomllib)."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

NAMESPACES = (
    "services", "regions", "availability", "comparisons", "concepts",
    "pricing", "compliance", "howto", "faq", "_meta",
)
# Compiled-truth changes here always need a human approver (PRD FR-C4).
PROTECTED_NAMESPACES = ("pricing", "compliance", "availability")
ROLE_READER, ROLE_CONTRIBUTOR, ROLE_CURATOR, ROLE_ADMIN = "reader", "contributor", "curator", "admin"
ROLE_RANK = {ROLE_READER: 0, ROLE_CONTRIBUTOR: 1, ROLE_CURATOR: 2, ROLE_ADMIN: 3}


@dataclass
class GBrainCfg:
    backend: str = "gbrain"             # "gbrain" | "files" (keyword-only fallback, PRD B-1)
    bin: str = "gbrain"
    # Command templates verified against gbrain 0.53.0.0 (E0-S5, 2026-09-24):
    #   put <slug> reads the page markdown on stdin and needs --force (or --expected-revision)
#   to replace an existing page — the glue is the single writer (D-5) and merges
#   read-modify-write on its side, so force is correct; list prints "slug<TAB>type<TAB>date<TAB>title";
    #   query is hybrid (RRF) and degrades to keyword-only with a stderr warning when no
    #   embedding endpoint is configured. "{q}", "{slug}" are substituted.
    search_cmd: list[str] = field(default_factory=lambda: ["{bin}", "query", "{q}"])
    get_cmd: list[str] = field(default_factory=lambda: ["{bin}", "get", "{slug}"])
    put_cmd: list[str] = field(default_factory=lambda: ["{bin}", "put", "{slug}", "--force"])
    delete_cmd: list[str] = field(default_factory=lambda: ["{bin}", "delete", "{slug}", "--force"])
    list_cmd: list[str] = field(default_factory=lambda: ["{bin}", "list", "--limit", "10000"])
    timeout_s: int = 60
    files_dir: str = "runtime/wiki"     # used by backend="files"; also the local mirror
    env: dict[str, str] = field(default_factory=dict)   # e.g. GBRAIN_HOME for the dedicated brain
    # gbrain maintenance (dream/autopilot) must never write pages on its own (E8-S5).
    # propose_only is a documentation + doctor-checked switch for the operator, not an enforcement
    # hook inside gbrain (we do not modify its source).
    maintenance_mode: str = "propose-only"


@dataclass
class JiuwenCfg:
    bin: str = "/root/.local/bin/jiuwenswarm"
    data_dir: str = "runtime/jiuwen"    # JIUWENSWARM_DATA_DIR of the dedicated LLMWiki instance
    gateway_port: int = 20001
    mode: str = "code"                  # agent-mode custom roles crash in 0.2.3 (PRD R-6)
    role: str = "llmwiki"
    timeout_s: int = 180
    require_role_dispatch: bool = True  # fail closed if the llmwiki sub-agent was not used


@dataclass
class AskCfg:
    top_k: int = 6
    max_evidence_chars: int = 60_000
    stale_after_days: int = 90
    pricing_stale_after_days: int = 90
    url_domains: list[str] = field(default_factory=lambda: [
        "huaweicloud.com", "support.huaweicloud.com", "www.huaweicloud.com",
    ])
    # Namespaces whose page titles become checked claim terms (GR-1). E6-S7: service names too.
    term_namespaces: list[str] = field(default_factory=lambda: ["regions", "compliance", "services"])
    # Extra fixed terms always checked (glossary names/abbreviations), file with one term per line.
    glossary_terms_file: str = "wiki/glossary-terms.txt"
    # OQ-4: retention for ask.jsonl. 0 = keep forever.
    log_retention_days: int = 180
    # GL-A9: raw (unverified) role answers are never logged; policy switch kept explicit.
    log_raw_answers: bool = False


@dataclass
class ReviewCfg:
    # FR-C4/E7-S7: non-protected, conflict-free, timeline/link-only change sets from public
    # sources may be auto-applied by policy (the human owner of this switch is the approver).
    auto_approve_nonprotected: bool = False
    auto_approve_actor: str = "auto-approve-policy"
    # PRD V5 §2: scoped auto-apply for the upload flow (public licence + pending +
    # zero problems + zero conflicts + no protected namespace). One-flag off switch.
    auto_apply_uploads: bool = True
    upload_actor: str = "upload-autoflow"


@dataclass
class WebCfg:
    host: str = "127.0.0.1"
    port: int = 20080
    # token file: JSON {"sha256": {"token-sha256": {"role": "...", "name": "..."}}}
    tokens_file: str = "runtime/auth/tokens.json"


@dataclass
class Config:
    gbrain: GBrainCfg
    jiuwen: JiuwenCfg
    ask: AskCfg
    review: ReviewCfg = field(default_factory=ReviewCfg)
    web: WebCfg = field(default_factory=WebCfg)
    runtime_dir: Path = Path("runtime")

    def path(self, rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else PROJECT_ROOT / p


def load(path: str | os.PathLike | None = None) -> Config:
    path = Path(path or os.environ.get("LLMWIKI_CONFIG") or PROJECT_ROOT / "llmwiki.toml")
    raw: dict = {}
    if path.exists():
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    runtime = Path(raw.get("runtime_dir", "runtime"))
    if not runtime.is_absolute():
        runtime = PROJECT_ROOT / runtime
    return Config(
        gbrain=GBrainCfg(**raw.get("gbrain", {})),
        jiuwen=JiuwenCfg(**raw.get("jiuwen", {})),
        ask=AskCfg(**raw.get("ask", {})),
        review=ReviewCfg(**raw.get("review", {})),
        web=WebCfg(**raw.get("web", {})),
        runtime_dir=runtime,
    )
