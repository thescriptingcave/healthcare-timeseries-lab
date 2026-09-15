-- ============================================================================
-- Lesson B3 — "Flag the patient who needs attention overnight"
--
-- Business question
--   It is 04:00 on the ward. Which monitored patients spent the previous
--   hour (03:00-04:00) with an average SpO2 below 95%? Everything we know
--   says one of them was desaturating during the night.
--
-- Concepts taught
--   * Filtering on a time window (BETWEEN ... AND ...)
--   * Aggregating before filtering: AVG() can NOT go in WHERE, so we compute
--     it first (in a CTE) and then apply HAVING / WHERE-on-the-aggregate
--   * A LEFT JOIN, to keep patients even when they have no telemetry -- see
--     the difference between INNER JOIN (B1) and LEFT JOIN here
--
-- Note: HAVING is how you filter a grouped aggregate directly; we use the
-- CTE + WHERE pattern to keep the logic readable and to make the report
-- columns available to the outer query.
--
-- The LEFT JOIN is the key learning this lesson: Marcus Lee (MRN-000002)
-- exists in the clinical store but has no vitals. An INNER JOIN would hide
-- him entirely; a LEFT JOIN keeps his row with a NULL vitals summary.
-- ============================================================================

WITH previous_hour AS (
    SELECT
        patient_id,
        ROUND(AVG(spo2_pct), 1) AS avg_spo2,
        COUNT(*)                AS readings
    FROM lake.lakehouse.vitals
    WHERE event_time BETWEEN
        TIMESTAMP '2026-01-01 03:00:00+00:00'
        AND TIMESTAMP '2026-01-01 03:59:59+00:00'
    GROUP BY patient_id
)
SELECT
    p.full_name,
    p.mrn,
    ph.avg_spo2,
    ph.readings,
    e.status
FROM mysql.clinical.patients p
LEFT JOIN mysql.clinical.encounters e
    ON e.patient_id = p.patient_id
LEFT JOIN previous_hour ph
    ON ph.patient_id = p.patient_id
ORDER BY ph.avg_spo2 ASC NULLS LAST