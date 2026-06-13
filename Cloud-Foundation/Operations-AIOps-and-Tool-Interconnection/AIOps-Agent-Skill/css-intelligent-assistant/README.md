# CSS Intelligent Ops Agent — Workflow Guide

## Overview

This agent monitors a Huawei Cloud CSS (Cloud Search Service) cluster with **28+ metrics**, performs **AI-powered health diagnosis**, and automatically scales **data nodes (ess)** based on multi-dimensional signals. A real-time HTML dashboard displays all monitoring data, 5 charts, AI decisions, and diagnosis results.

**Scope:**

- Monitors **28+ metrics**: CPU, disk, JVM heap, GC, search/indexing QPS & latency, thread pool queue & rejection, cluster status, HTTP connections, system load
- Scales **data nodes** only — never client or master nodes
- **Never changes flavor** (spec) — only node count
- **AI health diagnosis** when cluster is unhealthy: root cause analysis, severity, fix suggestions, optional auto-fix
- Scale-out and scale-in **step size is configurable**
- Scale-in is blocked for a **configurable time interval after the last scale-out**

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│  CES SDK    │────>│  Elasticity  │────>│  LLM (AI)   │────>│  CSS SDK     │
│  (metrics)  │     │  Engine      │     │  Decision    │     │  (executor)  │
└─────────────┘     └──────┬───────┘     └─────────────┘     └──────────────┘
                           │
                    ┌──────v───────┐
                    │  Cluster     │────>  AI Diagnosis
                    │  Health      │       (root cause +
                    │  Check       │        suggestions)
                    └──────┬───────┘
                           │
                           v
                    ┌──────────────┐
                    │  Dashboard   │
                    │  (Flask +    │
                    │   HTML)      │
                    └──────────────┘
```

### Components

| Component | File | Description |
|---|---|---|
| **Config** | `config.py` | All settings via `.env` file and environment variables |
| **Metrics** | `metrics.py` | Queries Huawei Cloud CES for 28+ metrics across 8 groups |
| **Executor** | `css_executor.py` | Calls Huawei Cloud CSS API to scale data nodes out or in |
| **AI Decision** | `ai_decide.py` | Sends full metrics context to LLM, parses the JSON decision |
| **Cluster Health** | `cluster_health.py` | Health check + AI diagnosis (root cause, suggestions, auto-fix) |
| **Engine** | `engine.py` | Orchestrates the full check cycle with health check, multi-dim spike, diagnosis |
| **Server** | `server.py` | Flask app serving the dashboard (5 charts) and REST API |
| **Entrypoint** | `main.py` | Starts the engine loop and the web server |

---

## Metrics Collected

### Regular Cycle (28 metrics)

| Group | Key | CES metric_name | Unit | Description |
|---|---|---|---|---|
| **CPU** | `cpu_avg` | `avg_cpu_usage` | % | Average CPU utilization |
| **CPU** | `cpu_max` | `max_cpu_usage` | % | Max CPU utilization across nodes |
| **Disk** | `disk_usage_pct` | `disk_util` | % | Max disk usage across nodes |
| **Disk** | `disk_io_util_max` | `max_disk_io_util` | % | Max disk IO utilization |
| **JVM** | `jvm_heap_max` | `max_jvm_heap_usage` | % | Max JVM heap usage |
| **JVM** | `jvm_heap_avg` | `avg_jvm_heap_usage` | % | Average JVM heap usage |
| **JVM** | `jvm_old_gc_time_avg` | `avg_jvm_old_gc_time` | ms | Average Old GC time |
| **JVM** | `jvm_young_gc_time_avg` | `avg_jvm_young_gc_time` | ms | Average Young GC time |
| **QPS** | `search_rate` | `SearchRate` | ops | Search QPS |
| **QPS** | `search_latency` | `SearchLatency` | ms | Search latency |
| **QPS** | `indexing_rate` | `IndexingRate` | ops | Indexing TPS |
| **QPS** | `indexing_latency` | `IndexingLatency` | ms | Indexing latency |
| **ThreadPool** | `tp_search_queue` | `sum_thread_pool_search_queue` | 个 | Search thread pool queue |
| **ThreadPool** | `tp_write_queue` | `sum_thread_pool_write_queue` | 个 | Write thread pool queue |
| **ThreadPool** | `tp_force_merge_queue` | `sum_thread_pool_force_merge_queue` | 个 | Force merge queue |
| **ThreadPool** | `tp_refresh_queue` | `sum_thread_pool_refresh_queue` | 个 | Refresh queue |
| **ThreadPool** | `tp_generic_queue` | `sum_thread_pool_generic_queue` | 个 | Generic queue |
| **ThreadPool** | `tp_management_queue` | `sum_thread_pool_management_queue` | 个 | Management queue |
| **ThreadPool** | `tp_search_rejected` | `sum_thread_pool_search_rejected` | 个 | Search rejected |
| **ThreadPool** | `tp_write_rejected` | `sum_thread_pool_write_rejected` | 个 | Write rejected |
| **ThreadPool** | `tp_force_merge_rejected` | `sum_thread_pool_force_merge_rejected` | 个 | Force merge rejected |
| **ThreadPool** | `tp_refresh_rejected` | `sum_thread_pool_refresh_rejected` | 个 | Refresh rejected |
| **ThreadPool** | `tp_generic_rejected` | `sum_thread_pool_generic_rejected` | 个 | Generic rejected |
| **ThreadPool** | `tp_management_rejected` | `sum_thread_pool_management_rejected` | 个 | Management rejected |
| **ThreadPool** | `pending_tasks` | `number_of_pending_tasks` | 个 | Pending tasks on master |
| **Cluster** | `cluster_status` | `status` | — | 0=available, 1=replica missing, 2=data missing, 3=unknown |
| **HTTP** | `http_open_max` | `max_current_opened_http_count` | 个 | Max open HTTP connections |
| **Load** | `load_avg_max` | `max_load_average` | — | Max 1-min load average |

### Diagnosis-Only Metrics (9 metrics)

Collected only when cluster is unhealthy:

| Key | CES metric_name | Description |
|---|---|---|
| `unassigned_shards` | `number_of_unassigned_shards` | Unassigned shard count |
| `shard_doc_exceed` | `shard_doc_exceed_threshold_count` | Shards exceeding doc threshold |
| `write_fail_alias` | `write_fail_alias_error` | Write failures (alias) |
| `write_fail_doc_count` | `write_fail_documents_count_exceed` | Write failures (doc count) |
| `write_fail_field_count` | `write_fail_fields_count_exceed` | Write failures (field count) |
| `write_fail_shard_count` | `write_fail_shards_count_exceed` | Write failures (shard count) |
| `write_fail_index_block` | `write_fail_index_blocks_write` | Write failures (index block) |
| `write_fail_mapping` | `write_fail_mapping_malformed` | Write failures (mapping) |
| `index_create_fail` | `number_of_index_creation_failures` | Index creation failures |

---

## Workflow — Step by Step

The engine runs `run_once()` on a fixed interval (`CHECK_INTERVAL_SECONDS`, default 60s). Each cycle:

```
┌──────────────────────────────────────────────────────────┐
│                    CHECK CYCLE                           │
│                                                          │
│  1. Collect All Metrics (28+)   ←── CES API             │
│              │                                           │
│  2. Get Current Data Node Count ←── CSS API             │
│              │                                           │
│  3. Cluster Health Check                                 │
│     ├─ Unhealthy → AI Diagnosis Flow                    │
│     │   ├─ Collect diagnosis context                    │
│     │   ├─ AI analyzes root cause + suggestions         │
│     │   ├─ If auto_fix available + enabled → execute    │
│     │   └─ Record diagnosis to dashboard                │
│     └─ Healthy → continue                               │
│              │                                           │
│  4. Multi-dimension Spike Detection                      │
│     CPU / Disk / JVM Heap / Latency / Queue             │
│              │                                           │
│  5. Scale-in Guard Check                                 │
│              │                                           │
│  6. AI Decision (full metrics context)                   │
│              │                                           │
│  7. Execute Action              ←── CSS API              │
│              │                                           │
│  8. Update State + History                               │
└──────────────────────────────────────────────────────────┘
```

### Step 3 — Cluster Health Check

Combines CES `status` metric and CSS cluster detail API:

| status value | Meaning | Color |
|---|---|---|
| 0 | Available (green) | 🟢 |
| 1 | Replica missing (yellow) | 🟡 |
| 2 | Data missing (red) | 🔴 |
| 3 | Unknown | ⚪ |

When unhealthy, AI diagnosis returns:

```json
{
  "root_cause": "JVM heap usage at 92% on data node-2, causing search thread pool rejection",
  "severity": "critical",
  "suggestions": [
    "Scale out data nodes to distribute load",
    "Increase JVM heap size on affected node",
    "Check for expensive queries causing heap pressure"
  ],
  "auto_fix_available": true,
  "auto_fix_action": "scale_out:1"
}
```

### Step 4 — Multi-dimension Spike Detection

Spike is detected if **any** of these conditions is true:

| Signal | Threshold Config | Default |
|---|---|---|
| CPU avg or max ≥ threshold | `CPU_SPIKE_THRESHOLD` | 80% |
| Disk usage ≥ threshold | `DISK_SPIKE_THRESHOLD` | 85% |
| JVM heap max ≥ threshold | `JVM_HEAP_SPIKE_THRESHOLD` | 85% |
| Search latency ≥ threshold | `SEARCH_LATENCY_SPIKE_THRESHOLD` | 500ms |
| Indexing latency ≥ threshold | `INDEXING_LATENCY_SPIKE_THRESHOLD` | 200ms |
| Search/write thread pool queue ≥ threshold | `THREAD_POOL_QUEUE_SPIKE_THRESHOLD` | 100 |

---

## Dashboard

The agent serves an HTML dashboard at `http://<SERVER_HOST>:<SERVER_PORT>/`.

### Features

- **Cluster health card** — green/yellow/red status, unhealthy node count, diagnosis panel
- **Diagnosis panel** — AI root cause analysis, severity badge, fix suggestions, auto-fix button
- **Key metrics overview** — 12 core metrics at a glance with color-coded progress bars
- **5 real-time charts**:
  1. CPU & Load (avg, max, load average with dual Y-axis)
  2. Disk (usage %, IO utilization %)
  3. JVM Heap & GC (heap max/avg %, Old GC ms with dual Y-axis)
  4. QPS & Latency (search/indexing rate, latency with dual Y-axis)
  5. Thread Pool (all 6 pool queues + pending tasks)
- **AI decision panel** — current LLM decision, delta, reason, cooldown
- **Action history table** — recent actions with all key metrics and health status
- **Configuration display** — all active settings

The dashboard polls `/api/status` every 3 seconds.

### API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | HTML dashboard |
| `/api/status` | GET | JSON with metrics, decision, health, diagnosis, state, history |
| `/api/config` | GET | JSON with all active configuration values |
| `/api/diagnose` | POST | Manually trigger AI diagnosis |
| `/api/fix/execute` | POST | Execute AI-suggested auto-fix (if available and enabled) |

---

## Configuration

All settings are loaded from a `.env` file or environment variables.

### AI Provider

| Variable | Default | Description |
|---|---|---|
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | LLM API endpoint (OpenAI-compatible) |
| `OPENAI_API_KEY` | *(empty)* | API key; if empty, agent always holds |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model name |

### Thresholds

| Variable | Default | Description |
|---|---|---|
| `CPU_SPIKE_THRESHOLD` | `80` | CPU % that triggers spike detection |
| `DISK_SPIKE_THRESHOLD` | `85` | Disk % that triggers spike detection |
| `JVM_HEAP_SPIKE_THRESHOLD` | `85` | JVM heap % that triggers spike detection |
| `SEARCH_LATENCY_SPIKE_THRESHOLD` | `500` | Search latency (ms) that triggers spike |
| `INDEXING_LATENCY_SPIKE_THRESHOLD` | `200` | Indexing latency (ms) that triggers spike |
| `THREAD_POOL_QUEUE_SPIKE_THRESHOLD` | `100` | Thread pool queue count that triggers spike |

### AI Diagnosis

| Variable | Default | Description |
|---|---|---|
| `AI_DIAGNOSE_ENABLED` | `true` | Enable AI diagnosis when cluster is unhealthy |
| `AI_AUTO_FIX_ENABLED` | `false` | Allow AI to execute auto-fix actions |

### Node Limits

| Variable | Default | Description |
|---|---|---|
| `MIN_NODES` | `2` | Minimum data node count (scale-in floor) |
| `MAX_NODES` | `10` | Maximum data node count (scale-out ceiling) |

### Scale Steps

| Variable | Default | Description |
|---|---|---|
| `SCALE_OUT_STEP` | `1` | Max nodes to add per scale-out action |
| `SCALE_IN_STEP` | `1` | Max nodes to remove per scale-in action |

### Cooldown & Guards

| Variable | Default | Description |
|---|---|---|
| `SCALE_OUT_COOLDOWN_MINUTES` | `10` | Cooldown after a scale-out before any action |
| `SCALE_IN_COOLDOWN_MINUTES` | `30` | Cooldown after a scale-in before any action |
| `SCALE_IN_DELAY_AFTER_SCALE_OUT_MINUTES` | `30` | Minimum time after scale-out before scale-in is allowed |

### Check Interval

| Variable | Default | Description |
|---|---|---|
| `CHECK_INTERVAL_SECONDS` | `60` | Seconds between metric checks |

### Huawei Cloud

| Variable | Description |
|---|---|
| `HUAWEICLOUD_SDK_AK` | Access key |
| `HUAWEICLOUD_SDK_SK` | Secret key |
| `HUAWEICLOUD_REGION` | Region (e.g. `cn-north-4`) |
| `HUAWEICLOUD_PROJECT_ID` | Project ID |
| `HUAWEICLOUD_CSS_ENDPOINT` | Custom CSS endpoint (optional, overrides region) |
| `HUAWEICLOUD_CES_ENDPOINT` | Custom CES endpoint (optional, overrides region) |

### Cluster & Mutation

| Variable | Default | Description |
|---|---|---|
| `CLUSTER_ID` | *(empty)* | CSS cluster ID to monitor and scale |
| `CLUSTER_NAME` | `css-cluster` | Display name for the dashboard |
| `CSS_MUTATION_ENABLED` | `false` | Set to `true` to execute actual scaling; `false` = observe-only |

### Dashboard Server

| Variable | Default | Description |
|---|---|---|
| `SERVER_HOST` | `0.0.0.0` | Bind address |
| `SERVER_PORT` | `5000` | Bind port |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your Huawei Cloud credentials and cluster ID

# 3. Run (observe-only by default)
python main.py

# 4. Open dashboard
# http://localhost:5000

# 5. Enable actual scaling when ready
# Set CSS_MUTATION_ENABLED=true in .env and restart
```

---

## Scale-in Safety

Scale-in has multiple layers of protection:

```
                     Scale-in request
                           │
              ┌────────────v────────────┐
              │  Cooldown active?       │──Yes──> HOLD
              └────────────┬───────────┘
                           │ No
              ┌────────────v────────────┐
              │  Scale-out delay not    │──Yes──> HOLD
              │  elapsed?               │
              └────────────┬───────────┘
                           │ No
              ┌────────────v────────────┐
              │  CSS_MUTATION_ENABLED?  │──No───> SKIP
              └────────────┬───────────┘
                           │ Yes
              ┌────────────v────────────┐
              │  Delta clamped by       │
              │  SCALE_IN_STEP,         │
              │  MIN_NODES, and CSS     │
              │  half-size rule         │
              └────────────┬───────────┘
                           │
                      Execute scale-in
```
