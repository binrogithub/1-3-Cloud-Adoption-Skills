"""Post-generation claim verifier (PRD §9).

A claim is grounded only if its value appears in a document *cited in the same sentence*
(table row / sentence unit) — not merely somewhere in the retrieved context. Checked claim
types: numbers with units (incl. prices, %, sizes, years), dates, spelled-out small
numbers, URLs, and configured terms (region, certification and service names). Works for
both answers ([W:slug] citations over wiki pages) and compile output ([S:id] citations
over one source).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

ABSTAIN_TOKEN = "NOT_IN_WIKI"
REDACTION = "⟦unverified⟧"

URL_RE = re.compile(r"https?://[^\s\)\]>\"'|]+")
# number token (EN 1,024.5 / ES-PT 1.024,5) with optional currency before and unit after.
# "$" folds to USD (ambiguous in LATAM, but consistently on both claim and page sides).
# Boundaries are ASCII-only: CJK text packs numbers against characters (于2026年9月10日)
# and 年/月/日 must not count as token boundaries the way v4.1 or 20260910-abc do.
NUM_RE = re.compile(
    r"(?P<cur>USD|US\$|R\$|MXN|ARS|CLP|BRL|EUR|[$€])?\s*"
    r"(?<![A-Za-z0-9_/.-])(?P<num>\d{1,3}(?:[.,\u00a0 ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)(?![A-Za-z0-9_/-])"
    r"(?:\s*(?:per\s+)?(?P<unit>[A-Za-zµ%][A-Za-z0-9µ%/-]*))?")
LIST_MARK_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑÂÊÔÃÕÇ¿¡*_(\"])")
DATE_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
DATE_SLASH_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b|\b(\d{4})/(\d{2})/(\d{2})\b")
WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
            "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
WORD_NUM_RE = re.compile(r"\b(%s)\b(?:\s+(?P<wunit>[A-Za-zµ%%][A-Za-z0-9µ%%/-]*))?"
                         % "|".join(WORD_NUM), re.I)

# Units that must match exactly (E6-S8): 48.8 GB is NOT grounded by a page saying 48.8 TB.
# Anything outside this set after canonicalisation is prose, not a unit, and is ignored.
_KNOWN_UNITS = {
    "b", "byte", "kb", "mb", "gb", "tb", "pb", "kib", "mib", "gib", "tib", "pib",
    "b/s", "kb/s", "mb/s", "gb/s", "bps", "kbps", "mbps", "gbps", "iops", "tps", "rps", "qps",
    "vcpu", "cpu", "core", "az", "node", "pod", "gpu",
    "ms", "s", "sec", "min", "h", "hour", "day", "month", "year",
    "gb-month", "tb-month", "gb-hour", "gb-year", "tb-year", "unit-month",
    "%", "pct", "usd", "eur", "brl", "mxn", "ars", "clp", "cny",
}
_UNIT_ALIAS = {"azs": "az", "cores": "core", "nodes": "node", "pods": "pod", "gpus": "gpu",
               "hours": "hour", "days": "day", "months": "month", "years": "year",
               "seconds": "sec", "minutes": "min", "bytes": "byte"}
_CUR_ALIAS = {"$": "USD", "US$": "USD", "us$": "USD", "€": "EUR", "R$": "BRL", "r$": "BRL"}


@dataclass
class Issue:
    claim: str
    unit: str
    reason: str   # uncited | unknown_citation | not_in_cited | url_domain


@dataclass
class Verdict:
    status: str                          # grounded | partially_verified | no_citations | abstained | no_claims
    claims: int = 0
    issues: list[Issue] = field(default_factory=list)
    cited: list[str] = field(default_factory=list)
    redacted_text: str = ""

    @property
    def ok(self) -> bool:
        return self.status in ("grounded", "abstained", "no_claims")


def verify(text: str, docs: dict[str, str], cite_prefix: str = "W",
           terms: list[str] | None = None, url_domains: list[str] | None = None,
           term_synonyms: dict[str, list[str]] | None = None) -> Verdict:
    """docs: {doc_id: full text}. cite_prefix "W" → [W:slug]; "S" → [S:source_id]."""
    stripped = text.strip()
    if stripped.startswith(ABSTAIN_TOKEN):
        return Verdict(status="abstained", redacted_text=text)

    cite_re = re.compile(r"\[%s:([^\]\s]+)\]" % re.escape(cite_prefix))
    doc_nums = {k: _num_occurrences(v) for k, v in docs.items()}
    doc_dates = {k: _dates_in(v) for k, v in docs.items()}
    # line wrapping inside a source must not break verbatim term/URL matching
    doc_low = {k: re.sub(r"\s+", " ", v.lower()) for k, v in docs.items()}
    terms = [t for t in (terms or []) if t.strip()]
    term_synonyms = term_synonyms or {}

    verdict = Verdict(status="grounded")
    cited_all: list[str] = []
    out_lines = []
    in_code = False
    heading_claims: list[tuple[int, list[tuple[str, str, str, str]]]] = []
    # A markdown heading is a title, not a sentence: the citation lives on the body
    # sentence it introduces. Heading claims are still checked — against the union
    # of pages the answer cites — so a fabricated number in a heading stays caught.
    HEADING_RE = re.compile(r"^\s*#+\s+\S")
    for line_no, line in enumerate(text.splitlines()):
        if line.strip().startswith("```"):
            in_code = not in_code
        if in_code or not line.strip() or _is_table_rule(line):
            out_lines.append(line)
            continue
        if HEADING_RE.match(line) and not cite_re.search(line):
            body = LIST_MARK_RE.sub("", line)
            body = re.sub(r"^#+\s*", "", body)
            h_claims = _claims(body, terms)
            verdict.claims += len(h_claims)
            heading_claims.append((line_no, h_claims))
            out_lines.append(line)
            continue
        units = [line] if line.lstrip().startswith("|") else SENT_SPLIT_RE.split(line)
        new_units = []
        for unit in units:
            cited = cite_re.findall(unit)
            cited_all += cited
            body = cite_re.sub(" ", unit)
            body = LIST_MARK_RE.sub("", body)
            body = re.sub(r"^#+\s*", "", body)
            claims = _claims(body, terms)
            synonyms = [term_synonyms.get(c[1], [c[1]]) if c[0] == "term" else [c[1]] for c in claims]
            verdict.claims += len(claims)
            bad: list[tuple[str, str]] = []
            known = [c for c in cited if c in docs]
            unknown = [c for c in cited if c not in docs]
            for c in unknown:                     # a citation to a page outside the pack is
                bad.append((f"[{cite_prefix}:{c}]", "unknown_citation"))   # itself an ungrounded claim
            for (kind, value, unit_tok, redact), value_syns in zip(claims, synonyms):
                if not cited:
                    bad.append((redact, "uncited"))
                elif unknown and not known:
                    bad.append((redact, "unknown_citation"))
                elif kind == "url" and url_domains is not None and not _domain_ok(value, url_domains):
                    bad.append((redact, "url_domain"))
                elif not any(_term_supported(value_syns, doc_low[c])
                             if kind == "term" else
                             _supported(kind, value, unit_tok, doc_low[c], doc_nums[c], doc_dates[c])
                             for c in known):
                    bad.append((redact, "not_in_cited"))
            for value, reason in bad:
                verdict.issues.append(Issue(value, unit.strip()[:240], reason))
                unit = _redact(unit, value)
            new_units.append(unit)
        out_lines.append(" ".join(new_units) if len(new_units) > 1 else new_units[0])

    known_any = [c for c in set(cited_all) if c in docs]
    for line_no, h_claims in heading_claims:
        for kind, value, unit_tok, redact in h_claims:
            if not cited_all:
                reason = "uncited"
            elif not known_any:
                reason = "unknown_citation"
            elif not any(_term_supported(term_synonyms.get(value, [value]) if kind == "term" else [value],
                                         doc_low[c]) if kind == "term" else
                         _supported(kind, value, unit_tok, doc_low[c], doc_nums[c], doc_dates[c])
                         for c in known_any):
                reason = "not_in_cited"
            else:
                continue
            verdict.issues.append(Issue(redact, out_lines[line_no].strip()[:240], reason))
            out_lines[line_no] = _redact(out_lines[line_no], redact)
    verdict.cited = sorted(set(cited_all))
    verdict.redacted_text = "\n".join(out_lines)
    if not cited_all and verdict.claims:
        verdict.status = "no_citations"
    elif verdict.issues:
        verdict.status = "partially_verified"
    elif verdict.claims == 0:
        verdict.status = "no_claims"
    return verdict


# ---- claim extraction -----------------------------------------------------

def _claims(body: str, terms: list[str]) -> list[tuple[str, str, str, str]]:
    """[(kind, value, unit_token, redactable_text)] — value is what to compare,
    redactable_text is what to blank out on failure (may differ for word numbers)."""
    claims: list[tuple[str, str, str, str]] = []
    urls = URL_RE.findall(body)
    for u in urls:
        claims.append(("url", u.rstrip(".,;:"), "", u.rstrip(".,;:")))
    no_urls = URL_RE.sub(" ", body)
    for m in NUM_RE.finditer(no_urls):
        num_tok = m.group("num")
        unit = m.group("unit") or ""
        cur = _canon_cur(m.group("cur")) or ""
        unit_full = f"{cur}|{unit}" if cur else unit       # currency folds into the unit key
        claims.append(("num", num_tok, unit_full, num_tok))
    for m in DATE_SLASH_RE.finditer(no_urls):
        g = m.groups()
        iso = (f"{g[3]}-{g[4]:0>2}-{g[5]:0>2}" if g[3]
               else f"{g[2]}-{g[1]:0>2}-{g[0]:0>2}")   # D/M/Y read as day-first in LATAM
        claims.append(("date", iso, "", m.group(0)))
    for m in DATE_ISO_RE.finditer(no_urls):
        claims.append(("date", m.group(0), "", m.group(0)))
    for m in WORD_NUM_RE.finditer(no_urls):
        val = WORD_NUM[m.group(1).lower()]
        claims.append(("wordnum", str(val), m.group("wunit") or "", m.group(1)))
    low = no_urls.lower()
    for t in terms:
        if re.search(r"(?<!\w)%s(?!\w)" % re.escape(t.lower()), low):
            claims.append(("term", t, "", t))
    return claims


def _canon_unit(u: str) -> str:
    u = u.lower().rstrip(".")
    u = _UNIT_ALIAS.get(u, u)
    if len(u) > 3 and u.endswith("s") and u not in _KNOWN_UNITS:
        u = u[:-1]
        u = _UNIT_ALIAS.get(u, u)
    return u


def _canon_cur(c: str | None) -> str | None:
    if not c:
        return None
    return _CUR_ALIAS.get(c) or _CUR_ALIAS.get(c.lower()) or c.upper()


def _num_values(tok: str) -> set[float]:
    """All plausible readings of a number token across EN (1,024.5) and ES/PT (1.024,5)."""
    tok = tok.replace("\u00a0", "").replace(" ", "")
    out: set[float] = set()
    for thou, dec in ((",", "."), (".", ",")):
        t = tok
        if thou in t and re.fullmatch(r"\d{1,3}(?:%s\d{3})+(?:%s\d+)?" % (re.escape(thou), re.escape(dec)), t):
            t = t.replace(thou, "")
        t = t.replace(dec, ".")
        try:
            out.add(round(float(t), 9))
        except ValueError:
            pass
    return out


def _num_occurrences(text: str) -> set[tuple[float, str]]:
    """{(numeric value, canonical unit or '')} for every number token, with currency folded
    into the unit when present ('USD' prefix and 'usd'-like units are the same dimension)."""
    out: set[tuple[float, str]] = set()
    for m in NUM_RE.finditer(text):
        unit = _canon_unit(m.group("unit") or "")
        cur = _canon_cur(m.group("cur"))
        if unit and unit not in _KNOWN_UNITS:
            unit = ""                      # prose word after the number, not a unit
        if cur:
            unit = f"{cur.lower()}|{unit}".rstrip("|")
        for v in _num_values(m.group("num")):
            out.add((v, unit))
    return out


def _dates_in(text: str) -> set[str]:
    out = {m.group(0) for m in DATE_ISO_RE.finditer(text)}
    for m in DATE_SLASH_RE.finditer(text):
        g = m.groups()
        out.add(f"{g[3]}-{g[4]:0>2}-{g[5]:0>2}" if g[3] else f"{g[2]}-{g[1]:0>2}-{g[0]:0>2}")
    return out


def _term_supported(synonyms: list[str], doc_low: str) -> bool:
    """A term claim is grounded when the term OR a configured synonym (glossary
    abbreviation, e.g. 'Object Storage Service (OBS)' ~ 'OBS') appears in the doc."""
    return any(syn.lower() in doc_low for syn in synonyms)


def _supported(kind: str, value: str, unit_tok: str, doc_low: str,
               doc_nums: set[tuple[float, str]], doc_dates: set[str]) -> bool:
    if kind == "num" or kind == "wordnum":
        vals = _num_values(value) if kind == "num" else {float(value)}
        occ = _num_occurrences_of_claim(value, unit_tok)
        if occ:
            return bool(occ & doc_nums)
        return bool(vals & {v for v, _ in doc_nums})       # claim carries no known unit
    if kind == "date":
        return value in doc_dates
    if kind == "url":
        return value.lower() in doc_low
    return value.lower() in doc_low                          # term


def _num_occurrences_of_claim(tok: str, unit_tok: str) -> set[tuple[float, str]]:
    """(value, key) pairs a claim carries; empty set = bare number (any context matches)."""
    if not unit_tok:
        return set()
    if "|" in unit_tok:
        cur, unit = unit_tok.split("|", 1)
        unit = _canon_unit(unit)                # cur arrives pre-canonicalised from _claims
    else:
        cur, unit = None, _canon_unit(unit_tok)
    if unit and unit not in _KNOWN_UNITS:
        return set()
    key = f"{cur.lower()}|{unit}".rstrip("|") if cur else unit
    return {(v, key) for v in _num_values(tok)}


def _domain_ok(url: str, allowed: list[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in allowed)


def _redact(unit: str, value: str) -> str:
    return re.sub(r"(?<![\w.,])%s(?![\w])" % re.escape(value), REDACTION, unit, count=0)


def _is_table_rule(line: str) -> bool:
    return bool(re.fullmatch(r"\s*\|?[\s:|-]+\|?\s*", line)) and "-" in line
