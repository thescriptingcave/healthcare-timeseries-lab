"""Cross-catalog analytic query for the clinical store (Milestone 5).

``CLINICAL_SUMMARY_QUERY`` joins three Trino catalogs on the shared synthetic
patient UUID:

* ``mysql.clinical`` — patient demographics + encounter windows
* ``lake.lakehouse.vitals`` — telemetry aggregates per patient
* ``fhir_pg.public`` — FHIR Patient resources (matched by the ``sim.htl``
  identifier) and the Observation count pointing at those FHIR patients

The FHIR leg is joined by matching the resource identifier, because HAPI
rewrites ``subject.reference`` to its internal numeric id rather than the
original simulated UUID.
"""

from __future__ import annotations

from healthcare_timeseries_lab.clinical.ddl import (
    CLINICAL_CATALOG,
    CLINICAL_SCHEMA,
    ENCOUNTERS_TABLE,
    PATIENTS_TABLE,
)

CLINICAL_SUMMARY_QUERY = f"""
WITH fhir_patient AS (
  SELECT r.fhir_id,
         json_extract_scalar(rv.res_text_vc, '$.identifier[0].value') AS sim_patient_id
  FROM fhir_pg.public.hfj_res_ver rv
  JOIN fhir_pg.public.hfj_resource r ON r.res_id = rv.res_id
  WHERE rv.res_type = 'Patient'
),
obs_count AS (
  SELECT fp.sim_patient_id, COUNT(*) AS fhir_observations
  FROM fhir_patient fp
  JOIN fhir_pg.public.hfj_res_ver ov
    ON ov.res_type = 'Observation'
   AND json_extract_scalar(ov.res_text_vc, '$.subject.reference') = CONCAT('Patient/', fp.fhir_id)
  GROUP BY fp.sim_patient_id
),
latest_fhir AS (
  SELECT sim_patient_id, MAX(fhir_id) AS fhir_id
  FROM fhir_patient GROUP BY sim_patient_id
),
vitals_agg AS (
  SELECT patient_id, COUNT(*) AS n,
         AVG(heart_rate_bpm) AS avg_heart_rate,
         AVG(spo2_pct) AS avg_spo2,
         AVG(respiration_rate_bpm) AS avg_respiration_rate,
         AVG(temperature_c) AS avg_temperature,
         AVG(systolic_bp_mmhg) AS avg_systolic_bp,
         AVG(diastolic_bp_mmhg) AS avg_diastolic_bp,
         MAX(event_time) AS last_vitals_at
  FROM lake.lakehouse.vitals GROUP BY patient_id
)
SELECT p.patient_id, p.mrn, p.full_name, p.age, p.sex,
       e.encounter_id, e.started_at, e.ended_at, e.status,
       v.n AS vitals_count,
       ROUND(v.avg_heart_rate, 1) AS avg_hr,
       ROUND(v.avg_spo2, 1) AS avg_spo2,
       ROUND(v.avg_respiration_rate, 1) AS avg_rr,
       ROUND(v.avg_temperature, 2) AS avg_temp,
       ROUND(v.avg_systolic_bp, 1) AS avg_sbp,
       ROUND(v.avg_diastolic_bp, 1) AS avg_dbp,
       v.last_vitals_at,
       fp.fhir_id AS fhir_patient_id,
       oc.fhir_observations
FROM {CLINICAL_CATALOG}.{CLINICAL_SCHEMA}.{PATIENTS_TABLE} p
JOIN {CLINICAL_CATALOG}.{CLINICAL_SCHEMA}.{ENCOUNTERS_TABLE} e ON e.patient_id = p.patient_id
LEFT JOIN latest_fhir fp ON fp.sim_patient_id = p.patient_id
LEFT JOIN obs_count oc ON oc.sim_patient_id = p.patient_id
LEFT JOIN vitals_agg v ON v.patient_id = p.patient_id
ORDER BY p.patient_id
"""

__all__ = ["CLINICAL_SUMMARY_QUERY"]