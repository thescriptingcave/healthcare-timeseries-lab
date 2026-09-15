"""Idempotent lakehouse provisioning (Milestone 3).

Seeds the Iceberg JdbcCatalog USchema DDL into the backing Postgres
(instance: ``htl-postgres-iceberg``, DB: ``iceberg``), then creates the
``lake.lakehouse`` schema + ``vitals`` Iceberg table via Trino.

Run with::

    uv run python scripts/provision_lakehouse.py
"""

from __future__ import annotations

import sys

from healthcare_timeseries_lab.environment import settings
from healthcare_timeseries_lab.lakehouse import LAKEHOUSE_DDL_STATEMENTS
from healthcare_timeseries_lab.lakehouse.catalog import (
    init_jdbc_catalog_metadata,
    run_trino_ddl,
)


def run() -> None:
    cfg = settings()
    print("== Milestone 3: lakehouse provisioning ==")

    print("  1. JDBC catalog metadata (pg iceberg DB)")
    init_jdbc_catalog_metadata()

    print("  2. Trino DDL: schema + vitals table")
    run_trino_ddl(LAKEHOUSE_DDL_STATEMENTS, catalog=cfg.lake_catalog)

    print("== Provisioning complete ==")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
