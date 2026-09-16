# Reliability

How the platform keeps simulations reproducible, provisioning idempotent,
services healthy, and data consistent — plus the guardrails that catch
invalid synthetic physiology before it is written.

- [Determinism](#determinism)
- [Idempotency](#idempotency)
- [Service health](#service-health)
- [Data-integrity guardrails](#data-integrity-guardrails)
- [The device layer is a reliability model](#the-device-layer-is-a-reliability-model)
- [Development rule](#development-rule)
- [Known gaps](#known-gaps)

## Determinism

The same configuration produces the same telemetry, rows, and event IDs:

- Every simulation run carries explicit seeds (`config.seed`, per-run RNG).
- Event IDs are **UUID5-derived** (`simulation/scenario_runner.py`):

  ```
  event_id = uuid5(EVENT_NAMESPACE, f"{simulation_id}:{device_id}:{sequence_number}")
  ```

  `EVENT_NAMESPACE = 00000000-0000-0000-0000-000000000001`, `TRUTH_NAMESPACE =
  ...0002` for `vitals_truth` rows. Identical inputs → identical keys, which
  makes re-runs idempotent inserts and benchmarking apples-to-apples.
- Scenarios are pure functions of time: `progressive_hypoxemia`,
  `tachycardia`, and the baseline produce the same trajectories run-to-run.

## Idempotency

Every provisioning/write path can be run repeatedly without corrupting state:

| Path | Mechanism |
|------|-----------|
| `init_infra.py` / `provision_lakehouse` | `CREATE TABLE IF NOT EXISTS` / `CREATE SCHEMA IF NOT EXISTS`; catalog DDL guarded by catalog-namespace properties |
| Lakehouse DDL | `VITALS_TABLE_DDL` is `IF NOT EXISTS` |
| Schema Registry | identical schema POST returns the existing ID |
| Clinical store / M10 reseed | re-seeds only its own MRNs; `clinical/ddl.py` helpers are DDL-guarded |
| Superset import | `ensure_dashboard` returns the existing id (logs `[SKIP]`) when the slug already exists; soft-deleted datasets are **restored then refreshed** (`/api/v1/dataset/{id}/restore`) |
| Pipeline | consumer reads tail without committing; UUID5 IDs make rows stable |

A mismatch between simulated/consumed/inserted counts in `run_pipeline`
raises `pipeline mismatch at the lakehouse sink` instead of silently
dropping rows.

## Service health

- Every core service exposes a healthcheck (see [infrastructure](infrastructure.md)).
- `scripts/init_infra.py` blocks until all checks pass and then provisions
  buckets/catalogs, so scripts never race a half-started stack.
- HAPI caveat: `hapiproject/hapi` is a JRE-only image with no shell/curl, so
  its health cannot run in-container. `init_infra.py` polls
  `/fhir/metadata` from the host instead (documented in `docker-compose.yml`).

## Data-integrity guardrails

- `VitalsTelemetryEvent.__post_init__` requires timezone-aware timestamps and
  `sequence_number > 0`.
- `PhysiologicalState` validates that vital channels stay within physiological
  bounds and that `systolic_bp_mmhg >= diastolic_bp_mmhg`
  (`physiology/models.py`).
- The pipeline raises on count mismatches; `insert_vitals` writes only the
  rows the consumer hands it.
- Output contracts are frozen dataclasses (`PipelineResult`,
  `SimulationRun`) — no stray mutation between stages.

## The device layer is a reliability model

The device layer (`device/`) deliberately models *faults* — dropout,
disconnections, degraded quality codes — so reliability behavior is part of
the dataset (exercised by the `a2_alarm_sessions` lesson, for example) rather
than something that only breaks live. This makes downtime observable and
queryable.

## Development rule

Every milestone follows (README, "Development Rule"):

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

The repo gate for "Test": `uv run pytest` (150 tests, offline);
the lint gate: `uv run ruff check .`. See [testing](testing.md).

## Known gaps

- No CI pipeline; gates run locally.
- No backup/retention strategy for named volumes (Kafka logs, MinIO buckets,
  Postgres/MySQL data) — `docker compose down -v` destroys them.
- Superset metadata is SQLite on a gitignored bind mount; it is recreated by
  the idempotent import script rather than versioned.
- Consumer offset semantics are intentionally minimal (read-from-earliest,
  no commits) because the platform is batch replay, not a production stream —
  see [data_flow](data_flow.md).