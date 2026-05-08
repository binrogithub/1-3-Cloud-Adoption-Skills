# Architecture Reference

## Target Customers

Use this architecture for public-sector and regulated organizations with large legal, policy, benefits, tax, court, healthcare, utility, or enterprise procedure document collections, including agencies similar to Guyana Supreme Court, Serpro, SAT, DIAN, PCM/gob.pe, IMSS, and Dataprev.

## Component Roles

- OBS stores immutable originals, normalized text, OCR outputs, extracted tables, and parse artifacts.
- RAGFlow handles complex document parsing, OCR, PDF layout, table extraction, visual chunk review, chunk QA, and citation traceability.
- LlamaIndex orchestrates retrieval, metadata filtering, reranking, workflow steps, tools, agent behavior, and citation assembly.
- CSS/OpenSearch stores keyword and vector indexes for hybrid search.
- GaussDB/RDS stores document metadata, ingestion state, ACL policy mappings, audit events, and evaluation runs.
- Huawei Cloud MaaS provides LLM inference for answer synthesis, query rewriting, classification, and judge workflows.
- ECS demo portal provides a fast upload/search interface when the customer needs a clickable proof of value before the full RAGFlow UI is ready.

## Demo Deployment Defaults

- Region/project: default to `la-north-2`; require `HWC_PROJECT_ID` when invoking SDKs.
- OBS: create a private bucket for raw documents and parse artifacts.
- CSS/OpenSearch: use one data node, `ess.spec-4u8g`, 40 GB disk, Elasticsearch/OpenSearch 7.10.x when available.
- CSS disk fallback: try the smallest supported disk type first, but switch from `COMMON` to `HIGH` when the region reports disk sold out.
- ECS: use a general-purpose Ubuntu ECS, attach a small traffic-billed EIP, and restrict inbound security group rules to the current operator CIDR.
- VPC: create a new VPC for clean demos only when quota allows; otherwise reuse an existing VPC/subnet and create a dedicated security group.

## Data Flow

1. Ingest PDF, Word, Excel, scanned image, and web captures into OBS.
2. Register metadata: source system, department, classification, language, effective date, retention class, and owner.
3. Parse with RAGFlow or equivalent: OCR, layout, headings, tables, page spans, and visual chunk validation.
4. Normalize chunks with stable `doc_id`, `chunk_id`, page/section anchors, language, and ACL fields.
5. Index chunks in CSS/OpenSearch with BM25 text fields, vector embeddings, metadata filters, and citation anchors.
6. Retrieve with LlamaIndex using keyword retrieval, vector retrieval, ACL filters, date/jurisdiction filters, and reranking.
7. Generate answers through Huawei Cloud MaaS using evidence-only prompts and citation constraints.
8. Log query, filters, retrieved chunks, cited chunks, model version, latency, and refusal reason.

## RAGFlow + LlamaIndex + MaaS Pattern

- Use RAGFlow for document ingestion quality: OCR, layout recovery, table recognition, and visual chunk validation.
- Export or synchronize approved chunks and metadata into CSS/OpenSearch.
- Use LlamaIndex as the retrieval and agent layer: hybrid retrieval, metadata filters, reranking, tool calls, and citation assembly.
- Use Huawei Cloud MaaS as the LLM backend for answer synthesis, query rewriting, classification, and evaluation judges.
- Keep prompts evidence-only and citation-first; do not let MaaS answer from model memory for regulated facts.

## KPI Defaults

- Query response: under 5 seconds for normal policy/procedure queries.
- Citation hit rate: above 90 percent on citation evaluation questions.
- Hallucination: reduce unsupported claims through strict evidence-only prompting and trap-question tests.
- Operational impact: reduce law/procedure lookup time from hours to minutes.
