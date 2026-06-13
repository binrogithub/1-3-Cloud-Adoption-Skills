#!/usr/bin/env python3
"""Index a Git repository into CSS/OpenSearch for code search.

Usage:
    python3 index_repo_to_css.py <repo_dir> <css_url> [index_name]

Example:
    python3 index_repo_to_css.py /tmp/1-3-Cloud-Adoption-Skills http://192.168.0.23:9200
    python3 index_repo_to_css.py /tmp/my-repo http://192.168.0.23:9200 my-repo-code
"""

import json
import os
import sys
from pathlib import Path

import requests

REPO_DIR = Path(sys.argv[1])
CSS_URL = sys.argv[2]
INDEX_NAME = sys.argv[3] if len(sys.argv) > 3 else REPO_DIR.name.lower().replace("-", "-")
CHUNK_SIZE = 8000
OVERLAP = 500

CODE_EXTS = {
    ".py", ".js", ".ts", ".java", ".go", ".sh", ".tf", ".yaml", ".yml",
    ".json", ".sql", ".cob", ".cbl", ".jcl", ".md", ".txt", ".toml",
    ".cfg", ".ini", ".env", ".rst", ".xml", ".html", ".css", ".scss",
    ".dockerfile", ".gitignore", ".editorconfig", ".properties",
}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".cache", ".venv", "venv", ".tox", "dist", "build"}


def should_index(path: Path) -> bool:
    if any(d in path.parts for d in SKIP_DIRS):
        return False
    if path.suffix.lower() in CODE_EXTS:
        return True
    if path.name.lower() in {"dockerfile", "makefile", "readme", "skill", "license"}:
        return True
    return False


def read_file(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> list[str]:
    if len(text) <= size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def create_index(css_url: str, index: str) -> bool:
    mapping = {
        "mappings": {
            "properties": {
                "repo_path": {"type": "keyword"},
                "file_name": {"type": "keyword"},
                "category": {"type": "keyword"},
                "subcategory": {"type": "keyword"},
                "skill_name": {"type": "keyword"},
                "ext": {"type": "keyword"},
                "chunk_index": {"type": "integer"},
                "total_chunks": {"type": "integer"},
                "content": {"type": "text", "analyzer": "standard"},
                "content_search": {"type": "text", "analyzer": "standard", "fielddata": True},
                "line_start": {"type": "integer"},
                "line_end": {"type": "integer"},
            }
        },
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    }
    r = requests.put(f"{css_url}/{index}", headers={"Content-Type": "application/json"}, json=mapping)
    print(f"Create index: {r.status_code} {r.text[:200]}")
    return r.status_code in (200, 201)


def extract_metadata(rel_path: str) -> dict:
    parts = Path(rel_path).parts
    return {
        "category": parts[0] if len(parts) > 0 else "",
        "subcategory": parts[1] if len(parts) > 1 else "",
        "skill_name": parts[2] if len(parts) > 2 else "",
    }


def index_file(css_url: str, index: str, rel_path: str, content: str, metadata: dict) -> int:
    chunks = chunk_text(content)
    ext = Path(rel_path).suffix.lstrip(".")
    file_name = Path(rel_path).name
    bulk_lines = []

    for i, chunk in enumerate(chunks):
        lines_before = content[: i * (CHUNK_SIZE - OVERLAP)].count("\n") if i > 0 else 0
        lines_in_chunk = chunk.count("\n") + 1
        doc = {
            "repo_path": rel_path, "file_name": file_name, "ext": ext,
            "chunk_index": i, "total_chunks": len(chunks),
            "content": chunk, "content_search": chunk,
            "line_start": lines_before + 1, "line_end": lines_before + lines_in_chunk,
            **metadata,
        }
        bulk_lines.append(json.dumps({"index": {"_index": index}}))
        bulk_lines.append(json.dumps(doc))

    if not bulk_lines:
        return 0

    r = requests.post(
        f"{css_url}/_bulk",
        headers={"Content-Type": "application/x-ndjson"},
        data="\n".join(bulk_lines) + "\n",
    )
    if r.status_code != 200:
        print(f"  Bulk error for {rel_path}: {r.status_code}")
        return 0
    if r.json().get("errors"):
        errors = [item for item in r.json().get("items", []) if item.get("index", {}).get("status", 200) >= 400]
        print(f"  {len(errors)} errors in {rel_path}")
    return len(chunks)


def main():
    print(f"Indexing {REPO_DIR} into {CSS_URL}/{INDEX_NAME}")

    r = requests.delete(f"{CSS_URL}/{INDEX_NAME}")
    if r.status_code in (200, 201):
        print(f"Deleted existing index {INDEX_NAME}")

    if not create_index(CSS_URL, INDEX_NAME):
        print("Failed to create index, aborting")
        sys.exit(1)

    files = sorted(p for p in REPO_DIR.rglob("*") if p.is_file() and should_index(p))
    print(f"Found {len(files)} files to index")

    total_chunks = 0
    for i, fpath in enumerate(files):
        rel = str(fpath.relative_to(REPO_DIR))
        content = read_file(fpath)
        if not content or not content.strip():
            continue
        metadata = extract_metadata(rel)
        n = index_file(CSS_URL, INDEX_NAME, rel, content, metadata)
        total_chunks += n
        if (i + 1) % 20 == 0 or i == len(files) - 1:
            print(f"  [{i+1}/{len(files)}] {rel} -> {n} chunks (total: {total_chunks})")

    print(f"\nDone: {len(files)} files, {total_chunks} chunks indexed")
    r = requests.get(f"{CSS_URL}/{INDEX_NAME}/_count")
    print(f"Index doc count: {r.json().get('count', 'error')}")


if __name__ == "__main__":
    main()
