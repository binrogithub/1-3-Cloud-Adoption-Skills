#!/usr/bin/env python3
"""Preprocess PDF/images into text for GLM-5.1 (no multimodal).

Text PDF: extract with pypdf / pymupdf / pdfplumber (first available).
Scanned PDF / image: optional Tesseract OCR; otherwise emit VISION_NEEDED
so the Cursor orchestrator uses a multimodal model first.

Examples:
  python preprocess_doc.py report.pdf -o .cursor-hybrid/preprocessed/report.md
  python preprocess_doc.py shot.png --ocr
  python preprocess_doc.py report.pdf --pages 1-3 --max-chars 12000
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable


def _parse_pages(spec: str | None, n_pages: int) -> list[int]:
    if not spec:
        return list(range(n_pages))
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start, end = int(a), int(b)
            pages.extend(range(start - 1, end))
        else:
            pages.append(int(part) - 1)
    return [p for p in pages if 0 <= p < n_pages]


def extract_pdf_text(path: Path, pages_spec: str | None) -> tuple[list[tuple[int, str]], str]:
    """Return ([(1-based page, text), ...], backend_name)."""
    # Prefer pypdf (lightweight), then pymupdf, then pdfplumber
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        idxs = _parse_pages(pages_spec, len(reader.pages))
        out: list[tuple[int, str]] = []
        for i in idxs:
            text = reader.pages[i].extract_text() or ""
            out.append((i + 1, text))
        return out, "pypdf"
    except ImportError:
        pass

    try:
        import fitz  # pymupdf

        doc = fitz.open(str(path))
        idxs = _parse_pages(pages_spec, doc.page_count)
        out = []
        for i in idxs:
            out.append((i + 1, doc.load_page(i).get_text("text") or ""))
        return out, "pymupdf"
    except ImportError:
        pass

    try:
        import pdfplumber  # type: ignore

        with pdfplumber.open(str(path)) as pdf:
            idxs = _parse_pages(pages_spec, len(pdf.pages))
            out = []
            for i in idxs:
                out.append((i + 1, (pdf.pages[i].extract_text() or "")))
        return out, "pdfplumber"
    except ImportError as e:
        raise SystemExit(
            "No PDF library found. Install one of:\n"
            "  pip install pypdf\n"
            "  pip install pymupdf\n"
            "  pip install pdfplumber"
        ) from e


def ocr_image(path: Path, lang: str) -> str:
    try:
        from PIL import Image  # type: ignore
        import pytesseract  # type: ignore
    except ImportError as e:
        raise SystemExit(
            "OCR requires: pip install pillow pytesseract\n"
            "Also install the Tesseract binary: https://github.com/tesseract-ocr/tesseract"
        ) from e
    img = Image.open(path)
    return pytesseract.image_to_string(img, lang=lang) or ""


def looks_empty(pages: Iterable[tuple[int, str]], min_chars: int = 40) -> bool:
    total = sum(len(re.sub(r"\s+", "", t)) for _, t in pages)
    return total < min_chars


def render_markdown(
    *,
    source: Path,
    backend: str,
    pages: list[tuple[int, str]],
    max_chars: int,
    note: str = "",
) -> str:
    lines = [
        f"# Preprocessed document",
        "",
        f"- source: `{source}`",
        f"- backend: `{backend}`",
        "",
    ]
    if note:
        lines.extend([f"> {note}", ""])

    body_parts: list[str] = []
    used = 0
    for page_no, text in pages:
        chunk = text.strip()
        if not chunk:
            chunk = "(empty page / no extractable text)"
        block = f"## Page {page_no}\n\n{chunk}\n"
        if used + len(block) > max_chars:
            remain = max_chars - used
            if remain > 80:
                body_parts.append(block[:remain] + "\n\n…[truncated]\n")
            body_parts.append(
                f"\n_Truncated at max_chars={max_chars}. "
                "Re-run with --pages or higher --max-chars._\n"
            )
            break
        body_parts.append(block)
        used += len(block)

    return "\n".join(lines) + "\n" + "\n".join(body_parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="PDF/image to text for GLM briefs")
    parser.add_argument("input", help="Path to .pdf / image")
    parser.add_argument("-o", "--output", default=None, help="Output markdown path")
    parser.add_argument("--pages", default=None, help="PDF pages, e.g. 1-3,5")
    parser.add_argument("--max-chars", type=int, default=16000)
    parser.add_argument("--ocr", action="store_true", help="Force OCR for images / empty PDF")
    parser.add_argument("--ocr-lang", default="eng+chi_sim", help="Tesseract languages")
    parser.add_argument(
        "--brief-context",
        action="store_true",
        help="Also print a single-line VISION/PDF context prefix for brief.context",
    )
    args = parser.parse_args()

    src = Path(args.input).expanduser().resolve()
    if not src.is_file():
        print(f"Input not found: {src}", file=sys.stderr)
        return 2

    suffix = src.suffix.lower()
    note = ""
    backend = ""
    pages: list[tuple[int, str]] = []

    if suffix == ".pdf":
        pages, backend = extract_pdf_text(src, args.pages)
        if looks_empty(pages) or args.ocr:
            note = (
                "VISION_NEEDED: little/no extractable text (likely scanned). "
                "Orchestrator must use a multimodal model or OCR before delegating to GLM-5.1."
            )
            if args.ocr:
                # Best-effort: OCR first page via raster if pymupdf available
                try:
                    import fitz
                    from PIL import Image
                    import pytesseract
                    import io

                    doc = fitz.open(str(src))
                    idxs = _parse_pages(args.pages, doc.page_count)
                    ocr_pages: list[tuple[int, str]] = []
                    for i in idxs:
                        pix = doc.load_page(i).get_pixmap(matrix=fitz.Matrix(2, 2))
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        ocr_pages.append(
                            (i + 1, pytesseract.image_to_string(img, lang=args.ocr_lang) or "")
                        )
                    if not looks_empty(ocr_pages):
                        pages, backend, note = ocr_pages, "tesseract+pymupdf", "OCR applied"
                except Exception as e:  # noqa: BLE001
                    note += f" OCR unavailable ({type(e).__name__}: {e})."
    elif suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
        if args.ocr:
            text = ocr_image(src, args.ocr_lang)
            pages = [(1, text)]
            backend = "tesseract"
            if looks_empty(pages):
                note = "VISION_NEEDED: OCR returned empty; use a multimodal model."
        else:
            pages = [(1, "")]
            backend = "none"
            note = (
                "VISION_NEEDED: image input. Use a Cursor multimodal model to describe/OCR, "
                "then put the result into brief.context (or re-run with --ocr)."
            )
    else:
        print(f"Unsupported type: {suffix}", file=sys.stderr)
        return 2

    md = render_markdown(
        source=src, backend=backend, pages=pages, max_chars=args.max_chars, note=note
    )

    if args.output:
        out = Path(args.output).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"Wrote {out}")
    else:
        print(md)

    if args.brief_context:
        # Compact prefix for delegate brief.context
        plain = re.sub(r"\s+", " ", md)[:4000]
        prefix = "VISION_NEEDED" if "VISION_NEEDED" in note else "DOC_TEXT"
        print(f"\n--- brief.context ---\n{prefix}: {plain}", file=sys.stderr)

    if "VISION_NEEDED" in note and looks_empty(pages):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
