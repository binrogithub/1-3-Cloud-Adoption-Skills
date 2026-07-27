# DataArts Deploy Agent

## Documentation

| Document | Description |
|----------|-------------|
| [Migration Tool Guide](README_DATAARTS_MIGRATION.md) | Complete usage guide for the Snowflake-to-DataArts migration framework |
| [Architecture Guide](docs/dataarts-migration-architecture.md) | Module map, command map, adapter strategy, safety controls, and roadmap |
| [MVP Release Notes](docs/mvp-v0.1-release-notes.md) | MVP v0.1 release notes |
| [MVP Quickstart](docs/mvp-v0.1-quickstart.md) | MVP v0.1 quickstart guide |
| [Architecture v0.1](docs/architecture-v0.1.md) | Architecture overview for v0.1 |

## Migration Framework MVP v0.1

**Status:** CONFIRMED

Snowflake Task Graph → DataArts Factory + DLI migration framework, validated with `orders_pipeline_simple` golden package.

- [Release Notes](docs/mvp-v0.1-release-notes.md)
- [Quickstart](docs/mvp-v0.1-quickstart.md)
- [Architecture](docs/architecture-v0.1.md)

> **Warning:** `--confirm` execution creates a real DataArts Factory job and triggers run-immediate. Always dry-run first.

## What This Agent Does

This is a **dry-run-only deployment agent** that reads AI-generated DataArts migration artifacts and produces a DataArts Factory Create Job API payload — without calling any real Huawei Cloud API.

It is the second stage of the Snowflake-to-Huawei migration demo:

1. **Stage 1 (AI migration agent):** Analyzed the Snowflake Task Graph and generated DataArts artifacts (pipeline YAML, SQL nodes, DAG JSON, diagrams, compatibility report).
2. **Stage 2 (this agent):** Reads those artifacts, validates the environment, and generates a ready-to-deploy API payload for review.

## What This Agent Does NOT Do Yet

- Does NOT call the Huawei Cloud DataArts Factory API.
- Does NOT create, update, or delete any DataArts jobs or pipelines.
- Does NOT upload SQL scripts to OBS.
- Does NOT execute any pipeline.
- Does NOT authenticate with Huawei Cloud IAM.
- Does NOT perform any destructive operation.

This is a **payload generator and readiness checker only**.

## How It Consumes the AI-Generated Artifacts

The agent reads from the directory specified by `DATAARTS_ARTIFACTS_DIR` (typically `../snowflake_to_dataarts_demo_output`):

| Artifact | Purpose |
|----------|---------|
| `analysis/canonical_dag.json` | Platform-neutral DAG: pipeline name, schedule, nodes, edges, source/target mapping |
| `dataarts/dataarts_pipeline.yaml` | DataArts-specific pipeline definition: node types, SQL file refs, execution order |
| `dataarts/nodes/*.sql` | SQL scripts for each pipeline node (DLI SQL) |

The agent combines these into a single DataArts Create Job API payload with all SQL inlined.

## How Credentials Are Handled Safely

- Credentials are loaded from `.env.dataarts` (never committed, in `.gitignore`).
- `HUAWEI_AK` and `HUAWEI_SK` are **never printed in full** — only the last 4 characters are shown (e.g., `***abcd`).
- The generated dry-run payload **does not contain secrets** — it references `workspace_id`, `region`, and `project_id` but not AK/SK.
- The `.env.dataarts` file is excluded from git via `.gitignore`.

## CLI Commands

```bash
# Validate that .env.dataarts is complete and artifacts exist
npm run validate-env

# Generate the dry-run payload and readiness report
npm run dry-run
```

### Equivalence Summary Table

After a successful demo run, generate an executive equivalence summary comparing Snowflake expected results vs DataArts/DLI actual results:

```bash
npm run demo:equivalence-summary -- \
  --run-id run_20260623134324._324a19bb \
  --job-name snowflake_to_dataarts_demo_v11_full_ai_async
```

Or without `--run-id` (reads `out/current_run.json` to resolve):

```bash
npm run demo:equivalence-summary -- \
  --job-name snowflake_to_dataarts_demo_v11_full_ai_async
```

This command is **read-only** — it only reads local result files. It does not call Huawei Cloud APIs, execute DLI SQL, or run the DataArts job.

Output includes a markdown table:

| VALIDATION_TYPE | OBJECT_NAME | SNOWFLAKE_EXPECTED | DATAARTS_DLI_ACTUAL | STATUS | DETAIL |
|-----------------|-------------|--------------------|---------------------|--------|--------|
| PIPELINE_READY | SNOWFLAKE_TASK_GRAPH_TO_DATAARTS_DAG | PASS | PASS | PASS | ... |
| TABLE_COUNT | RAW_ORDERS | 5 | 5 | PASS | ... |
| TABLE_COUNT | SILVER_ORDERS | 5 | 5 | PASS | ... |
| TABLE_COUNT | GOLD_DAILY_SALES | 2 | 2 | PASS | ... |
| TABLE_COUNT | TASK_AUDIT_SUCCESS | >=1 | 1 | PASS | ... |
| AGGREGATE_CHECK | 2026-06-20 | order_count=2,total_amount=420.50 | order_count=2,total_amount=420.50 | PASS | ... |
| AGGREGATE_CHECK | 2026-06-21 | order_count=3,total_amount=630.34 | order_count=3,total_amount=630.34 | PASS | ... |
| FINAL_EQUIVALENCE | SNOWFLAKE_TO_DATAARTS | EQUIVALENT | EQUIVALENT | PASS | ... |

Generated files:
- `out/equivalence_summary_report.md`
- `out/equivalence_summary_result.json`
- `out/runs/<run_id>/equivalence_summary_report.md` (copy)
- `out/runs/<run_id>/equivalence_summary_result.json` (copy)

### One-Shot Demo Commands (Dynamic Job Name)

The one-shot demo commands accept `--job-name`, `--artifacts-dir`, and `--dli-queue` as **runtime parameters**. They do **not** require `DATAARTS_JOB_NAME` or `DATAARTS_ARTIFACTS_DIR` in `.env.dataarts`.

```bash
# Plan only (read-only, no API writes)
npm run demo:one-shot:plan -- \
  --job-name snowflake_to_dataarts_demo_v9_mcp_oneshot \
  --artifacts-dir ../snowflake_to_dataarts_demo_v4_runtime_output \
  --dli-queue default

# Full one-shot execution (requires --confirm)
npm run demo:one-shot -- \
  --confirm \
  --job-name snowflake_to_dataarts_demo_v9_mcp_oneshot \
  --artifacts-dir ../snowflake_to_dataarts_demo_v4_runtime_output \
  --dli-queue default

# Doctor: diagnose results for a specific job
npm run demo:one-shot:doctor -- \
  --job-name snowflake_to_dataarts_demo_v9_mcp_oneshot
```

If `--dli-queue` is omitted, it falls back to `DLI_QUEUE_NAME` from `.env.dataarts` or `"default"`.

### Environment File (.env.dataarts)

The `.env.dataarts` file must contain only **stable tenant/environment configuration**:

| Variable | Required | Description |
|----------|----------|-------------|
| `HUAWEI_REGION` | Yes | Huawei Cloud region code |
| `HUAWEI_PROJECT_ID` | Yes | Huawei Cloud project ID |
| `HUAWEI_AK` | Yes | Access key |
| `HUAWEI_SK` | Yes | Secret key |
| `DATAARTS_WORKSPACE_ID` | Yes | DataArts Factory workspace ID |
| `DLI_QUEUE_NAME` | No | Default DLI queue name (falls back to `"default"`) |
| `DATAARTS_JOB_NAME` | No | Job name fallback (not required for one-shot/MCP — use `--job-name` instead) |
| `DATAARTS_ARTIFACTS_DIR` | No | Artifacts dir fallback (not required for one-shot/MCP — use `--artifacts-dir` instead) |

## Output Files

Both commands write to `./out/` (created at runtime, gitignored):

| File | Description |
|------|-------------|
| `out/dataarts_create_job_payload.dryrun.json` | Full DataArts Create Job API payload candidate (no secrets) |
| `out/deployment_readiness_report.md` | Human-readable readiness checklist and summary |

## What Would Be Needed for the Next Step: Real DataArts API Deployment

To go from dry-run to actual deployment:

1. **Implement `src/deploy.js`** that:
   - Authenticates using HUAWEI_AK / HUAWEI_SK (Huawei Cloud IAM / API Gateway signing).
   - Uploads SQL scripts to OBS (or inlines them in the job definition).
   - Calls `POST /v2/{project_id}/design/jobs/batch` to create the DataArts Factory job.
   - Configures node dependencies and schedule.
   - Publishes the job.
   - Optionally triggers a pipeline run.

2. **Or use a DataArts MCP server** that wraps the above API calls and can be invoked by an AI agent.

3. **Or use Playwright MCP** to automate the DataArts Factory web console (create pipeline, add nodes, wire dependencies, configure schedule).

## Running as MCP

The agent can run as an MCP (Model Context Protocol) server, exposing its demo commands as tools for AI agents.

### Start the MCP server

```bash
npm run mcp
```

This starts the server in stdio mode. It does **not** execute any demo commands on startup — tools are only invoked when called by the MCP client.

### Available MCP Tools

All MCP tools accept **dynamic runtime parameters**. They do **not** rely on `DATAARTS_JOB_NAME` from `.env.dataarts`.

| Tool | Description | Safety |
|------|-------------|--------|
| `snowflake_dataarts_demo_plan` | Runs the one-shot plan only (read-only) | Read-only, no API writes |
| `snowflake_dataarts_demo_run` | Runs the full one-shot demo synchronously | Requires `confirm=true` |
| `snowflake_dataarts_demo_start` | Starts the one-shot demo **asynchronously** in background | Requires `confirm=true`, returns immediately |
| `snowflake_dataarts_demo_status` | Reads run status/progress (supports `run_id`) | Read-only, no execution |
| `snowflake_dataarts_demo_last_report` | Reads the report markdown | Read-only, secrets scrubbed |
| `snowflake_dataarts_demo_equivalence_summary` | Generates equivalence summary table from local results | Read-only, no APIs, no SQL |

#### `snowflake_dataarts_demo_plan`

```json
{
  "job_name": "snowflake_to_dataarts_demo_v9_mcp_oneshot",
  "artifact_dir": "../snowflake_to_dataarts_demo_v4_runtime_output",
  "dli_queue": "default"
}
```

#### `snowflake_dataarts_demo_run`

```json
{
  "confirm": true,
  "job_name": "snowflake_to_dataarts_demo_v9_mcp_oneshot",
  "artifact_dir": "../snowflake_to_dataarts_demo_v4_runtime_output",
  "dli_queue": "default"
}
```

**Note:** This tool runs synchronously and may time out for long-running demos. Prefer `snowflake_dataarts_demo_start` for production use.

#### `snowflake_dataarts_demo_start` (Async)

Starts the one-shot demo in a detached background process and returns immediately.

```json
{
  "confirm": true,
  "job_name": "snowflake_to_dataarts_demo_v10_async_mcp_oneshot",
  "artifact_dir": "../snowflake_to_dataarts_demo_v4_runtime_output",
  "dli_queue": "default"
}
```

Returns:
```json
{
  "status": "STARTED",
  "run_id": "run_20260623102849_284329b0",
  "job_name": "snowflake_to_dataarts_demo_v10_async_mcp_oneshot",
  "next_step": "Call snowflake_dataarts_demo_status with run_id or job_name to poll progress.",
  "polling_example": { "tool": "snowflake_dataarts_demo_status", "args": { "run_id": "run_20260623102849_284329b0" } }
}
```

Background process stdout/stderr are written to `out/runs/<run_id>/mcp_async_stdout.log` and `mcp_async_stderr.log`.

#### `snowflake_dataarts_demo_status`

```json
{
  "run_id": "run_20260623102849_284329b0"
}
```

Or by job_name:

```json
{
  "job_name": "snowflake_to_dataarts_demo_v9_mcp_oneshot"
}
```

If `run_id` is provided, reads from `out/runs/<run_id>/`. Returns `current_step`, `current_step_name`, `completed_steps`, `failed_step`, `instance_id`, `final_equivalence`, and more.

If `job_name` is provided and the latest result belongs to a different job, returns `STATUS_STALE_FOR_REQUESTED_JOB`.

#### `snowflake_dataarts_demo_last_report`

```json
{
  "run_id": "optional",
  "job_name": "optional"
}
```

#### `snowflake_dataarts_demo_equivalence_summary`

Generates an equivalence summary table from local runtime validation result files. Read-only — no Huawei Cloud APIs, no DLI SQL, no job execution.

```json
{
  "run_id": "run_20260623134324._324a19bb",
  "job_name": "snowflake_to_dataarts_demo_v11_full_ai_async"
}
```

Returns `status`, `job_name`, `run_id`, `instance_id`, `final_equivalence`, `markdown_table`, `report_path`, and safety flags.

### Register in OpenCode

Add to your `opencode.json` (or `.opencode/opencode.json`):

```json
{
  "mcpServers": {
    "dataarts-deploy-agent": {
      "command": "node",
      "args": ["mcp-server.mjs"],
      "cwd": "<path-to-dataarts-deploy-agent>",
      "timeout": 900000
    }
  }
}
```

Replace `<path-to-dataarts-deploy-agent>` with the absolute path to this directory, e.g.:

```json
"cwd": "/root/opencode-pricing-assistant/dataarts-deploy-agent"
```

**Timeout:** Set to `900000` (15 minutes). The one-shot demo creates DataArts jobs, resets DLI data, runs DataArts run-immediate, and validates DLI results — each step can take 30-120 seconds. For even longer runs, use the async `snowflake_dataarts_demo_start` tool instead.

### Test the plan tool

Once registered, call `snowflake_dataarts_demo_plan` from your MCP client. This runs `npm run demo:one-shot:plan` and returns the plan result without executing any write operations.

## Project Structure

```
dataarts-deploy-agent/
├── .env.dataarts          ← Credentials (gitignored)
├── .gitignore
├── package.json
├── README.md              ← This file
├── src/
│   ├── config.js          ← Load & validate .env, mask secrets
│   ├── validate-env.js    ← CLI: npm run validate-env
│   ├── load-artifacts.js  ← Read canonical_dag.json, pipeline YAML, SQL nodes
│   ├── generate-dataarts-payload.js  ← Build API payload & readiness report
│   └── dry-run.js         ← CLI: npm run dry-run
└── out/                   ← Generated at runtime (gitignored)
    ├── dataarts_create_job_payload.dryrun.json
    └── deployment_readiness_report.md
```
