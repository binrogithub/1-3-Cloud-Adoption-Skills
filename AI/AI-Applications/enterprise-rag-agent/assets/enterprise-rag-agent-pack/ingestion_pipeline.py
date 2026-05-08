#!/usr/bin/env python3
"""Starter ingestion pipeline for an Enterprise RAG Agent Pack.

This file is intentionally provider-light. Replace placeholder parser,
embedding, and OpenSearch calls with the customer's approved SDKs.
Credentials must come from environment variables or a secret manager.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_REGION = os.environ.get("HWC_REGION", "la-north-2")


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    chunk_id: str
    title: str
    content: str
    department: str
    security_level: str
    language: str
    effective_date: str
    source_uri: str
    page_start: int | None = None
    page_end: int | None = None
    section_path: str | None = None
    document_type: str = "policy"
    jurisdiction: str = "unknown"
    acl_roles: tuple[str, ...] = ("public",)
    acl_departments: tuple[str, ...] = ("public",)

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


def parse_document(path: Path) -> Iterable[Chunk]:
    """Replace with RAGFlow or a LlamaParse-like parser."""
    text = path.read_text(encoding="utf-8")
    doc_id = path.stem.upper().replace("-", "_")
    yield Chunk(
        doc_id=doc_id,
        chunk_id=f"{doc_id}-C001",
        title=path.stem.replace("-", " ").title(),
        content=text,
        department=os.environ.get("DEFAULT_DEPARTMENT", "sample-agency"),
        security_level=os.environ.get("DEFAULT_SECURITY_LEVEL", "public"),
        language=os.environ.get("DEFAULT_LANGUAGE", "en"),
        effective_date=os.environ.get("DEFAULT_EFFECTIVE_DATE", "2026-01-01"),
        source_uri=f"obs://raw-documents/{path.name}",
    )


def prepare_index_record(chunk: Chunk) -> dict:
    record = asdict(chunk)
    record["hash"] = chunk.hash
    record["acl_roles"] = list(chunk.acl_roles)
    record["acl_departments"] = list(chunk.acl_departments)
    record["embedding"] = []  # Fill with the approved embedding model output.
    return record


def main() -> None:
    source_dir = Path(os.environ.get("SOURCE_DOCUMENT_DIR", "sample_documents"))
    output_path = Path(os.environ.get("OUTPUT_JSONL", "chunks.jsonl"))
    records = []
    for path in sorted(source_dir.glob("*.txt")):
        records.extend(prepare_index_record(chunk) for chunk in parse_document(path))
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"Wrote {len(records)} chunk records for region {DEFAULT_REGION} to {output_path}")


if __name__ == "__main__":
    main()
