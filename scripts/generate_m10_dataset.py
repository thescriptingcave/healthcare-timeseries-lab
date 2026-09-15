"""Generate the Milestone 10 ward dataset.

Builds a small multi-patient ICU ward that the business-question tutorials
query: three synthetic patients with realistic vitals ranges and clinical
events (one desaturation, one tachycardia, one stable control), written to:

* ``lake.lakehouse.vitals`` — observed device telemetry (via Trino INSERT)
* ``lake.lakehouse.vitals_truth`` — true underlying physiology for each tick
  (via Trino INSERT) so the advanced lessons can benchmark device fidelity
* ``mysql.clinical.patients`` + ``mysql.clinical.encounters`` — demographics
  and admission/discharge windows (re-seeded for these MRNs only)
* ``datasets/m10/truth/*.parquet`` — local truth snapshots for offline reads

Run with::

    uv run python scripts/generate_m10_dataset.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pandas as pd

from healthcare_timeseries_lab.clinical.ddl import (
    CLINICAL_CATALOG,
    CLINICAL_SCHEMA,
    ENCOUNTERS_TABLE,
    PATIENTS_TABLE,
    _literal,
    _quote,
    _timestamps,
)
from healthcare_timeseries_lab.device import (
    default_bedside_monitor_config,
)
from healthcare_timeseries_lab.lakehouse.catalog import run_trino_ddl, trino_query
from healthcare_timeseries_lab.lakehouse.writer import insert_vitals
from healthcare_timeseries_lab.patients.models import PatientProfile
from healthcare_timeseries_lab.scenarios.library import (
    progressive_hypoxemia,
    tachycardia,
)
from healthcare_timeseries_lab.simulation.scenario_runner import (
    ScenarioSimulationConfig,
    run_scenario_simulation,
)

WARD_START = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)

TRUTH_DIR = Path("datasets/m10/truth")

TRUTH_TABLE = "lake.lakehouse.vitals_truth"
TRUTH_COLUMNS = (
    "event_time,sequence_number,patient_id,"
    "heart_rate_bpm,spo2_pct,respiration_rate_bpm,temperature_c,"
    "systolic_bp_mmhg,diastolic_bp_mmhg"
)


@dataclass(frozen=True)
class WardPatient:
    key: str
    patient_id: UUID
    full_name: str
    mrn: str
    age: int
    sex: str
    admitted_at: str
    ended_at: str | None
    scenario_name: str
    start_offset: timedelta
    duration: timedelta
    seed: int
    baseline_heart_rate_bpm: float
    baseline_spo2_pct: float
    baseline_respiration_rate_bpm: float
    baseline_temperature_c: float
    baseline_systolic_bp_mmhg: float
    baseline_diastolic_bp_mmhg: float

    @property
    def start_time(self) -> datetime:
        return WARD_START + self.start_offset

    def profile(self) -> PatientProfile:
        return PatientProfile(
            patient_id=self.patient_id,
            age=self.age,
            sex=self.sex,
            baseline_heart_rate_bpm=self.baseline_heart_rate_bpm,
            baseline_spo2_pct=self.baseline_spo2_pct,
            baseline_respiration_rate_bpm=self.baseline_respiration_rate_bpm,
            baseline_temperature_c=self.baseline_temperature_c,
            baseline_systolic_bp_mmhg=self.baseline_systolic_bp_mmhg,
            baseline_diastolic_bp_mmhg=self.baseline_diastolic_bp_mmhg,
        )

    def conditions(self) -> tuple:
        if self.scenario_name == "progressive_hypoxemia":
            return progressive_hypoxemia()
        if self.scenario_name == "tachycardia":
            return tachycardia()
        return ()


WARD_PATIENTS: tuple[WardPatient, ...] = (
    WardPatient(
        key="naomi",
        patient_id=UUID("55555555-5555-5555-5555-555555555555"),
        full_name="Naomi Brooks",
        mrn="MRN-000101",
        age=52,
        sex="female",
        admitted_at="2026-01-01 00:00:00",
        ended_at=None,
        scenario_name="progressive_hypoxemia",
        start_offset=timedelta(0),
        duration=timedelta(hours=6),
        seed=3,
        baseline_heart_rate_bpm=76.0,
        baseline_spo2_pct=99.0,
        baseline_respiration_rate_bpm=15.0,
        baseline_temperature_c=36.9,
        baseline_systolic_bp_mmhg=128.0,
        baseline_diastolic_bp_mmhg=78.0,
    ),
    WardPatient(
        key="cole",
        patient_id=UUID("66666666-6666-6666-6666-666666666666"),
        full_name="Cole Freeman",
        mrn="MRN-000102",
        age=68,
        sex="male",
        admitted_at="2026-01-01 00:30:00",
        ended_at="2026-01-01 05:30:00",
        scenario_name="tachycardia",
        start_offset=timedelta(minutes=30),
        duration=timedelta(hours=5),
        seed=7,
        baseline_heart_rate_bpm=84.0,
        baseline_spo2_pct=97.0,
        baseline_respiration_rate_bpm=17.0,
        baseline_temperature_c=37.1,
        baseline_systolic_bp_mmhg=142.0,
        baseline_diastolic_bp_mmhg=86.0,
    ),
    WardPatient(
        key="ivy",
        patient_id=UUID("77777777-7777-7777-7777-777777777777"),
        full_name="Ivy Watson",
        mrn="MRN-000103",
        age=47,
        sex="female",
        admitted_at="2026-01-01 01:00:00",
        ended_at="2026-01-01 04:00:00",
        scenario_name="baseline",
        start_offset=timedelta(hours=1),
        duration=timedelta(hours=3),
        seed=11,
        baseline_heart_rate_bpm=62.0,
        baseline_spo2_pct=99.0,
        baseline_respiration_rate_bpm=12.0,
        baseline_temperature_c=36.7,
        baseline_systolic_bp_mmhg=115.0,
        baseline_diastolic_bp_mmhg=72.0,
    ),
)


def _truth_record(state, patient_id: UUID, sequence_number: int) -> dict:
    return {
        "event_time": state.timestamp.isoformat(),
        "sequence_number": sequence_number,
        "patient_id": str(patient_id),
        "heart_rate_bpm": state.heart_rate_bpm,
        "spo2_pct": state.spo2_pct,
        "respiration_rate_bpm": state.respiration_rate_bpm,
        "temperature_c": state.temperature_c,
        "systolic_bp_mmhg": state.systolic_bp_mmhg,
        "diastolic_bp_mmhg": state.diastolic_bp_mmhg,
    }


def _trino_timestamp(iso_string: str) -> str:
    return iso_string.replace("T", " ")


def _clone_simulation(
    patient: WardPatient,
) -> tuple:
    config = ScenarioSimulationConfig(
        simulation_id=UUID(f"a0000000-aaaa-aaaa-aaaa-{patient.patient_id.hex[20:]}"),
        device_id=UUID(f"b0000000-bbbb-bbbb-bbbb-{patient.patient_id.hex[20:]}"),
        scenario_name=patient.scenario_name,
        scenario_version="1.0",
        start_time=patient.start_time,
        duration=patient.duration,
        step=timedelta(seconds=5),
        seed=patient.seed,
    )

    return run_scenario_simulation(
        patient=patient.profile(),
        config=config,
        conditions=patient.conditions(),
        device=default_bedside_monitor_config(),
    )


def create_truth_table() -> None:
    ddl = (
        f"CREATE TABLE IF NOT EXISTS {TRUTH_TABLE} ("
        "event_time TIMESTAMP WITH TIME ZONE NOT NULL,"
        "sequence_number BIGINT NOT NULL,"
        "patient_id VARCHAR NOT NULL,"
        "heart_rate_bpm DOUBLE NOT NULL,"
        "spo2_pct DOUBLE NOT NULL,"
        "respiration_rate_bpm DOUBLE NOT NULL,"
        "temperature_c DOUBLE NOT NULL,"
        "systolic_bp_mmhg DOUBLE NOT NULL,"
        "diastolic_bp_mmhg DOUBLE NOT NULL)"
    )
    run_trino_ddl([f"DROP TABLE IF EXISTS {TRUTH_TABLE}", ddl])


def clear_observed() -> None:
    identifiers: list[str] = []
    for p in WARD_PATIENTS:
        identifiers.extend([str(p.patient_id), p.patient_id.hex])
    clause = ", ".join(f"'{value}'" for value in identifiers)
    run_trino_ddl(
        [
            (
                f"DELETE FROM lake.lakehouse.vitals "
                f"WHERE patient_id IN ({clause})"
            )
        ]
    )


def insert_truth(patient: WardPatient) -> int:
    records: list[dict] = []
    result = _clone_simulation(patient)
    for sequence_number, state in enumerate(result.states, start=1):
        records.append(_truth_record(state, patient.patient_id, sequence_number))

    placeholders: list[str] = []
    for record in records:
        placeholders.append(
            f"(TIMESTAMP '{_trino_timestamp(record['event_time'])}', "
            f"{record['sequence_number']}, "
            f"'{record['patient_id']}', {record['heart_rate_bpm']}, "
            f"{record['spo2_pct']}, {record['respiration_rate_bpm']}, "
            f"{record['temperature_c']}, {record['systolic_bp_mmhg']}, "
            f"{record['diastolic_bp_mmhg']})"
        )
    statement = (
        f"INSERT INTO {TRUTH_TABLE} ({TRUTH_COLUMNS}) VALUES "
        f"{', '.join(placeholders)}"
    )
    run_trino_ddl([statement])
    return len(records)


def ingest_observed(patient: WardPatient) -> int:
    result = _clone_simulation(patient)
    records = [
        {
            "event_time": event.event_time.isoformat(),
            "patient_id": str(patient.patient_id),
            "heart_rate_bpm": event.heart_rate_bpm,
            "spo2_pct": event.spo2_pct,
            "respiration_rate_bpm": event.respiration_rate_bpm,
            "temperature_c": event.temperature_c,
            "systolic_bp_mmhg": event.systolic_bp_mmhg,
            "diastolic_bp_mmhg": event.diastolic_bp_mmhg,
        }
        for event in result.events
    ]
    return insert_vitals(records)


def seed_clinical() -> None:
    patient_rows = [
        (
            str(p.patient_id),
            p.mrn,
            p.full_name,
            p.age,
            p.sex,
            p.admitted_at,
        )
        for p in WARD_PATIENTS
    ]
    encounter_rows = [
        (
            f"enc-m10-{p.patient_id.hex[:4]}",
            str(p.patient_id),
            p.admitted_at,
            p.ended_at,
            "ACTIVE" if p.ended_at is None else "COMPLETED",
        )
        for p in WARD_PATIENTS
    ]

    patients_values = ", ".join(
        f"({_quote(patient_id)}, {_quote(mrn)}, {_quote(full_name)}, "
        f"{_literal(age)}, {_quote(sex)}, {_timestamps(admitted_at)})"
        for (patient_id, mrn, full_name, age, sex, admitted_at) in patient_rows
    )
    encounters_values = ", ".join(
        f"({_quote(encounter_id)}, {_quote(patient_id)}, {_timestamps(started_at)}, "
        f"{'NULL' if ended_at is None else _timestamps(ended_at)}, "
        f"{_quote(status)})"
        for (encounter_id, patient_id, started_at, ended_at, status) in encounter_rows
    )

    mrn_clause = ", ".join(_quote(p.mrn) for p in WARD_PATIENTS)

    existing_patients = trino_query(
        f"SELECT count(*) FROM {CLINICAL_CATALOG}.{CLINICAL_SCHEMA}.{PATIENTS_TABLE} "
        f"WHERE mrn IN ({mrn_clause})"
    )[0][0]
    existing_encounters = trino_query(
        f"SELECT count(*) FROM {CLINICAL_CATALOG}.{CLINICAL_SCHEMA}.{ENCOUNTERS_TABLE} "
        f"WHERE encounter_id LIKE 'enc-m10-%'"
    )[0][0]

    statements: list[str] = []

    if existing_patients < len(patient_rows):
        statements.append(
            
                f"INSERT INTO {CLINICAL_CATALOG}.{CLINICAL_SCHEMA}.{PATIENTS_TABLE} "
                f"(patient_id, mrn, full_name, age, sex, admitted_at) "
                f"VALUES {patients_values}"
            
        )

    if existing_encounters < len(encounter_rows):
        statements.append(
            
                f"INSERT INTO {CLINICAL_CATALOG}.{CLINICAL_SCHEMA}.{ENCOUNTERS_TABLE} "
                f"(encounter_id, patient_id, started_at, ended_at, status) "
                f"VALUES {encounters_values}"
            
        )

    run_trino_ddl(statements)


def write_truth_parquets() -> None:
    TRUTH_DIR.mkdir(parents=True, exist_ok=True)
    for patient in WARD_PATIENTS:
        result = _clone_simulation(patient)
        records = [
            _truth_record(state, patient.patient_id, sequence_number)
            for sequence_number, state in enumerate(result.states, start=1)
        ]
        frame = pd.DataFrame(records)
        frame["event_time"] = pd.to_datetime(
            frame["event_time"],
            format="ISO8601",
        )
        frame.to_parquet(
            TRUTH_DIR / f"{patient.key}.parquet",
            index=False,
        )


def run() -> None:
    print("== Generating Milestone 10 ward dataset ==")

    print("  1. Truth telemetry table (iceberg vitals_truth) ...")
    create_truth_table()
    clear_observed()

    for patient in WARD_PATIENTS:
        print(f"  2. Generating {patient.full_name} ({patient.scenario_name}) ...")
        observed = ingest_observed(patient)
        truth = insert_truth(patient)
        print(
            f"     observed={observed} rows, "
            f"truth={truth} states"
        )

    print("  3. Seeding mysql.clinical patients + encounters ...")
    seed_clinical()

    print("  4. Writing truth parquets to datasets/m10/truth ...")
    write_truth_parquets()

    print()
    print("  5. Verification via Trino:")
    print("     vitals          =", trino_query(
        "SELECT patient_id, count(*) FROM lake.lakehouse.vitals "
        "WHERE patient_id IN ('55555555-5555-5555-5555-555555555555',"
        "'66666666-6666-6666-6666-666666666666',"
        "'77777777-7777-7777-7777-777777777777') "
        "GROUP BY patient_id ORDER BY patient_id"
    ))
    print("     vitals_truth    =", trino_query(
        "SELECT patient_id, count(*) FROM lake.lakehouse.vitals_truth "
        "WHERE patient_id IN ('55555555-5555-5555-5555-555555555555',"
        "'66666666-6666-6666-6666-666666666666',"
        "'77777777-7777-7777-7777-777777777777') "
        "GROUP BY patient_id ORDER BY patient_id"
    ))
    print("     clinical        =", trino_query(
        f"SELECT p.mrn, e.status, e.ended_at "
        f"FROM {CLINICAL_CATALOG}.{CLINICAL_SCHEMA}.{PATIENTS_TABLE} p "
        f"LEFT JOIN {CLINICAL_CATALOG}.{CLINICAL_SCHEMA}.{ENCOUNTERS_TABLE} e "
        f"ON e.patient_id = p.patient_id WHERE p.mrn LIKE 'MRN-0001%' ORDER BY p.mrn"
    ))

    print()
    print("MILESTONE 10 WARD DATASET OK")


if __name__ == "__main__":
    run()