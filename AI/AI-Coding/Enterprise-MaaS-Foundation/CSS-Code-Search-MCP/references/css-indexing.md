# CSS Indexing Strategy

## Chunking

Files are split into ~8 KB chunks with 500-char overlap to balance:

- **Search precision**: chunks small enough for relevant snippets to score high.
- **Context preservation**: 500-char overlap prevents losing context at chunk boundaries.
- **Token budget**: each chunk fits within typical LLM context windows for tool results.

## Metadata Extraction

Path segments are mapped to structured fields:

```
Big-Data/AI-Knowledge-Base/CSS-Autoscaling-Benchmark-Skill/config.py
│  │                │          │
│  │                │          └─ file_name
│  │                └─ skill_name
│  └─ subcategory
└─ category
```

This enables filtered queries like `category=AI AND skill_name=CSS-Autoscaling-Benchmark-Skill`.

## Index Mapping

| Field | Type | Purpose |
|-------|------|---------|
| `repo_path` | keyword | Exact match for get_file; also displayed to user |
| `file_name` | keyword | Filter and boost in search (3x weight) |
| `category` | keyword | Top-level filter (AI, Big-Data, etc.) |
| `subcategory` | keyword | Second-level filter |
| `skill_name` | keyword | Skill-level filter (2x weight) |
| `ext` | keyword | File extension filter |
| `chunk_index` | integer | Ordering chunks for get_file |
| `total_chunks` | integer | UI hint for chunk count |
| `content` | text (standard) | Primary search field (2x weight) |
| `content_search` | text (standard, fielddata) | Supports aggregations on text |
| `line_start` / `line_end` | integer | Line number range for UI display |

## Search Scoring

Multi-match query with field weights:

```json
{
  "multi_match": {
    "query": "LiteLLM gateway",
    "fields": ["content^2", "file_name^3", "skill_name^2", "category", "subcategory"]
  }
}
```

- `file_name^3`: exact file name matches rank highest.
- `content^2` and `skill_name^2`: content and skill name are equally important.
- `category` and `subcategory`: lower weight, used for relevance tuning.

## Highlighting

Search results include highlighted snippets:

```json
{
  "highlight": {
    "fields": {"content": {"fragment_size": 200, "number_of_fragments": 2}},
    "pre_tags": [">>>"],
    "post_tags": ["<<<"]
  }
}
```

Two fragments of 200 chars each, with `>>>match<<<` markers.

## Re-indexing

The indexer deletes the existing index before re-creating it. This is safe for small repos (< 1000 files) where indexing completes in seconds. For large repos, consider using an alias-based zero-downtime reindex:

1. Create new index with timestamp suffix.
2. Bulk-index into the new index.
3. Atomically swap the alias.
4. Delete the old index.
