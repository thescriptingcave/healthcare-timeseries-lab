# Healthcare Time-Series Lab

A synthetic healthcare time-series simulation and analytics learning platform.

The project is designed to generate reproducible physiological telemetry for learning and experimentation with time-series analysis, streaming systems, lakehouse architecture, SQL, Python, visualization, and eventually LLM-assisted analytical workflows.

> This project produces synthetic data for software engineering and analytics education. It is not a clinically validated physiological simulator and must not be used for diagnosis, treatment, or clinical decision-making.

## Core Design Principle

**Model the patient and the condition; do not script telemetry.**

The simulator maintains an underlying physiological state for each synthetic patient. Clinical conditions will modify that state over time, while simulated monitoring devices will observe the state and produce telemetry.

This keeps true physiology separate from observed device data.

```text
Patient Profile
      │
      ▼
Physiology Engine
      │
      ▼
Physiological State
      │
      ▼
Device / Fault Layer
      │
      ▼
Observed Telemetry
```

The device and fault layer (Milestone 8) implements this split.

## Sprint 0

Sprint 0 establishes the deterministic physiological simulation foundation.

Implemented:

* timezone-aware simulation clock
* synthetic patient profile
* six-vital physiological state
* seeded random number generation
* baseline physiological variability
* mean reversion toward patient baseline
* broad physiological guardrails
* systolic/diastolic blood-pressure invariant
* telemetry event contract
* deterministic event identifiers
* monotonic device sequence numbers
* reusable baseline simulation runner
* one-hour baseline simulation
* automated behavioral tests

### Supported Vitals

The current simulator models:

* heart rate
* oxygen saturation (SpO₂)
* respiration rate
* body temperature
* systolic blood pressure
* diastolic blood pressure

## Baseline Simulation

The initial baseline simulation generates one synthetic patient's physiological state every five seconds for one hour.

```text
60 minutes × 60 seconds / 5 seconds = 720 observations
```

The baseline model uses:

```text
next_value =
    current_value
    + mean_reversion
    + physiological_noise
```

where:

```text
mean_reversion =
    (patient_baseline - current_value)
    × mean_reversion_strength
```

This prevents uncontrolled random-walk behavior while still producing natural variation.

## Reproducibility

Simulation randomness is explicitly seeded.

Given the same:

* patient configuration
* simulation configuration
* random seed
* simulator implementation

the generated physiological trajectory is reproducible.

Event identifiers are also deterministic and are derived from:

```text
simulation_id
+ device_id
+ sequence_number
```

using UUID5.

## Current Architecture

```text
BaselineSimulationConfig
          │
          ▼
   SimulationClock
          │
          ▼
    PatientProfile
          │
          ▼
   PhysiologyEngine
          │
          ▼
 PhysiologicalState
     (true state)
          │
          ▼
VitalsTelemetryEvent
   (observed event)
```

During Sprint 0, observed telemetry directly mirrored physiological state.
Milestone 8 added an optional device/fault layer between them (send
`DeviceSimulationConfig` to a runner or the pipeline); with no device config,
telemetry still mirrors physiology exactly.

## Project Structure

```text
healthcare-timeseries-lab/
├── scripts/
 │   ├── build_m10_notebooks.py      # Milestone 10 (notebook builder)
 │   ├── import_superset_dashboards.py # Milestone 10 (Superset REST API import)
 │   ├── init_infra.py
│   ├── provision_lakehouse.py
│   ├── push_to_fhir.py
│   ├── run_baseline.py
│   ├── run_clinical_store.py
│   ├── run_hypoxemia.py
│   ├── run_lakehouse_analytics.py
│   └── run_pipeline.py             # Milestones 7-8 (unified pipeline + device)
├── infra/
│   ├── grafana/
│   │   └── dashboards/
│   │       ├── vitals.json            # Milestone 6 (vitals dashboard)
│   │       └── business_questions.json # Milestone 10 (8 panels mirroring B1-A3)
 │   └── superset/
 │       ├── Dockerfile                  # Milestone 10 (Superset + Trino driver)
 │       ├── patch_trino_dialect.py      # Milestone 10 (SQLAlchemy 2.x compat patch)
 │       └── dashboards/
 │           ├── b1_ward_census.json       # Milestone 10 (beginner)
│           ├── b2_hourly_handoff.json    # Milestone 10 (beginner)
│           ├── i1_first_drop.json        # Milestone 10 (intermediate)
│           ├── i2_moving_average.json    # Milestone 10 (intermediate)
│           ├── a1_desaturation_episodes.json # Milestone 10 (advanced)
│           └── a2_alarm_sessions.json    # Milestone 10 (advanced)
├── notebooks/
│   ├── device_vs_true_spo2.ipynb      # Milestone 9 (observed vs true vitals)
│   ├── tutorial_business_advanced.ipynb    # Milestone 10 (advanced SQL/business questions)
│   ├── tutorial_business_beginner.ipynb    # Milestone 10 (beginner SQL/business questions)
│   ├── tutorial_business_intermediate.ipynb  # Milestone 10 (intermediate SQL/business questions)
│   └── vitals_analysis.ipynb          # Milestone 6 (Jupyter analysis)

├── sql/
│   └── dql/
│       ├── beginner/       # Milestone 10 (B1-B3: ward census, handoff, flag patient)
│       ├── intermediate/   # Milestone 10 (I1-I3: first drop, moving avg, rank/decile)
│       └── advanced/       # Milestone 10 (A1-A3: episodes, sessions, observed vs truth)

├── datasets/
│   └── m10/                        # Milestone 10 (lesson snapshots + truth table)
├── src/
│   └── healthcare_timeseries_lab/
│       ├── analysis/            # Milestone 9 (observed-vs-truth alignment + metrics)
│       ├── clinical/            # Milestone 5 (MySQL clinical store)
│       ├── device/              # Milestone 8 (fault layer)
│       ├── fhir/                # Milestone 2
│       ├── ground_truth/
│       ├── lakehouse/           # Milestone 3
│       ├── patients/
│       ├── physiology/
│       ├── runtime/
│       ├── scenarios/
│       ├── simulation/          # Milestone 7 (pipeline orchestrator)
│       ├── streaming/           # Milestone 4 (Kafka + Avro)
│       ├── telemetry/
│       └── tutorials/           # Milestone 10 (SQL, notebooks, business questions)
└── tests/
    └── test_tutorials.py      # Milestone 10 (tutorials logic tests)
```

## Milestones

Every milestone is validated end-to-end before commit and push.

| Milestone | Result | How to observe |
|-----------|--------|----------------|
| M1 — Lakehouse infrastructure | Docker Compose lakehouse: Kafka, Schema Registry, MinIO, Postgres (FHIR + Iceberg), HAPI FHIR, Trino, InfluxDB | `docker compose ps` all healthy; `uv run python scripts/init_infra.py` |
| M2 — FHIR vital-signs panel | Simulated vitals pushed as LOINC `85353-1` transaction Bundle to HAPI | `uv run python scripts/push_to_fhir.py` → 12 Observations live on `/fhir` |
| M3 — Iceberg lakehouse | `lake.lakehouse.vitals` Iceberg table over JDBC catalog on Postgres; analytics read-back | `uv run python scripts/provision_lakehouse.py` + `uv run python scripts/run_lakehouse_analytics.py` |
| M4 — Kafka vitals streaming | Simulated vitals flow as Avro through Kafka/Schema Registry into `lake.lakehouse.vitals` | `uv run python scripts/run_pipeline.py --scenario baseline` (supersedes the M4 demo) → produce/consume + Trino aggregation |
| M5 — MySQL clinical store | MySQL `clinical.patients`/`clinical.encounters` exposed via Trino `mysql` catalog; one query joins MySQL demographics + Iceberg vitals + FHIR resources | `uv run python scripts/run_clinical_store.py` → 3-catalog patient summary |
| M6 — Observability & analysis | Grafana (custom image) + `trino-datasource` plugin + provisioned "Lakehouse Vitals" dashboard; Jupyter notebook analyzing `lake.lakehouse.vitals` | open http://localhost:3000 (admin/admin); `uv run jupyter nbconvert --to notebook --execute notebooks/vitals_analysis.ipynb` |
| M7 — Unified simulation → pipeline | One general pipeline runs any scenario (baseline or a clinical condition) through the physiology engine and streams it `simulate → Kafka (Avro) → Iceberg lakehouse → HAPI FHIR`; `run_baseline.py`/`run_hypoxemia.py` reuse the sim runners | `uv run python scripts/run_pipeline.py --scenario progressive_hypoxemia` → Kafka + lakehouse rows + FHIR Observations; `uv run python scripts/run_baseline.py` |
| M8 — Device / fault layer | `DeviceSimulator` between true physiology and observed telemetry: per-channel measurement noise, precision/rounding, sensor latency, clock skew, dropout, drift, spikes, flatlines and disconnects (with `CONNECTED`/`DISCONNECTED` status and `GOOD`/`DEGRADED`/`POOR`/`LOST` quality); pipeline applies a bedside-monitor profile by default | `uv run python scripts/run_pipeline.py --scenario baseline` → observed events with noise/rounding and occasional dropouts; `--no-device` restores exact physiology |
| M9 — Device-fidelity analysis | Jupyter notebook compares device-observed telemetry against the true physiological states: SpO2 overlay with dropout/spike markers, per-channel bias/MAE/RMSE, SpO2 error distribution, sensor latency, and a fault-window demo (SpO2 flatline + disconnect) using the `analysis` package (`align_observed_to_truth`, `error_metrics`) | `uv run python scripts/run_hypoxemia.py` writes observed + truth CSVs; `uv run jupyter nbconvert --to notebook --execute --inplace notebooks/device_vs_true_spo2.ipynb` |
| M10 — Business questions | 9 SQL tutorials (beginner/intermediate/advanced) mirroring clinical workflows; Grafana dashboard with 8 panels; Superset dashboards (6); Jupyter notebooks with business-driven analysis; ward (Naomi/Cole/Ivy) + legacy (Ava/Marcus) patients; truth table for device-fidelity benchmarking | `uv run python scripts/build_m10_notebooks.py`; run `tutorial_business_{beginner,intermediate,advanced}.ipynb`; `uv run pytest tests/test_tutorials.py`; import Superset dashboards with `uv run python scripts/import_superset_dashboards.py` |

## Development Environment

The project uses:

* Python 3.12
* uv
* pytest
* Ruff
* Git

Install dependencies:

```bash
uv sync
```

Run the tests:

```bash
uv run pytest
```

Run linting:

```bash
uv run ruff check .
```

## Visualization

**Grafana** (M6, M10):
- Run `docker compose up grafana`
- Access at http://localhost:3000 (admin/admin)
- Import dashboards from `infra/grafana/dashboards/`

**Superset** (M10):
- Run `docker compose -f docker-compose.superset.yml up -d superset`
- Access at http://localhost:8088 (admin/admin)
- Import dashboards: `uv run python scripts/import_superset_dashboards.py`
  - The script uses the Superset REST API (login + CSRF) to create the
    `trino` database connection, one virtual dataset per lesson query, the
    table/timeseries charts, and the dashboards. It is idempotent: re-running
    skips dashboards that already exist.
- The `trino` connection is created automatically as `trino://trino@trino:8080/lake`
  (the dashboard JSON files are a project-specific format and are **not**
  importable through the Superset UI; use the script).

Run the baseline simulator:

```bash
uv run python scripts/run_baseline.py
```

## Current Limitations

Sprint 0 intentionally keeps the simulator small.

Not yet implemented:

* correlated physiological signals
* clinical conditions
* scenario phases
* interventions
* patient response profiles
* simulation-run metadata
* ground-truth event datasets
* Parquet persistence
* Kafka
* Avro
* Schema Registry
* Iceberg
* MinIO
* Nessie
* Trino
* MySQL integration
* Grafana
* Jupyter analysis workflow
* dbt
* LLM assistance

These capabilities will be added incrementally after the deterministic simulator foundation is validated.

## Planned Platform

The longer-term architecture is:

```text
Clinical Data
    MySQL
      │
      │
Simulator
      │
      ├──────────────► Parquet / historical generation
      │
      ▼
Kafka + Avro + Schema Registry
      │
      ▼
Telemetry Ingestor
      │
      ▼
Apache Iceberg
      │
   MinIO + Nessie
      │
      ▼
     Trino
      │
      ├── TablePlus
      ├── Jupyter
      └── Grafana
```

An optional LLM assistance layer will eventually support scenario authoring, analytical interpretation, evaluation, synthetic narrative generation, and assisted SQL generation.

The LLM will not directly generate physiological state or telemetry.

## Development Rule

Every milestone follows:

```text
Build
  ↓
Test
  ↓
Validate behavior
  ↓
Document
  ↓
Commit
```

Nothing is committed until the implementation works and its behavior has been validated.
