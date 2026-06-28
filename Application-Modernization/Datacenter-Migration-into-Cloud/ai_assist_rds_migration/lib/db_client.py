#!/usr/bin/env python3
"""Database client module for DRS migration automation.

Provides read-only database access with SQL safety checks.
"""

import re
import sys

import pymysql

from config_loader import get_source_db_config, get_target_db_config
from log_utils import get_logger, mask_sensitive

logger = get_logger("db_client")

# Forbidden SQL patterns (case-insensitive)
FORBIDDEN_PATTERNS = [
    re.compile(r"\bDROP\b", re.IGNORECASE),
    re.compile(r"\bDELETE\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\b", re.IGNORECASE),
    re.compile(r"\bALTER\b", re.IGNORECASE),
    re.compile(r"\bCREATE\s+USER\b", re.IGNORECASE),
    re.compile(r"\bGRANT\b", re.IGNORECASE),
    re.compile(r"\bREVOKE\b", re.IGNORECASE),
    re.compile(r"\bINSERT\b", re.IGNORECASE),
    re.compile(r"\bUPDATE\b", re.IGNORECASE),
    re.compile(r"\bREPLACE\b", re.IGNORECASE),
    re.compile(r"\bLOAD\s+DATA\b", re.IGNORECASE),
]

# Cache for database connections
_connection_cache = {}


def _validate_sql(sql):
    """Validate that a SQL statement is safe (read-only).

    Args:
        sql: SQL statement to validate.

    Raises:
        ValueError: If the SQL contains forbidden operations.
    """
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.search(sql):
            raise ValueError(
                f"FORBIDDEN SQL detected: Statement contains prohibited operation. "
                f"Only read-only queries (SELECT/SHOW/DESCRIBE/EXPLAIN) are allowed. "
                f"SQL: {sql[:200]}"
            )


def get_connection(endpoint="source"):
    """Get a database connection.

    Args:
        endpoint: 'source' or 'target'.

    Returns:
        pymysql.connections.Connection instance.
    """
    if endpoint in _connection_cache:
        conn = _connection_cache[endpoint]
        try:
            conn.ping(reconnect=True)
            return conn
        except Exception:
            del _connection_cache[endpoint]

    if endpoint == "source":
        config = get_source_db_config()
    elif endpoint == "target":
        config = get_target_db_config()
    else:
        raise ValueError(f"Invalid endpoint: {endpoint}. Must be 'source' or 'target'.")

    if not config.get("host") or not config.get("user"):
        raise ValueError(f"Missing database connection config for {endpoint}")

    try:
        conn = pymysql.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            charset="utf8mb4",
            connect_timeout=10,
            read_timeout=30,
        )
        _connection_cache[endpoint] = conn
        logger.info(f"Connected to {endpoint} database: {config['host']}:{config['port']}")
        return conn
    except pymysql.Error as e:
        logger.error(f"Failed to connect to {endpoint} database: {mask_sensitive(str(e))}")
        raise


def execute_query(endpoint, sql, params=None):
    """Execute a read-only query on the specified database.

    Args:
        endpoint: 'source' or 'target'.
        sql: SQL query string (must be read-only).
        params: Query parameters (optional).

    Returns:
        List of result rows as dictionaries.
    """
    _validate_sql(sql)
    conn = get_connection(endpoint)
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, params)
            results = cursor.fetchall()
        logger.debug(f"Query on {endpoint}: {sql[:100]}... -> {len(results)} rows")
        return results
    except pymysql.Error as e:
        logger.error(f"Query failed on {endpoint}: {mask_sensitive(str(e))}")
        raise


def get_version(endpoint):
    """Get MySQL version string.

    Args:
        endpoint: 'source' or 'target'.

    Returns:
        Version string (e.g., '8.0.32').
    """
    results = execute_query(endpoint, "SELECT VERSION() AS version")
    return results[0]["version"] if results else None


def get_charset(endpoint):
    """Get character set configuration.

    Args:
        endpoint: 'source' or 'target'.

    Returns:
        Dictionary with character set information.
    """
    results = execute_query(
        endpoint,
        "SHOW VARIABLES WHERE Variable_name IN "
        "('character_set_server', 'character_set_database', 'collation_server', 'collation_database')",
    )
    charset_info = {}
    for row in results:
        charset_info[row["Variable_name"]] = row["Value"]
    return charset_info


def get_engines(endpoint):
    """Get available storage engines.

    Args:
        endpoint: 'source' or 'target'.

    Returns:
        List of engine dictionaries.
    """
    return execute_query(endpoint, "SHOW ENGINES")


def get_binlog_config(endpoint):
    """Get binary log configuration.

    Args:
        endpoint: 'source' or 'target'.

    Returns:
        Dictionary with binlog configuration.
    """
    results = execute_query(
        endpoint,
        "SHOW VARIABLES WHERE Variable_name IN "
        "('binlog_format', 'binlog_row_image', 'gtid_mode', 'log_bin', "
        "'binlog_checksum', 'sync_binlog')",
    )
    config = {}
    for row in results:
        config[row["Variable_name"]] = row["Value"]
    return config


def get_databases(endpoint):
    """Get list of databases (excluding system databases).

    Args:
        endpoint: 'source' or 'target'.

    Returns:
        List of database names.
    """
    results = execute_query(endpoint, "SHOW DATABASES")
    system_dbs = {"information_schema", "mysql", "performance_schema", "sys"}
    return [row["Database"] for row in results if row["Database"] not in system_dbs]


def get_table_list(endpoint, database):
    """Get list of tables in a database.

    Args:
        endpoint: 'source' or 'target'.
        database: Database name.

    Returns:
        List of table names.
    """
    results = execute_query(
        endpoint,
        "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'",
        (database,),
    )
    return [row["TABLE_NAME"] for row in results]


def get_table_row_count(endpoint, database, table):
    """Get row count for a specific table.

    Args:
        endpoint: 'source' or 'target'.
        database: Database name.
        table: Table name.

    Returns:
        Number of rows in the table.
    """
    # Use information_schema for approximate count (faster for large tables)
    results = execute_query(
        endpoint,
        "SELECT TABLE_ROWS FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
        (database, table),
    )
    if results and results[0]["TABLE_ROWS"] is not None:
        return int(results[0]["TABLE_ROWS"])
    # Fallback to exact count
    results = execute_query(
        endpoint,
        f"SELECT COUNT(*) AS cnt FROM `{database}`.`{table}`",
    )
    return results[0]["cnt"] if results else 0


def get_sample_data(endpoint, database, table, limit=10):
    """Get sample data from a table.

    Args:
        endpoint: 'source' or 'target'.
        database: Database name.
        table: Table name.
        limit: Maximum number of rows to return.

    Returns:
        List of row dictionaries.
    """
    return execute_query(
        endpoint,
        f"SELECT * FROM `{database}`.`{table}` LIMIT %s",
        (limit,),
    )


def get_foreign_keys(endpoint):
    """Check if there are foreign key constraints.

    Args:
        endpoint: 'source' or 'target'.

    Returns:
        List of foreign key information.
    """
    return execute_query(
        endpoint,
        "SELECT TABLE_SCHEMA, TABLE_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME "
        "FROM information_schema.TABLE_CONSTRAINTS "
        "WHERE CONSTRAINT_TYPE = 'FOREIGN KEY' AND TABLE_SCHEMA NOT IN ('mysql','information_schema','performance_schema','sys')",
    )


def get_triggers(endpoint):
    """Check if there are triggers.

    Args:
        endpoint: 'source' or 'target'.

    Returns:
        List of trigger information.
    """
    return execute_query(
        endpoint,
        "SELECT TRIGGER_SCHEMA, TRIGGER_NAME, EVENT_OBJECT_TABLE "
        "FROM information_schema.TRIGGERS "
        "WHERE TRIGGER_SCHEMA NOT IN ('mysql','information_schema','performance_schema','sys')",
    )


def get_routines(endpoint):
    """Check if there are stored procedures or functions.

    Args:
        endpoint: 'source' or 'target'.

    Returns:
        List of routine information.
    """
    return execute_query(
        endpoint,
        "SELECT ROUTINE_SCHEMA, ROUTINE_NAME, ROUTINE_TYPE "
        "FROM information_schema.ROUTINES "
        "WHERE ROUTINE_SCHEMA NOT IN ('mysql','information_schema','performance_schema','sys')",
    )


def close_all_connections():
    """Close all cached database connections."""
    for endpoint, conn in _connection_cache.items():
        try:
            conn.close()
        except Exception:
            pass
    _connection_cache.clear()
