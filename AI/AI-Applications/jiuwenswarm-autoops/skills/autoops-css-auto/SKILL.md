---
name: autoops-css-auto
description: Analyze and safely operate a registered Huawei Cloud CSS cluster through the css_auto role.
version: 1
allowed_roles: [css_auto]
---

# CSS AutoOps

Use this skill for a Huawei Cloud CSS or OpenSearch cluster whose cluster_id,
region, project ID, and credential reference were registered with
scripts/css-register.py.

SDK setup command:

    python3 scripts/css-register.py --profile-id <name> --cluster-id <css-uuid> --region <region> --project-id <project-id>

It asks for AK and hidden SK input when the corresponding environment variables
are absent. Never put the SK in a TUI prompt, task description, result,
workflow argument, Git file, or log. Use HUAWEICLOUD_SDK_AK and
HUAWEICLOUD_SDK_SK only for non-interactive setup.

Use the registered cluster profile for inspect, plan, operation status, and
verify. The default mode is observe. A scale-out or scale-in proposal must
include the current data-node count, target count, delta, policy revision,
evidence window, data quality, reason codes, and constraints.

Only the fixed E01 CSS Runbook may submit an ess node-count change. An API
acceptance response is SUBMITTED, never SUCCEEDED; wait for topology,
cluster health, shard migration, and independent E09 business verification.
Unknown responses must be reconciled before retrying. Missing or stale metrics,
unknown health, an unfinished operation, or an unsafe AZ/replica/disk result
blocks scale-in.

## KooCLI adapter

When the host already has Huawei Cloud KooCLI configured, register the cluster
with the project-owned KooCLI adapter. This keeps AK/SK inside KooCLI and does
not pass secrets through JiuwenSwarm tasks or process arguments:

    python3 scripts/css-register.py --profile-id css-santiago \
      --cluster-id <css-uuid> --region la-south-2 \
      --project-id <project-id> --api-adapter koo-cli \
      --koo-cli-profile default --koo-cli-mode AKSK --mode observe

The adapter calls KooCLI `CSS ShowClusterDetail`, `CES ShowMetricData`,
`CSS UpdateExtendInstanceStorage`, and `CSS UpdateShrinkCluster`. The profile
must point at a valid KooCLI installation, normally `/usr/local/bin/hcloud`.
`AKSK` is the default authentication mode; `ecsAgency` is an explicit option
only for hosts that have a Huawei Cloud ECS agency configured.
KooCLI read operations are used for inspection and metrics; CSS writes remain
behind the same authenticated E01 Runbook, policy, idempotency, and explicit
`--execute` boundary.

For a real pressure-to-capacity check, use the project-owned live entry:

    python3 scripts/css-live-pressure.py --profile-id <name> --iterations 1 \
      --evidence /var/lib/jiuwenswarm-autoops/css-live/observation.json

This reads CSS topology and CES pressure from the registered profile. It is
observe-only by default and does not generate traffic. To submit one real
policy-approved E01 action, add `--execute --max-actions 1`; the process sets
the existing Runbook role boundary and then reconciles the cloud action. Add a
read-only `--probe-url` when the cluster has a business health endpoint. A
missing SDK, profile, or data source is reported as `UNAVAILABLE`; it never
falls back to a fixture or silently changes the cluster.
