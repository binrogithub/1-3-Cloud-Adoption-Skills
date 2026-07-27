#!/usr/bin/env python3
"""Generic Databricks SQL warehouse execution pattern for migration work."""

from __future__ import annotations

import json
import os
import subprocess

from databricks import sql


PROFILE_NAME = os.environ.get("DATABRICKS_PROFILE", "<profile>")
SERVER_HOSTNAME = os.environ.get("DATABRICKS_SERVER_HOSTNAME", "<server_hostname>")
WAREHOUSE_HTTP_PATH = os.environ.get("DATABRICKS_WAREHOUSE_HTTP_PATH", "<warehouse_http_path>")

SQL_STATEMENTS = [
    "USE CATALOG <catalog>",
    "USE SCHEMA <schema>",
    """
    CREATE OR REPLACE TABLE <catalog>.<schema>.<target_table> AS
    SELECT *
    FROM read_files(
      '/Volumes/<catalog>/<schema>/<volume>/<source_file>.csv',
      format => 'csv',
      header => true,
      inferSchema => true
    )
    """,
]

METRIC_QUERIES = {
    "target_rows": "SELECT COUNT(*) FROM <catalog>.<schema>.<target_table>",
}


def get_access_token() -> str:
    result = subprocess.run(
        ["databricks", "auth", "token", "--profile", PROFILE_NAME, "--output", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)["access_token"]


def main() -> None:
    access_token = get_access_token()
    with sql.connect(
        server_hostname=SERVER_HOSTNAME,
        http_path=WAREHOUSE_HTTP_PATH,
        access_token=access_token,
    ) as connection:
        with connection.cursor() as cursor:
            for statement in SQL_STATEMENTS:
                cursor.execute(statement)
            for metric_name, query in METRIC_QUERIES.items():
                cursor.execute(query)
                print(f"{metric_name}={cursor.fetchone()[0]}")


if __name__ == "__main__":
    main()
