# LiteLLM Huawei MaaS Single ECS

This child skill package focuses on deploying LiteLLM Proxy on a single Huawei Cloud ECS instance and connecting it to Huawei Cloud MaaS through an OpenAI-compatible endpoint. It is intended for AI development scenarios where teams need a practical single-host proxy with local Redis, PostgreSQL, systemd services, and multi-user token management.

## Included Assets

- [SKILL.md](./SKILL.md): Main skill definition, deployment workflow, and repair guidance
- [assets/](./assets): Configuration templates for LiteLLM, environment files, Redis, and systemd
- [references/](./references): Architecture guidance for single-host deployment and FinOps usage
- [scripts/](./scripts): Helper scripts for FinOps bootstrap and end-to-end validation

## Typical Use

- Deploy LiteLLM Proxy on one ECS host
- Connect LiteLLM to Huawei Cloud MaaS through the OpenAI-compatible API
- Enable multi-user key management and spend control
- Validate both direct MaaS access and proxied LiteLLM access
