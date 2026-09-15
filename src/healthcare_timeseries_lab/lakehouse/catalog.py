"""Low-level catalog helpers for the lakehouse package (Milestone 3).

Thin wrappers around ``trino.dbapi`` (catalog DDL) and ``psycopg``
(JDBC metadata seeding into the backing Postgres).
"""

from __future__ import annotations

from urllib.parse import urlparse

import psycopg
from trino import dbapi as trino_dbapi

from healthcare_timeseries_lab.environment import settings
from healthcare_timeseries_lab.lakehouse import get_jdbc_catalog_cleanup

# ---------------------------------------------------------------------------
# Trino helpers
# ---------------------------------------------------------------------------


def _trino_connection() -> trino_dbapi.Connection:
    cfg = settings()
    parsed = urlparse(cfg.trino_url)
    return trino_dbapi.connect(
        host=parsed.hostname,
        port=parsed.port,
        user=cfg.trino_user,
        timezone="UTC",
    )


def run_trino_ddl(statements: list[str], catalog: str | None = None) -> None:
    """Execute DDL statements via Trino. No-op for empty lists."""
    if not statements:
        return
    connection = _trino_connection()
    cursor = connection.cursor()
    for stmt in statements:
        cursor.execute(stmt)
    if catalog:
        # Validate the catalog is reachable by listing its schemas
        cursor.execute(f"SHOW SCHEMAS FROM {catalog}")
    cursor.close()


def trino_query(sql: str) -> list[tuple]:
    """Run a query via Trino and return all result rows."""
    connection = _trino_connection()
    cursor = connection.cursor()
    cursor.execute(sql)
    rows = cursor.fetchall()
    cursor.close()
    return rows


# ---------------------------------------------------------------------------
# Postgres JDBC metadata helpers
# ---------------------------------------------------------------------------


def _pg_connection() -> psycopg.Connection:
    # The backing Postgres is the iceberg instance exposed on its own port.
    # Port 5434 is the host-mapped ``htl-postgres-iceberg`` container.
    iceberg_port = 5434
    return psycopg.connect(
        host="localhost",
        port=iceberg_port,
        dbname="iceberg",
        user="iceberg",
        password="iceberg",
    )


def _table_exists(cur, table: str) -> bool:
    cur.execute(
        "SELECT EXISTS ("
        "  SELECT 1 FROM information_schema.tables"
        "  WHERE table_schema = 'public' AND table_name = %s"
        ")",
        (table,),
    )
    return cur.fetchone()[0]


def _column_exists(cur, table: str, column: str) -> bool:
    cur.execute(
        "SELECT EXISTS ("
        "  SELECT 1 FROM information_schema.columns"
        "  WHERE table_schema = 'public' AND table_name = %s AND column_name = %s"
        ")",
        (table, column),
    )
    return cur.fetchone()[0]


def init_jdbc_catalog_metadata() -> None:
    """Create the exact Iceberg 1.11 USchema; never drops the real tables.

    Cleanup only removes legacy mis-shapen tables in the ``lake`` schema.
    The ``public`` metadata tables are created if missing and migrated to
    V1 (``iceberg_type``) if needed, so existing lakehouse data survives.
    """
    from healthcare_timeseries_lab.lakehouse import (
        JDBC_CATALOG_NAMESPACE_PROPERTIES_DDL,
        JDBC_CATALOG_V0_DDL,
        JDBC_CATALOG_V1_ALTER,
    )

    conn = _pg_connection()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            for stmt in get_jdbc_catalog_cleanup():
                cur.execute(stmt)

            if not _table_exists(cur, "iceberg_tables"):
                cur.execute(JDBC_CATALOG_V0_DDL)
                cur.execute(JDBC_CATALOG_V1_ALTER)
                print("    metadata tables created (V0+V1)")
            elif not _column_exists(cur, "iceberg_tables", "iceberg_type"):
                cur.execute(JDBC_CATALOG_V1_ALTER)
                print("    iceberg_tables migrated to V1 (iceberg_type)")

            if not _table_exists(cur, "iceberg_namespace_properties"):
                cur.execute(JDBC_CATALOG_NAMESPACE_PROPERTIES_DDL)
                print("    iceberg_namespace_properties created")
        conn.commit()
    finally:
        conn.close()
