# Common Pitfalls

## Databricks-Specific Assumptions

Watch for these source assumptions:

- `dbutils` dependencies
- hard-coded `Volumes` paths
- warehouse-only SQL execution assumptions
- Delta-only design assumptions
- notebook UX features treated as core logic

The fix is usually to separate:

- business logic
- storage path
- execution environment
- output format

## Huawei-Side Operational Pitfalls

### OBS access issues

Common problem:

- object-store access is blocked because AK/SK is invalid
- agency is not attached
- temporary credential retrieval is not working

Preferred response:

- keep the migration moving with `HDFS` or local-node fallback for logic validation
- record the object-store issue as an operational hardening gap

### Path mismatches

Typical issues:

- `obs://...` path used where `hdfs:///...` was intended
- curated output written to one path but queried from another
- Databricks export path and MRS import path do not align

### Join ambiguity in Spark

After migration, Spark DataFrame jobs often fail because a column name exists on both sides of a join.

Preferred fix:

- alias inputs explicitly
- reference qualified columns such as `left.col_name` and `right.col_name`

### Hive access assumptions

Do not assume:

- Hive JDBC is reachable on localhost
- a specific Beeline endpoint is open
- one interactive SQL endpoint exists for every cluster configuration

Prefer Spark-side validation when in doubt.

## Migration Process Pitfalls

- validating too late
- comparing only row counts and not business aggregates
- overclaiming performance superiority from limited timing data
- mixing business-result gaps with infrastructure gaps
- copying environment-specific commands into reusable documentation

## Required Agent Hygiene

Always sanitize:

- hostnames
- bucket names
- usernames
- passwords
- access keys
- secret keys
- tokens
- project IDs
- region-specific identifiers unless the user explicitly wants them

Use placeholders such as:

- `<server_hostname>`
- `<warehouse_http_path>`
- `<bucket>`
- `<prefix>`
- `<mrs-master>`
- `<catalog>`
- `<schema>`
