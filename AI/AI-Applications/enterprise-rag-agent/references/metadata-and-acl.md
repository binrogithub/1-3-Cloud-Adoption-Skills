# Metadata and ACL Reference

## Required Index Fields

- `doc_id`: stable document identifier.
- `chunk_id`: stable chunk identifier unique within the index.
- `department`: owning agency, ministry, court, tax office, healthcare unit, or business domain.
- `security_level`: public, internal, confidential, restricted, or customer-defined classification.
- `effective_date`: date the law, policy, procedure, or official guidance became effective.
- `language`: ISO-style language tag such as `en`, `es`, or `pt`.

## Strongly Recommended Fields

- `source_uri`: OBS URI or source system URI.
- `title`: official document title.
- `document_type`: law, policy, official_correspondence, faq, procedure, historical_case, form, table, web_page.
- `jurisdiction`: country, state/province, municipality, court, or agency scope.
- `version`: source version or revision identifier.
- `page_start`, `page_end`: source page span.
- `section_path`: heading or clause path.
- `published_date`, `expiry_date`: lifecycle controls when available.
- `acl_roles`, `acl_departments`: searchable allow lists.
- `hash`: checksum for provenance and tamper detection.

## Permission Rules

- Filter by user role, department, and security level before retrieval.
- Re-check all candidate chunks before answer generation.
- Never cite or summarize chunks the user is not allowed to see.
- Return a permission-safe refusal when relevant documents exist but are not accessible.
- Log denials without leaking restricted titles or snippets.

## Audit Events

Record query text, user or service identity, resolved role, filters applied, retrieved chunk IDs, cited chunk IDs, model ID, latency, refusal reason, and final answer hash. Avoid logging sensitive source text unless the customer explicitly requires and permits it.
