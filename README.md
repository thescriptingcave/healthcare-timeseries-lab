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
│   └── run_baseline.py
├── src/
│   └── healthcare_timeseries_lab/
│       ├── patients/
│       ├── physiology/
│       ├── runtime/
│       ├── simulation/
│       └── telemetry/
└── tests/
```

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
