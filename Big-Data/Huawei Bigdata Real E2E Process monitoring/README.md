# Huawei Cloud SEC EDGAR Big Data POC

This skill package documents and operationalizes an end-to-end Huawei Cloud big-data monitoring PoC built around public SEC EDGAR filings. It covers infrastructure provisioning, secure credential handling, data ingestion to OBS, MRS Spark processing, DWS loading, Superset dashboarding, and a public lifecycle-monitoring website.

## Use This Skill When

- You need to reproduce or explain a real Huawei Cloud big-data PoC that spans OBS, MRS, DWS, ECS, Superset, and a monitoring website.
- You need step-by-step operational guidance for running the SEC EDGAR raw-to-BI pipeline and validating each stage.
- You need troubleshooting guidance for common issues such as MRS OBS credential failures, Superset driver setup, stale frontend cache, or DWS load verification.

## Included Assets

- `SKILL.md`: agent-facing execution workflow, safety rules, validation checklist, and operational defaults.
- `references/RUNBOOK.md`: detailed operator runbook for provisioning, deployment, data flow, troubleshooting, and final validation.
- `agents/openai.yaml`: runtime metadata for OpenAI-compatible agent invocation.

## Security Rules

- Never commit or print Huawei Cloud AK/SK, service passwords, Superset credentials, SSH private keys, or secret-bearing Terraform state.
- Keep secrets in environment variables, DPAPI-encrypted local XML files, SSH agent/key files, or cloud secret services.
- Avoid logging or echoing Spark submission arguments that include OBS access keys or secret keys.

## Expected Outputs

- A reproducible workflow for standing up the SEC EDGAR PoC on Huawei Cloud.
- Clear validation checkpoints across OBS, MRS, DWS, Superset, and the monitoring API/UI.
- Troubleshooting guidance for the main infrastructure, data, and dashboarding failure modes seen during the original run.
