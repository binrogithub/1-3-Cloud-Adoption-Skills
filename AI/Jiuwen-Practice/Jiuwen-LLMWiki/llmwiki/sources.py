"""L1 raw source store: immutable, content-addressed (sha256) snapshots + metadata."""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

LICENCES = ("public", "internal", "confidential")
PARSER_VERSION = "extract-1.1"          # E3-S5: bump when any extractor here changes
_MIN_TABLE_ROWS = 3                     # below this a table check is not meaningful


class SourceError(RuntimeError):
    pass


def detect_lang(text: str) -> str:
    """Cheap trilingual heuristic over the extracted text (E3-S5). 'en' as default."""
    low = text.lower()
    pt = sum(low.count(w) for w in (" não ", " são ", "ção", "çã", " você", " com ", " para ",
                                    " região", " disponível", " preço"))
    es = sum(low.count(w) for w in (" no son ", "ción", "ñ", " usted", " región",
                                    " disponible", " precio", "¿", "¡"))
    if pt > es and pt >= 2:
        return "pt-BR"
    if es > pt and es >= 2:
        return "es"
    return "en"


class SourceStore:
    def __init__(self, root: Path):
        self.root = root

    def add(self, ref: str, kind: str = "doc", licence: str = "public", lang: str = "",
            owner: str = "", meta_ref: str = "") -> dict:
        """ref is the read path; meta_ref (optional) overrides the stored display ref,
        so uploads can read an absolute temp path but cite a stable relative name."""
        if licence not in LICENCES:
            raise SourceError(f"licence must be one of {LICENCES}")
        text, fmt, raw = _read(ref)
        if len(text.strip()) < 40:
            raise SourceError(f"extracted text too short ({len(text.strip())} chars) from {ref}; "
                              "refusing an empty snapshot")
        if kind in ("price", "quota", "pricing"):
            _table_self_check(text, ref, raw, fmt)   # GL-C2: falsifiable parser self-check
        if not lang:
            lang = detect_lang(text)
        sid = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        meta_f = self.root / f"{sid}.json"
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if meta_f.exists():                       # FR-I2: dedup by content hash
            meta = json.loads(meta_f.read_text())
            meta["last_seen"] = now
            meta_f.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
            meta["duplicate"] = True
            return meta
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / f"{sid}.txt").write_text(text, encoding="utf-8")
        meta = {"id": sid, "ref": meta_ref or ref, "format": fmt, "kind": kind, "licence": licence,
                "lang": lang, "owner": owner, "fetched_at": now, "last_seen": now,
                "chars": len(text), "parser_version": PARSER_VERSION}
        meta_f.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
        return meta

    def get(self, sid: str) -> tuple[dict, str]:
        if not re.fullmatch(r"[0-9a-f]{16}", sid):
            raise SourceError(f"bad source id {sid!r}")
        meta_f = self.root / f"{sid}.json"
        if not meta_f.exists():
            raise SourceError(f"unknown source {sid}")
        return json.loads(meta_f.read_text()), (self.root / f"{sid}.txt").read_text(encoding="utf-8")

    def list(self) -> list[dict]:
        if not self.root.exists():
            return []
        return [json.loads(p.read_text()) for p in sorted(self.root.glob("*.json"))]


def _read(ref: str) -> tuple[str, str, str | None]:
    """(extracted text, format, raw original) — raw feeds the falsifiable self-check."""
    if ref.startswith(("http://", "https://")):
        req = urllib.request.Request(ref, headers={"User-Agent": "LLMWiki-ingest/0.1"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            ctype = r.headers.get("Content-Type", "")
        if "pdf" in ctype:
            return _pdf_bytes(raw), "pdf", None
        html_text = raw.decode("utf-8", "replace")
        return _html_to_text(html_text), "html", html_text
    p = Path(ref)
    if not p.exists():
        raise SourceError(f"no such file: {ref}")
    suf = p.suffix.lower()
    if suf == ".pdf":
        return _pdf_bytes(p.read_bytes()), "pdf", None
    if suf in (".html", ".htm"):
        raw = p.read_text(encoding="utf-8", errors="replace")
        return _html_to_text(raw), "html", raw
    if suf in (".md", ".txt", ".csv", ".json", ".yaml", ".yml"):
        t = p.read_text(encoding="utf-8", errors="replace")
        return t, suf.lstrip("."), t
    raise SourceError(f"unsupported format {suf}; convert to PDF/HTML/MD/TXT first")


def _pdf_bytes(raw: bytes) -> str:
    exe = shutil.which("pdftotext")
    if not exe:
        raise SourceError("pdftotext (poppler-utils) is required for PDF sources")
    p = subprocess.run([exe, "-layout", "-", "-"], input=raw, capture_output=True, timeout=120)
    if p.returncode != 0:
        raise SourceError(f"pdftotext failed: {p.stderr.decode()[:200]}")
    return p.stdout.decode("utf-8", "replace")


# ---- GL-C2: falsifiable table self-check -----------------------------------
# A check that cannot fail is not a check. When a price/quota source is ingested, the
# extracted tables are validated against the *rendered* source: row shape must be
# consistent, and numeric cell values sampled from the raw HTML must survive into the
# extract. Any mismatch fails the ingest instead of silently storing a wrong table.

def _md_tables(text: str) -> list[list[list[str]]]:
    tables, current = [], []
    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not all(set(c) <= set(":- ") and c for c in cells):   # skip rule rows
                current.append(cells)
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def _sample_td_numbers(raw_html: str, limit: int = 20) -> list[str]:
    return re.findall(r"<td[^>]*>\s*([\d.,]+)\s*</td>", raw_html, re.I)[:limit]


def _table_self_check(text: str, ref: str, raw: str | None = None, fmt: str = "") -> None:
    errors: list[str] = []
    for i, rows in enumerate(_md_tables(text)):
        if len(rows) < _MIN_TABLE_ROWS:
            continue
        header_cols = len(rows[0])
        for r in rows[1:]:
            if len(r) != header_cols:
                errors.append(f"table {i}: row with {len(r)} cells, header has {header_cols}")
    if fmt == "html" and raw:
        raw_rows = len(re.findall(r"<tr\b", raw, re.I))
        ext_rows = len([l for l in text.splitlines() if l.count(" | ") >= 1])
        if raw_rows and ext_rows * 2 < raw_rows:
            errors.append(f"rows under-extracted: {raw_rows} <tr> in HTML, {ext_rows} row-like lines kept")
        for v in _sample_td_numbers(raw):
            if v not in text:
                errors.append(f"cell value {v!r} lost by the extractor")
    if errors:
        raise SourceError(f"parser self-check failed for {ref}: " + "; ".join(errors[:5]))


def _html_to_text(s: str) -> str:
    s = re.sub(r"(?is)<(script|style|nav|footer|header|noscript)\b.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h[1-6])>", "\n", s)
    s = re.sub(r"(?i)</t[dh]>", " | ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t ]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n\n", s).strip()
