# E01 Runbook Operator

Load `config/rundeck.env.example` values from a protected local environment and replace the placeholder Job ID in `config/rundeck-jobs.json` with a published, read-only Rundeck Job.

`runbook-execute.py` accepts only an allowlisted Job name and a schema-validated target. It stores the intent under a unique idempotency key before the HTTP submission. A second request with the same key reads the existing Rundeck execution instead of starting another Job; an intent without an execution ID is reported as `UNKNOWN` and is never retried automatically.

```bash
./scripts/runbook-execute.py --task-id incident-42 --idempotency-key incident-42-step-1 \
  --job host-basic-check --target test-host-01
```

The JSON result carries the Rundeck execution ID, status, observation time, and a bounded redacted output summary. A `running` or `waiting` status is retryable regardless of Rundeck's letter case; reuse the same idempotency key when polling. Do not put API tokens in registry files, prompts, or task arguments.
