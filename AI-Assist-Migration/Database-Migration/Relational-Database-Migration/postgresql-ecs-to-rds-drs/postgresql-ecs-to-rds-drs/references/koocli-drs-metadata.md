# KooCLI DRS metadata and PostgreSQL support

## The problem

`hcloud DRS CreateJob` validates its parameters against a local metadata template before
sending anything to the API. On some KooCLI versions that template does not list
PostgreSQL, so a perfectly valid request is rejected on the client side.

The symptom is a validation error naming the allowed values, typically:

```
db_type: allowed values are oracle|gaussdbv5|redis|rediscluster|gaussredis|mysql
```

and an `engine_type` enum with no `postgresql-to-postgresql` entry.

This is a **client-side** limitation. The DRS API itself supports PostgreSQL; the console
creates these tasks routinely. Only the CLI's local metadata is behind.

## How to detect it

Step 0 of the workflow runs:

```
hcloud_cli(command="DRS CreateJob --help")
```

Read the allowed values for `db_type` and `engine_type`. If `postgresql` and
`postgresql-to-postgresql` are both present, there is nothing to do — skip the rest of
this page.

## How to resolve it

### Option 1 — update KooCLI (try this first)

The cleanest fix. A newer KooCLI ships newer metadata:

```bash
hcloud version
hcloud update
```

Then clear the cached metadata so it is re-fetched, and re-check:

```bash
rm -rf ~/.hcloud/metaRepo
hcloud DRS CreateJob --help
```

If PostgreSQL now appears, done.

### Option 2 — patch the local metadata template

Only if Option 1 does not resolve it.

The template lives under the KooCLI metadata repository. Locate it:

```bash
find ~/.hcloud/metaRepo -iname "CreateJob*" -path "*drs*"
```

The file is typically:

```
~/.hcloud/metaRepo/template/drs/CreateJob_v5_en.yaml
```

Back it up before editing:

```bash
cp ~/.hcloud/metaRepo/template/drs/CreateJob_v5_en.yaml \
   ~/.hcloud/metaRepo/template/drs/CreateJob_v5_en.yaml.bak
```

Two enums need an entry added:

1. `db_type` — add `postgresql`
2. `engine_type` — add `postgresql-to-postgresql`

Do not remove existing values. Add only.

Verify the change took effect:

```bash
hcloud DRS CreateJob --help
```

Both new values must now appear.

## Consequences you must account for

**This patch is local to one machine.** A customer following this scenario on a clean
workstation will hit exactly the same wall. That is why Step 0 checks for it explicitly
rather than letting `CreateJob` fail halfway through the workflow.

**A KooCLI update may overwrite it.** If `CreateJob` starts rejecting PostgreSQL again
after an update, re-check the metadata before assuming something else broke.

**Record it in the migration report.** If the patch was needed, the run is not
reproducible without it, and whoever reads the report needs to know.

## If neither option works

Fall back to creating the DRS task from the console, then drive the rest of the workflow
by ID with the CLI. Everything after task creation — `BatchStartJobs`, `ShowJobDetail`,
`CreateObjectLevelCompareJob`, `BatchStopJobs`, `BatchDeleteJobs` — works normally,
because only `CreateJob` carries the engine enums.

Note the fallback in the report. Task creation via console is a legitimate path, but it
means the scenario is not fully CLI-driven on that KooCLI version.
