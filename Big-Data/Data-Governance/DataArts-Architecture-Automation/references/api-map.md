# DataArts Architecture API Map

Use these official DataArts Architecture APIs for metadata creation.

## Core Setup

- Model workspace: `POST /v2/{project_id}/design/workspaces`
  - Use for logical, physical, dimension, and mart model workspaces.
  - Common fields: `name`, `description`, `type`, `frequent`, `is_physical`, `dw_type`, `table_model_prefix`, `dimension_prefix`.

- Directory: `POST /v2/{project_id}/design/directorys`
  - Use for `STANDARD_ELEMENT` and `CODE` directories.
  - Common fields: `name`, `name_en`, `description`, `type`, `parent_id`, `prev_id`.

- Subject/topic: `POST /v3/{project_id}/design/subjects`
  - Use for DataArts Architecture subject areas/topics.
  - Common fields: `name_ch`, `name_en`, `description`, `level`, `parent_id`, `data_owner_list`.

## Standards And Lookup Tables

- Data standard: `POST /v2/{project_id}/design/standards`
  - Initialize template first if needed:
    - `GET /v2/{project_id}/design/standards/templates`
    - `POST /v2/{project_id}/design/standards/templates/action?action-id=init`
  - Body: `directory_id` plus `values`.
  - Common `values.fd_name`: `nameCh`, `nameEn`, `englishName`, `dataType`, `dataLength`, `hasAllowValueList`, `allowList`, `ruleOwner`, `description`.

- Code table: `POST /v2/{project_id}/design/code-tables`
  - Required: `name_en`, `name_ch`, `directory_id`, `code_table_fields`.
  - Field objects require `ordinal`, `name_en`, `name_ch`, `data_type`; use `code_table_field_values` for values.

## Models

- Table model: `POST /v2/{project_id}/design/table-model`
  - Required: `model_id`, `logic_tb_name`, `tb_name`, `description`, `attributes`, `dw_type`.
  - For DWS include `dw_id`, `db_name`, `schema`, `table_type`, `distribute`, `distribute_column`.
  - `biz_catalog_id` usually validates against subject IDs in Architecture contexts.

- Dimension: `POST /v2/{project_id}/design/dimensions`
  - Required: `name_en`, `name_ch`, `dimension_type`, `description`, `l3_id`, `attributes`, datasource fields.
  - Use published subject IDs for `l3_id` unless the target workspace proves level-3 IDs are accepted.

- Summary table: `POST /v2/{project_id}/design/aggregation-logic-tables`
  - Required: `tb_name`, `tb_logic_name`, `l3_id`, `owner`, `dw_type`, datasource fields, table attributes.
  - Workspace model prefixes may be enforced. Respect the API error and rename predictably.

## Metrics

- Atomic metric: `POST /v2/{project_id}/design/atomic-indexs`
  - Required: `name_en`, `name_ch`, `cal_exp`, `l3_id`, `table_id`, `field_ids`.
  - Use real table attribute IDs in `cal_exp`, for example `sum(${1531855222463430661})`.

- Derivative metric: `POST /v2/{project_id}/design/derivative-indexs`
  - Body is an array.
  - Required: `name_en`, `name_ch`, `l3_id`, `atomic_index_id`.
  - Add dimension groups to express analysis grain.

- Compound metric: `POST /v2/{project_id}/design/compound-metrics`
  - Common expression payload: `compound_type: EXPRESSION`, `dimension_group`, `metric_ids`, `cal_exp`, `l3_id`, `data_type`.
  - Use derivative/compound metric IDs in `cal_exp`, for example `(${id1} / ${id2}) * 100`.

- Business metric/service indicator: `POST /v2/{project_id}/design/biz-metrics`
  - Common fields: `name`, `biz_catalog_id`, `destination`, `definition`, `expression`, `dimensions`, `technical_metric`, `measure`, `owner`.
  - `technical_metric` expects a numeric metric ID, not a display name.

## Read-Back Endpoints

Use matching `GET` endpoints with `limit` and `offset` before and after writes:

- `/design/workspaces`
- `/design/directorys?type=STANDARD_ELEMENT`
- `/design/directorys?type=CODE`
- `/design/subjects`
- `/design/standards`
- `/design/code-tables`
- `/design/table-model`
- `/design/dimensions`
- `/design/aggregation-logic-tables`
- `/design/atomic-indexs`
- `/design/derivative-indexs`
- `/design/compound-metrics`
- `/design/biz-metrics`
