# Testing

How the codebase is tested, what the test suite covers, and the gates every
change must pass.

- [Strategy](#strategy)
- [Module map](#module-map)
- [Conventions](#conventions)
- [Tutorials tests](#tutorials-tests)
- [Gates](#gates)
- [How to run](#how-to-run)
- [Known gaps](#known-gaps)

## Strategy

The suite is **unit + behavioral**, runnable **fully offline** — no Docker, no
live Kafka/Iceberg/FHIR. Pipeline and streaming orchestrators keep their stage
functions injectable (see `simulation/pipeline.py` docstring), so tests inject
fakes instead of infrastructure. Current state: **150 tests passing** across
19 test files, plus a clean `ruff` run.

```text
uv run pytest          # 150 passed
uv run ruff check .    # All checks passed
```

Test files are 1:1 with source areas (`src/...` vs `tests/`), so a change to
a module expects its mirror test file to update and stay green.

## Module map

Test counts as of this document:

| Test file | Count | Covers |
|-----------|------:|--------|
| `test_lakehouse.py` | 24 | ICE catalog DDL, `insert_vitals`, FHIR→row mapping, table reads |
| `test_device.py` | 16 | `DeviceSimulator`, noise/precision/dropout, status/quality |
| `test_streaming.py` | 9 | Avro schema, Schema Registry idempotent registration, produce/consume fakes |
| `test_simulation.py` | 9 | `run_baseline_simulation`, runner configs |
| `test_physiology.py` | 9 | `PhysiologyEngine`, bounds, BP invariant, deterministic seeds |
| `test_clinical.py` | 9 | MySQL DDL/seed helpers, typed store queries |
| `test_tutorials.py` | 7 | M10 lesson registry, SQL files, snapshot/run helpers |
| `test_scenario_simulation.py` | 7 | scenario runner + ground-truth wiring |
| `test_scenario_engine.py` | 7 | condition evaluation, onset/duration/severity |
| `test_observability.py` | 7 | InfluxDB exporter payloads, Grafana provisioning helpers |
| `test_pipeline.py` | 6 | unified pipeline orchestration, count-mismatch detection |
| `test_patient.py` | 6 | `PatientProfile` normalization/baselines |
| `test_ground_truth.py` | 6 | truth event conversion, `vitals_truth` mapping |
| `test_analysis.py` | 6 | `align_observed_to_truth`, `error_metrics` |
| `test_simulation_models.py` | 5 | run/output dataclasses |
| `test_fhir.py` | 5 | Observation bundle build/validation, LOINC codes |
| `test_clock.py` | 5 | `SimulationClock` stepping |
| `test_scenarios.py` | 4 | scenario library shape |
| `test_telemetry.py` | 3 | `VitalsTelemetryEvent` invariants, conversion |

## Conventions

- **Determinism**: tests use explicit small seeds; the seeded engine makes
  expected-values tests stable.
- **No live infra**: anything network/topology-bound is covered via injected
  fakes or pure logic; infrastructure bring-up is validated by
  `scripts/init_infra.py` and manual milestone checks, not pytest.
- **Naming**: `test_<area>.py`, functions `test_*`.
- **Style**: type-hinted signatures, docstrings for expectations, minimal
  mocking surface.

## Tutorials tests

`tests/test_tutorials.py` (7 tests) is pure logic: it validates the lesson
registry (tiers, 9 lessons, order), that every lesson has a SQL file with
non-empty statements, and the snapshot/run helpers. It does **not** execute
SQL against Trino. The heavier lesson behaviors are exercised by running the
generated notebooks (`build_m10_notebooks.py` then execute
`tutorial_business_{beginner,intermediate,advanced}.ipynb`) as a manual,
documented step in the M10 observe path.

## Gates

The development rule (README, "Development Rule"):

```text
Build
  ↓
Test          → uv run pytest
  ↓
Validate behavior    → milestone "How to observe" steps (end-to-end)
  ↓
Document
  ↓
Commit
```

CI is not configured; gates run locally before every commit.

## How to run

```bash
uv run pytest                  # full suite
uv run pytest tests/test_fhir.py   # single file
uv run pytest -q -m "not ..."  # (no markers are defined currently)
uv run ruff check .            # lint gate
```

## Known gaps

- No CI pipeline (would gate on GitHub Actions).
- No coverage metric is tracked (`pytest --cov` not configured).
- No infra-level integration suite; end-to-end verification relies on the
  milestone "observe" steps (`infra/` + `scripts/`) and the manual Playwright
  checks used during M10 Superset development.
- Some paths (notebook execution, dashboard layout, Trino SQL against real
  data) are manually verified rather than automated.