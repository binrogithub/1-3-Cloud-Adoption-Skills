---
name: enterprise-rag-agent
description: Build enterprise RAG knowledge agents for public-sector and regulated document collections. Use when Codex must design, provision, or generate an Enterprise RAG Agent Pack for laws, policies, official correspondence, PDFs, scans, procedures, FAQ, court/tax/social-security/healthcare/public-utility knowledge bases, multilingual Portuguese/Spanish/English cited answers, RAGFlow document parsing and OCR, LlamaIndex retrieval agents and workflows, OpenSearch/CSS hybrid retrieval, OBS storage, GaussDB/RDS metadata and audit, Huawei Cloud MaaS LLM inference, ECS demo portals for document upload and search, ACL enforcement, citation generation, evidence-chain prompts, evaluation sets, Terraform deployment, or anti-hallucination RAG workflows.
---

# Enterprise RAG Agent

Use this skill to produce implementation-ready enterprise RAG assets, not generic chatbot advice. Keep outputs evidence-grounded, multilingual, auditable, and permission-aware.

## Default Workflow

1. Clarify the agency, languages, document classes, security model, hosting region, and KPI target only when missing from the task.
2. Generate an Enterprise RAG Agent Pack using `scripts/scaffold_pack.py` when the user asks for implementation assets or a starter project.
3. Use `references/architecture.md` for the canonical Huawei Cloud architecture and component responsibilities.
4. Use `references/metadata-and-acl.md` before defining schemas, filters, roles, or audit fields.
5. Use `references/prompts.md` when writing answer, citation, refusal, and evidence-chain prompts.
6. Use `references/evaluation.md` when creating evaluation spreadsheets, test cases, acceptance criteria, or KPI reports.
7. Use `references/huawei-cloud-deployment.md` before provisioning Huawei Cloud resources or debugging OBS/CSS/ECS/RAGFlow deployments.
8. Include an ECS portal when the user asks for a demo UI, document upload, or search experience; follow the portal pattern in `references/huawei-cloud-deployment.md`.

## Required Pack Shape

Generate or preserve these deliverables unless the user narrows scope:

- `sample_documents/`
- `ingestion_pipeline.py`
- `index_schema.json`
- `rag_prompt.md`
- `citation_prompt.md`
- `evaluation_set.xlsx` or `evaluation_set.csv`
- `demo_ui/`
- `deployment_terraform/`

## Architecture Defaults

Use this baseline unless the user provides a different stack:

```text
PDF / Word / Excel / Scan / Web
        -> OBS file lake
        -> RAGFlow document parsing, OCR, layout, table extraction, visual chunk review
        -> Chunk + metadata + ACL
        -> CSS/OpenSearch hybrid keyword + vector search
        -> LlamaIndex retrieval agent, workflow, rerank, citation assembly
        -> Huawei Cloud MaaS LLM inference
        -> Answer + citations + evidence chain
```

Default Huawei Cloud region is `la-north-2`. Never hardcode cloud credentials in generated files. Use environment variables such as `HWC_REGION`, `HWC_ACCESS_KEY_ID`, and `HWC_SECRET_ACCESS_KEY`, or the customer's secret manager.

When creating demo infrastructure, default to a private OBS bucket, a single-node CSS/OpenSearch cluster, and one general-purpose ECS with an EIP restricted by security group to the operator's current public IP. Prefer reusing an existing VPC/subnet if VPC router quota is exhausted.

When creating a fast demo, deploy a lightweight portal on ECS before full RAGFlow startup if Docker image pulls are slow. The portal should support upload of `.txt`, `.md`, `.pdf`, and `.docx`, extract text, chunk content, index into CSS/OpenSearch, and provide keyword search with highlighted snippets. Keep it clearly labeled as a demo portal, not a production access-control system.

## Guardrails

- Require citations for factual answers.
- Refuse or ask for clarification when retrieved evidence is insufficient.
- Apply ACL filters before retrieval and again before response construction.
- Separate legal/policy interpretation from operational instructions when the source text supports only one of them.
- Preserve effective dates and jurisdiction in answers involving laws, policy, tax, benefits, healthcare, court processes, or public services.
- Support Portuguese, Spanish, and English queries; answer in the user's language unless instructed otherwise.

## Resources

- `scripts/scaffold_pack.py`: copy the starter Enterprise RAG Agent Pack into a target folder.
- `scripts/provision_huawei_demo.py`: provision a minimal Huawei Cloud OBS + CSS + ECS demo using environment variables and non-secret state.
- `scripts/install_ecs_portal.sh`: install a lightweight upload/search portal on a provisioned ECS and connect it to CSS/OpenSearch.
- `assets/enterprise-rag-agent-pack/`: starter pack templates.
- `references/architecture.md`: architecture and data flow.
- `references/metadata-and-acl.md`: metadata, permissions, and audit rules.
- `references/prompts.md`: RAG and citation prompt templates.
- `references/evaluation.md`: evaluation dataset design and KPI checks.
- `references/huawei-cloud-deployment.md`: deployment defaults, SDK notes, fallback choices, and verification commands.
