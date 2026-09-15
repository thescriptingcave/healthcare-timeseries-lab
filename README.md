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

The device and fault layers are planned but are not yet implemented.

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

During Sprint 0, observed telemetry directly mirrors physiological state.

A later device layer will introduce:

* measurement noise
* precision and rounding
* sensor latency
* dropout
* drift
* spikes
* flatlines
* noisy signals
* clock skew
* device disconnects

## Project Structure

```text
healthcare-timeseries-lab/
├── scripts/
│   ├── init_infra.py
│   ├── provision_lakehouse.py
│   ├── push_to_fhir.py
│   ├── run_lakehouse_analytics.py
│   ├── run_kafka_streaming.py
│   └── run_baseline.py
├── infra/
│   └── grafana/            # Milestone 6 (image, provisioning, dashboard)
├── notebooks/
│   └── vitals_analysis.ipynb  # Milestone 6 (Jupyter analysis)
├── src/
│   └── healthcare_timeseries_lab/
│       ├── clinical/            # Milestone 5 (MySQL clinical store)
│       ├── fhir/                # Milestone 2
│       ├── ground_truth/
│       ├── lakehouse/           # Milestone 3
│       ├── patients/
│       ├── physiology/
│       ├── runtime/
│       ├── scenarios/
│       ├── simulation/
│       ├── streaming/           # Milestone 4 (Kafka + Avro)
│       └── telemetry/
└── tests/
```

## Milestones

Every milestone is validated end-to-end before commit and push.

| Milestone | Result | How to observe |
|-----------|--------|----------------|
| M1 — Lakehouse infrastructure | Docker Compose lakehouse: Kafka, Schema Registry, MinIO, Postgres (FHIR + Iceberg), HAPI FHIR, Trino, InfluxDB | `docker compose ps` all healthy; `uv run python scripts/init_infra.py` |
| M2 — FHIR vital-signs panel | Simulated vitals pushed as LOINC `85353-1` transaction Bundle to HAPI | `uv run python scripts/push_to_fhir.py` → 12 Observations live on `/fhir` |
| M3 — Iceberg lakehouse | `lake.lakehouse.vitals` Iceberg table over JDBC catalog on Postgres; analytics read-back | `uv run python scripts/provision_lakehouse.py` + `uv run python scripts/run_lakehouse_analytics.py` |
| M4 — Kafka vitals streaming | Simulated vitals flow as Avro through Kafka/Schema Registry into `lake.lakehouse.vitals` | `uv run python scripts/run_kafka_streaming.py` → produce/consume + Trino aggregation |
| M5 — MySQL clinical store | MySQL `clinical.patients`/`clinical.encounters` exposed via Trino `mysql` catalog; one query joins MySQL demographics + Iceberg vitals + FHIR resources | `uv run python scripts/run_clinical_store.py` → 3-catalog patient summary |
| M6 — Observability & analysis | Grafana (custom image) + `trino-datasource` plugin + provisioned "Lakehouse Vitals" dashboard; Jupyter notebook analyzing `lake.lakehouse.vitals` | open http://localhost:3000 (admin/admin); `uv run jupyter nbconvert --to notebook --execute notebooks/vitals_analysis.ipynb` |

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
* device simulation
* sensor faults
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
