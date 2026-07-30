# Driver Config Schema

Use this shape for `scripts/dataarts_architecture_driver.py`.

```json
{
  "scenario": "Example Citizen Data Platform",
  "region": "la-south-2",
  "workspace_id": "project-or-workspace-id",
  "credentials_file": "credentials.env",
  "objects": {
    "subjects": [],
    "directories": [],
    "standards": [],
    "code_tables": [],
    "model_workspaces": [],
    "table_models": [],
    "dimensions": [],
    "summary_tables": [],
    "atomic_metrics": [],
    "derivative_metrics": [],
    "compound_metrics": [],
    "business_metrics": []
  }
}
```

Each object list should contain API-ready dictionaries plus stable match keys:

```json
{
  "match": {"name_en": "ct_example_status"},
  "body": {"name_en": "ct_example_status", "name_ch": "Example Status", "directory_id": "..."}
}
```

Prefer generating this config from source-table inference, then reviewing it before executing writes.
