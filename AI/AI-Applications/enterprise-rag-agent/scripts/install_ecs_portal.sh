#!/usr/bin/env bash
set -euo pipefail

CSS_URL="${CSS_URL:-http://127.0.0.1:9200}"
PORTAL_INDEX="${PORTAL_INDEX:-government-documents}"
PORTAL_PORT="${PORTAL_PORT:-8000}"
PORTAL_ROOT="${PORTAL_ROOT:-/opt/government-rag/portal}"
VENV="${VENV:-/opt/government-rag/venv}"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3-venv python3-pip curl

mkdir -p "${PORTAL_ROOT}/templates" "${PORTAL_ROOT}/uploads" "$(dirname "${VENV}")"
if [ ! -x "${VENV}/bin/python" ]; then
  python3 -m venv "${VENV}"
fi
"${VENV}/bin/pip" install --upgrade pip wheel
"${VENV}/bin/pip" install flask gunicorn opensearch-py pypdf python-docx werkzeug

cat >"${PORTAL_ROOT}/app.py" <<'PY'
from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from flask import Flask, flash, redirect, render_template, request, url_for
from opensearchpy import OpenSearch
from pypdf import PdfReader
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
INDEX_NAME = os.environ.get("PORTAL_INDEX", "government-documents")
CSS_URL = os.environ.get("CSS_URL", "http://127.0.0.1:9200")
MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", "50")) * 1024 * 1024
ALLOWED_SUFFIXES = {".txt", ".md", ".pdf", ".docx"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.secret_key = os.environ.get("PORTAL_SECRET_KEY", "change-me-for-demo")
client = OpenSearch(hosts=[CSS_URL], timeout=10, max_retries=2, retry_on_timeout=True)


def ensure_index() -> None:
    if client.indices.exists(index=INDEX_NAME):
        return
    client.indices.create(
        index=INDEX_NAME,
        body={
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
            "mappings": {
                "properties": {
                    "doc_id": {"type": "keyword"},
                    "chunk_id": {"type": "keyword"},
                    "title": {"type": "text"},
                    "content": {"type": "text"},
                    "filename": {"type": "keyword"},
                    "uploaded_at": {"type": "date"},
                    "chunk_index": {"type": "integer"},
                    "hash": {"type": "keyword"},
                }
            },
        },
    )


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix == ".docx":
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    raise ValueError(f"Unsupported file type: {suffix}")


def chunks(text: str, size: int = 1200, overlap: int = 180):
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return
    start = 0
    while start < len(normalized):
        yield normalized[start : start + size]
        if start + size >= len(normalized):
            break
        start += size - overlap


def index_file(path: Path) -> int:
    ensure_index()
    text = extract_text(path)
    doc_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    doc_id = doc_hash[:16]
    client.delete_by_query(
        index=INDEX_NAME,
        body={"query": {"term": {"doc_id": doc_id}}},
        conflicts="proceed",
        refresh=True,
        ignore=[404],
    )
    count = 0
    now = datetime.now(timezone.utc).isoformat()
    for idx, chunk in enumerate(chunks(text) or [], start=1):
        body = {
            "doc_id": doc_id,
            "chunk_id": f"{doc_id}-{idx:04d}",
            "title": path.stem,
            "content": chunk,
            "filename": path.name,
            "uploaded_at": now,
            "chunk_index": idx,
            "hash": doc_hash,
        }
        client.index(index=INDEX_NAME, id=body["chunk_id"], body=body, refresh=True)
        count += 1
    return count


def search_docs(query: str):
    ensure_index()
    if not query.strip():
        return []
    resp = client.search(
        index=INDEX_NAME,
        body={
            "size": 10,
            "query": {"multi_match": {"query": query, "fields": ["title^2", "content"], "type": "best_fields"}},
            "highlight": {"fields": {"content": {"fragment_size": 220, "number_of_fragments": 2}}},
        },
    )
    results = []
    for hit in resp.get("hits", {}).get("hits", []):
        src = hit["_source"]
        snippets = hit.get("highlight", {}).get("content", []) or [src.get("content", "")[:240]]
        results.append({"score": hit["_score"], "source": src, "snippets": snippets})
    return results


@app.route("/", methods=["GET"])
def home():
    query = request.args.get("q", "")
    return render_template("index.html", query=query, results=search_docs(query) if query else [])


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("document")
    if not file or not file.filename:
        flash("Choose a document to upload.", "error")
        return redirect(url_for("home"))
    filename = secure_filename(file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        flash("Supported types: txt, md, pdf, docx.", "error")
        return redirect(url_for("home"))
    target = UPLOAD_DIR / filename
    file.save(target)
    try:
        count = index_file(target)
        flash(f"Uploaded and indexed {filename}: {count} chunks.", "ok")
    except Exception as exc:
        flash(f"Upload saved but indexing failed: {exc}", "error")
    return redirect(url_for("home"))


@app.route("/health", methods=["GET"])
def health():
    ensure_index()
    return {"ok": True, "index": INDEX_NAME, "css": CSS_URL}
PY

cat >"${PORTAL_ROOT}/templates/index.html" <<'HTML'
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Enterprise RAG Portal</title>
  <style>
    :root { color-scheme: light; --ink:#172026; --muted:#60707c; --line:#d9e1e7; --fill:#f5f7f9; --accent:#0f766e; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Arial, sans-serif; color:var(--ink); background:#fff; }
    header { border-bottom:1px solid var(--line); padding:18px 28px; display:flex; align-items:center; justify-content:space-between; gap:16px; }
    h1 { font-size:20px; margin:0; font-weight:700; letter-spacing:0; }
    main { max-width:1120px; margin:0 auto; padding:28px; }
    .bar { display:grid; grid-template-columns: 1fr auto; gap:10px; margin-bottom:20px; }
    input[type="search"], input[type="file"] { width:100%; border:1px solid var(--line); border-radius:6px; padding:11px 12px; font-size:15px; background:#fff; }
    button { border:0; border-radius:6px; padding:11px 16px; background:var(--accent); color:#fff; font-weight:650; cursor:pointer; white-space:nowrap; }
    section { margin-top:28px; }
    .upload { border:1px solid var(--line); background:var(--fill); border-radius:8px; padding:16px; display:grid; grid-template-columns:1fr auto; gap:10px; align-items:center; }
    .msg { border-radius:6px; padding:10px 12px; margin:8px 0; font-size:14px; }
    .ok { background:#e7f6ee; color:#11613a; } .error { background:#fdecec; color:#9b1c1c; }
    .result { border-top:1px solid var(--line); padding:18px 0; }
    .meta { color:var(--muted); font-size:13px; margin:4px 0 10px; }
    mark, em { background:#fff3b0; padding:1px 2px; font-style:normal; }
    .snippet { line-height:1.55; margin:8px 0; }
    @media (max-width: 700px) { header, main { padding-left:16px; padding-right:16px; } .bar, .upload { grid-template-columns:1fr; } button { width:100%; } }
  </style>
</head>
<body>
<header><h1>Enterprise RAG Portal</h1><span>Upload + CSS Search Demo</span></header>
<main>
  {% with messages = get_flashed_messages(with_categories=true) %}
    {% for category, message in messages %}<div class="msg {{ category }}">{{ message }}</div>{% endfor %}
  {% endwith %}
  <form class="bar" method="get" action="/">
    <input type="search" name="q" value="{{ query }}" placeholder="Search uploaded regulations, policies, procedures, and cases">
    <button type="submit">Search</button>
  </form>
  <form class="upload" method="post" action="/upload" enctype="multipart/form-data">
    <input type="file" name="document" accept=".txt,.md,.pdf,.docx">
    <button type="submit">Upload & Index</button>
  </form>
  <section>
    {% if query %}<div class="meta">{{ results|length }} results for "{{ query }}"</div>{% endif %}
    {% for item in results %}
      <article class="result">
        <strong>{{ item.source.title }}</strong>
        <div class="meta">{{ item.source.filename }} · chunk {{ item.source.chunk_index }} · score {{ item.score|round(2) }}</div>
        {% for snippet in item.snippets %}<p class="snippet">{{ snippet|safe }}</p>{% endfor %}
      </article>
    {% endfor %}
  </section>
</main>
</body>
</html>
HTML

cat >/etc/systemd/system/enterprise-rag-portal.service <<SERVICE
[Unit]
Description=Enterprise RAG Upload/Search Portal
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=${PORTAL_ROOT}
Environment=CSS_URL=${CSS_URL}
Environment=PORTAL_INDEX=${PORTAL_INDEX}
Environment=PORTAL_SECRET_KEY=change-me-for-demo
ExecStart=${VENV}/bin/gunicorn -w 2 -b 0.0.0.0:${PORTAL_PORT} app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

cat >"${PORTAL_ROOT}/README.md" <<EOF
# Enterprise RAG Portal

URL: http://<ecs-public-ip>:${PORTAL_PORT}
CSS endpoint: ${CSS_URL}
Index: ${PORTAL_INDEX}
Uploads: ${PORTAL_ROOT}/uploads

Supported upload types: txt, md, pdf, docx.

Operations:
- Health: curl http://127.0.0.1:${PORTAL_PORT}/health
- Logs: journalctl -u enterprise-rag-portal.service -f
- Restart: systemctl restart enterprise-rag-portal.service
EOF

systemctl daemon-reload
systemctl enable --now enterprise-rag-portal.service
systemctl --no-pager --full status enterprise-rag-portal.service | sed -n '1,18p'
