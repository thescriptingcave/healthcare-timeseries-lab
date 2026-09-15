"""Provision the MySQL clinical store and run a three-catalog analytic
summary joining MySQL demographics, Iceberg vitals, and FHIR resources
(Milestone 5).

Run with::

    uv run python scripts/run_clinical_store.py
"""

from __future__ import annotations

import sys

from healthcare_timeseries_lab.clinical import (
    CLINICAL_SUMMARY_QUERY,
    get_clinical_cleanup,
    get_clinical_create_statements,
    get_clinical_seed_statements,
)
from healthcare_timeseries_lab.lakehouse.catalog import run_trino_ddl, trino_query


def run() -> None:
    print("== Milestone 5: MySQL clinical store + cross-catalog analytics ==")

    print("  1. Re-creating mysql.clinical tables ...")
    run_trino_ddl(get_clinical_cleanup())
    run_trino_ddl(get_clinical_create_statements())
    print("     patients + encounters tables ready")

    print("  2. Seeding demographics + encounters ...")
    run_trino_ddl(get_clinical_seed_statements())
    print("     2 patients, 2 encounters seeded")

    print("  3. Cross-catalog summary (mysql . lake . fhir_pg):")
    rows = trino_query(CLINICAL_SUMMARY_QUERY)
    print(f"     {len(rows)} patient rows returned")
    for row in rows:
        (
            patient_id,
            mrn,
            full_name,
            age,
            sex,
            encounter_id,
            started_at,
            ended_at,
            status,
            vitals_count,
            avg_hr,
            avg_spo2,
            avg_rr,
            avg_temp,
            avg_sbp,
            avg_dbp,
            last_vitals_at,
            fhir_patient_id,
            fhir_observations,
        ) = row
        print()
        print(f"    {full_name} (MRN {mrn}, age {age}, {sex})")
        print(f"      clinical.patient_id  = {patient_id}")
        print(f"      encounter            = {encounter_id} [{status}]")
        print(f"      window               = {started_at} -> {ended_at}")
        vitals = (
            f"vitals_count={vitals_count}  avg_HR={avg_hr}  avg_SpO2={avg_spo2}  "
            f"avg_RR={avg_rr}  avg_T={avg_temp}  avg_SBP={avg_sbp}  avg_DBP={avg_dbp}  "
            f"last_vitals={last_vitals_at}"
            if vitals_count is not None
            else "no lakehouse vitals"
        )
        print(f"      lake.lakehouse.vitals = {vitals}")
        if fhir_patient_id is not None:
            print(
                f"      fhir_pg patient       = {fhir_patient_id} "
                f"({fhir_observations} Observations)"
            )
        else:
            print("      fhir_pg               = no matching Patient resource")

    print()
    print("MILESTONE 5 CROSS-CATALOG OK")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)