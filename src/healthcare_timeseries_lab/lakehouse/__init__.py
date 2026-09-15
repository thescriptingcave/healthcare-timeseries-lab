"""Lakehouse DDL, JDBC catalog metadata, and analytics queries (Milestone 3).

Dialect: Trino Iceberg (connector ``lake``) backed by Iceberg JdbcCatalog
on PostgreSQL (Iceberg 1.11.0, ``io.trino_trino-iceberg-483``).

JdbcCatalog USchema constants below were extracted verbatim from the running
Trino plugin jar via ``javap -v -p`` on
``org.apache.iceberg.jdbc.JdbcUtil`` (constant pool Utf8 entries).

V0 catalog table DDL (V0_CREATE_CATALOG_SQL) + V1 view-support migration
(executeV1CatalogUpdate) + namespace properties table DDL
(CREATE_NAMESPACE_PROPERTIES_TABLE_SQL).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# JdbcCatalog USchema — exact strings from Iceberg 1.11.0 JdbcUtil
# ---------------------------------------------------------------------------

JDBC_CATALOG_V0_DDL = (
    "CREATE TABLE iceberg_tables("
    "catalog_name VARCHAR(255) NOT NULL,"
    "table_namespace VARCHAR(255) NOT NULL,"
    "table_name VARCHAR(255) NOT NULL,"
    "metadata_location VARCHAR(1000),"
    "previous_metadata_location VARCHAR(1000),"
    "PRIMARY KEY (catalog_name, table_namespace, table_name))"
)

JDBC_CATALOG_V1_ALTER = (
    "ALTER TABLE iceberg_tables ADD COLUMN iceberg_type VARCHAR(5)"
)

JDBC_CATALOG_NAMESPACE_PROPERTIES_DDL = (
    "CREATE TABLE iceberg_namespace_properties("
    "catalog_name VARCHAR(255) NOT NULL,"
    "namespace VARCHAR(255) NOT NULL,"
    "property_key VARCHAR(255),"
    "property_value VARCHAR(1000),"
    "PRIMARY KEY (catalog_name, namespace, property_key))"
)

# Down-catalog cleanup (legacy mis-shapen tables from earlier manual seeding).
# Only touches the ``lake`` schema — the real catalog metadata lives in
# ``public`` and must never be dropped by provisioning (it holds data).
_LEGACY_BOGUS_TABLES: list[str] = [
    "DROP TABLE IF EXISTS lake.iceberg_tables",
    "DROP TABLE IF EXISTS lake.iceberg_columns",
    "DROP TABLE IF EXISTS lake.iceberg_properties",
    "DROP SCHEMA IF EXISTS lake",
]

# Down-catalog bootstrap sequence (V0 + V1 migration, runs in one txn)
_JDBC_SEED_SEQUENCE: list[str] = [
    JDBC_CATALOG_V0_DDL,
    JDBC_CATALOG_V1_ALTER,
    JDBC_CATALOG_NAMESPACE_PROPERTIES_DDL,
]


def get_jdbc_catalog_cleanup() -> list[str]:
    """Statements to drop legacy mis-shapen tables in the ``lake`` schema."""
    return list(_LEGACY_BOGUS_TABLES)


def get_jdbc_catalog_seed_statements() -> list[str]:
    """Exact DDL sequence to create the Iceberg JdbcCatalog metadata tables."""
    return list(_JDBC_SEED_SEQUENCE)


# ---------------------------------------------------------------------------
# Lakehouse schema + vitals Iceberg table DDL
# ---------------------------------------------------------------------------

LAKEHOUSE_SCHEMA = "lakehouse"
VITALS_TABLE = "vitals"

LAKEHOUSE_SCHEMA_DDL = f"CREATE SCHEMA IF NOT EXISTS lake.{LAKEHOUSE_SCHEMA}"

VITALS_TABLE_DDL = (
    f"CREATE TABLE IF NOT EXISTS lake.{LAKEHOUSE_SCHEMA}.{VITALS_TABLE} ("
    "event_time TIMESTAMP(6) WITH TIME ZONE NOT NULL,"
    "patient_id VARCHAR(64) NOT NULL,"
    "heart_rate_bpm DOUBLE,"
    "spo2_pct DOUBLE,"
    "respiration_rate_bpm DOUBLE,"
    "temperature_c DOUBLE,"
    "systolic_bp_mmhg DOUBLE,"
    "diastolic_bp_mmhg DOUBLE"
    ") WITH ("
    "format = 'PARQUET',"
    "partitioning = ARRAY['day(event_time)']"
    ")"
)

LAKEHOUSE_DDL_STATEMENTS: list[str] = [
    LAKEHOUSE_SCHEMA_DDL,
    VITALS_TABLE_DDL,
]

# ---------------------------------------------------------------------------
# FHIR Observation -> vitals row mapping
# ---------------------------------------------------------------------------

# FHIR Observation component LOINC code -> (display_name, trino_column_name)
_VITAL_MAP: dict[str, tuple[str, str]] = {
    "8867-4": ("Heart rate", "heart_rate_bpm"),
    "2708-6": ("Oxygen saturation", "spo2_pct"),
    "9279-1": ("Respiratory rate", "respiration_rate_bpm"),
    "8310-5": ("Body temperature", "temperature_c"),
    "8480-6": ("Systolic blood pressure", "systolic_bp_mmhg"),
    "8462-4": ("Diastolic blood pressure", "diastolic_bp_mmhg"),
}


def _patient_id_from_reference(reference: str) -> str:
    """Extract the Patient UUID string from a FHIR ``subject.reference``."""
    return reference.rsplit("/", 1)[-1]


def parse_observation_row(observation: dict) -> dict | None:
    """Convert a FHIR Observation JSON (panel 85353-1) into a vitals row dict.

    Returns ``None`` when no components can be parsed.
    """
    effective = observation.get("effectiveDateTime")
    if effective is None:
        return None

    subject_ref = (observation.get("subject") or {}).get("reference", "")
    patient_id = _patient_id_from_reference(subject_ref) if subject_ref else ""

    row: dict = {
        "event_time": effective,
        "patient_id": patient_id,
    }

    for comp in observation.get("component", []):
        codings = (comp.get("code") or {}).get("coding", [])
        code = codings[0].get("code") if codings else None
        value_qty = comp.get("valueQuantity") or {}
        value = value_qty.get("value")
        if code in _VITAL_MAP and value is not None:
            _, col = _VITAL_MAP[code]
            row[col] = float(value)

    return row


# ---------------------------------------------------------------------------
# Analytics queries
# ---------------------------------------------------------------------------

ANALYTICS_AGG_QUERY = (
    f"SELECT patient_id,"
    f" COUNT(*) AS n,"
    f" AVG(heart_rate_bpm) AS avg_heart_rate,"
    f" AVG(spo2_pct) AS avg_spo2,"
    f" AVG(respiration_rate_bpm) AS avg_respiration_rate,"
    f" AVG(temperature_c) AS avg_temperature,"
    f" AVG(systolic_bp_mmhg) AS avg_systolic_bp,"
    f" AVG(diastolic_bp_mmhg) AS avg_diastolic_bp,"
    f" MIN(event_time) AS window_start,"
    f" MAX(event_time) AS window_end"
    f" FROM lake.{LAKEHOUSE_SCHEMA}.{VITALS_TABLE}"
    f" GROUP BY patient_id"
    f" ORDER BY patient_id"
)

READ_BACK_QUERY = (
    f"SELECT * FROM lake.{LAKEHOUSE_SCHEMA}.{VITALS_TABLE}"
    f" ORDER BY event_time"
)

__all__ = [
    "ANALYTICS_AGG_QUERY",
    "JDBC_CATALOG_NAMESPACE_PROPERTIES_DDL",
    "JDBC_CATALOG_V0_DDL",
    "JDBC_CATALOG_V1_ALTER",
    "LAKEHOUSE_DDL_STATEMENTS",
    "LAKEHOUSE_SCHEMA",
    "LAKEHOUSE_SCHEMA_DDL",
    "READ_BACK_QUERY",
    "VITALS_TABLE",
    "VITALS_TABLE_DDL",
    "_VITAL_MAP",
    "get_jdbc_catalog_cleanup",
    "get_jdbc_catalog_seed_statements",
    "parse_observation_row",
]
