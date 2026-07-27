# MRS-DWS-Finance-Skill

This Level 2 folder imports a reusable skill package for financial risk control scenarios on Huawei Cloud. It focuses on configuring OBS, MRS, and DWS for big-data financial analysis pipelines, including risk scoring, anomaly detection, regulatory compliance, and reporting.

## Included Assets

- [SKILL.md](./SKILL.md): Main skill definition, workflow, and default deliverables
- [references/](./references): Architecture patterns, regulatory compliance, and common pitfalls
- [scripts/](./scripts): Setup, ETL, analysis, and reporting templates
- [examples/](./examples): Proven working examples for quick-start deployment
- [agents/](./agents): Agent configuration used by the skill package

## Typical Use

- Configure OBS + MRS + DWS for financial risk control
- Deploy risk scoring and anomaly detection pipelines
- Generate regulatory compliance reports (CNBV, Banxico, AML/KYC)
- Validate data pipeline parity and execution behavior

## Quick Start with Examples

1. **Discover resources**: `python examples/example_discover_resources.py`
2. **Create DWS cluster**: `python examples/example_create_dws_cluster.py`
3. **Generate test data**: `python examples/example_generate_mexico_data.py`
4. **Run full pipeline**: `./examples/example_full_pipeline.sh`
