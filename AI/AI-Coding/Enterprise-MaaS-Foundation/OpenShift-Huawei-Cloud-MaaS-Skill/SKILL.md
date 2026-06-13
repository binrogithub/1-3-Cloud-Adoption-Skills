---
name: Openshift+Huawei-Cloud-MaaS-Skill
description: Use this skill when integrating OpenShift Dev Spaces or Eclipse Che browser-based VS Code with Cline and Huawei Cloud MaaS. It covers OpenAI-compatible MaaS configuration, Cline provider setup, verification, compatibility checks, and troubleshooting for browser-based development environments.
---

# Openshift+Huawei-Cloud-MaaS-Skill

## Overview

Use this skill for browser-based developer workspaces where the editor runs inside OpenShift Dev Spaces or Eclipse Che and Cline must call Huawei Cloud MaaS through an OpenAI-compatible endpoint.

Prefer Red Hat OpenShift Dev Spaces on real OCP when available. If local OpenShift is not feasible because CRC or nested virtualization is unavailable, use the same integration pattern on Eclipse Che as the practical fallback for demos and validation.

## Use This Skill When

- You need to connect `Cline` to `Huawei Cloud MaaS`.
- The editor is `VS Code - Open Source` inside `OpenShift Dev Spaces` or `Eclipse Che`.
- You need a repeatable `OpenAI Compatible` configuration.
- You need to separate platform issues from MaaS API issues.
- You need to debug why Cline can reach a provider but still fails during agent or tool execution.

## Default Workflow

Follow this sequence by default:

1. Confirm the workspace platform shape:
   - real `OpenShift Dev Spaces` on OCP, or
   - `Eclipse Che` fallback on Kubernetes.
2. Confirm the browser editor is `che-code` / browser VS Code and that Cline is already installed.
3. Configure Cline with the minimum viable provider settings first.
4. Verify MaaS transport and authentication independently of Cline behavior.
5. Validate a simple text-only response.
6. Validate agentic or tool-driven Cline behavior only after simple text succeeds.
7. If failures appear, classify them as:
   - editor/UI config issue
   - MaaS auth or endpoint issue
   - OpenAI-compatible but not fully Cline-compatible behavior

## Core Rules

- Start with the smallest possible Cline configuration:
  - provider
  - base URL
  - API key
  - model
- Do not enable optional capabilities until plain text requests work.
- Treat `OpenAI compatible` as a transport contract, not a guarantee of full Cline agent compatibility.
- Distinguish:
  - `basic chat works`
  - `tool calling works`
  - `full Cline workflow works`
- Avoid heavy or failure-prone `postStart` hooks in Dev Spaces workspaces when validating integrations. If a package install or model test is non-essential for workspace startup, run it manually after the workspace opens.
- Keep examples sanitized:
  - use `<region>`, `<base_url>`, `<api_key>`, `<model>`
  - do not embed real tokens or tenant-specific hostnames in reusable output

## Cline Configuration Pattern

In Cline, use `OpenAI Compatible` as the provider type.

Minimum fields:

- `Base URL`: `https://api-<region>.modelarts-maas.com/openai/v1`
- `API Key`: MaaS API key
- `Model`: provider-specific model ID such as `<model_id>`; for example `glm-5.1`

Recommended first-pass settings:

- keep context-window overrides unset unless required
- disable optional image or computer-use features during first verification
- use a simple prompt such as `Reply with exactly: ok`

If the user cannot find the Cline config UI, read [references/devspaces-cline.md](references/devspaces-cline.md).

If the user needs Huawei MaaS field mapping, read [references/maas-openai-compatible.md](references/maas-openai-compatible.md).

## Verification Workflow

Run verification in this order:

1. Endpoint and auth:
   - use `scripts/verify_maas_openai_compatible.sh`
2. Plain text model response:
   - send a minimal prompt
3. Browser editor and Cline UI:
   - confirm provider settings were actually saved
4. Agent compatibility:
   - only after text-only calls succeed

Use `scripts/print_cline_config_example.sh` when you need a clean Cline settings block for the user.

## Troubleshooting Map

- `401` or `403`:
  - key invalid, wrong auth scope, or rejected bearer token
- `404`:
  - base URL or path mismatch, often missing or duplicated `/openai/v1`
- `model not found`:
  - model ID mismatch on the MaaS side
- TLS or network error:
  - workspace network path, CA trust, or proxy issue
- Cline verifies but cannot complete agent tasks:
  - MaaS may be chat-compatible but not fully aligned with Cline's tool or reasoning flow
- Workspace fails before editor opens:
  - remove non-essential startup hooks and re-test manually inside the workspace

## Deliverables

When using this skill, prefer producing:

- a minimal Cline configuration block
- a MaaS verification command or script invocation
- a short diagnosis that separates:
  - workspace issues
  - Cline provider issues
  - MaaS compatibility issues
- a fallback recommendation:
  - continue with plain text verification, or
  - switch to another supported OpenAI-compatible model/provider if full agent mode is blocked
