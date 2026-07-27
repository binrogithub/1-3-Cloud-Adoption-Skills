# Vision & PDF routing (GLM-5.1 has no multimodal)

GLM-5.1 / 5.2 on Huawei MaaS are **text-only**. Images and scanned PDFs must be
converted to text **before** `delegate.py`.

## Decision table

| Input | Orchestrator (Cursor) | Delegate (GLM) |
|-------|----------------------|----------------|
| Screenshot / photo / UI image | Multimodal model describes/OCR → text | Receives text in `brief.context` only |
| Digital PDF (selectable text) | Run `preprocess_doc.py` | Summarize / codegen from extract |
| Scanned PDF | Multimodal **or** `preprocess_doc.py --ocr` | Same as text |
| Mixed (charts + text) | Vision for chart pages; extract for text pages | Merged context |

## Hard rules

1. **Never** attach raw images to a GLM brief.
2. If the user message contains images → **do not delegate** until a text summary exists.
3. Prefer extractors over vision for text PDFs (cheaper, more accurate for code/docs).
4. Truncate with `--max-chars` / `--pages`; never dump a whole book into one brief.

## Commands

```powershell
pip install pypdf
# optional OCR:
# pip install pillow pytesseract pymupdf

python $HOME/.cursor/skills/cursor-maas-delegate-router/scripts/preprocess_doc.py `
  .\docs\spec.pdf -o .\.cursor-hybrid\preprocessed\spec.md --pages 1-5

# Image without OCR → exits 3 with VISION_NEEDED (orchestrator must use vision model)
python .../preprocess_doc.py .\shot.png
```

## Brief pattern after preprocess

```json
{
  "goal": "Implement API fields listed in the spec excerpt",
  "files": ["src/api.ts"],
  "acceptance": "types compile",
  "context": "DOC_TEXT: ...paste or load preprocessed markdown...",
  "constraints": ["Do not invent fields not present in context"]
}
```

For images processed by a multimodal model in-session, prefix with `VISION_SUMMARY:`.
