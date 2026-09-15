-- ============================================================================
-- Lesson B2 — "Build the hourly handoff summary"
--
-- Business question
--   At shift change the oncoming nurse asks: "for every monitored patient,
--   what did each vital look like on average every hour?" The summary is the
--   handoff sheet: one row per patient per clock-hour.
--
-- Concepts taught
--   * Binning time with date_trunc('hour', timestamp) -- the bread and butter
--     of every time-series analysis
--   * GROUP BY patient + hour, with AVG() per vital
--   * ROUND() to keep the report readable
--   * A Common Table Expression (WITH hourly AS (...)) so the final SELECT is
--     a clean reading of an already-shaped table
--   * A second, cross-catalog JOIN now that the vitals live in a different
--     catalog (lake.lakehouse.vitals) than the demographics (mysql.clinical)
--
-- Read it top-down: WITH builds the "hourly" table, the main SELECT joins
-- it back to patient names and sorts it.
--
-- We filter to this milestone's three ward patients so the report stays on
-- one page; remove the WHERE to summarize the whole lakehouse.
-- ============================================================================

WITH hourly AS (
    SELECT
        patient_id,
        date_trunc('hour', event_time) AS hour_bucket,
        ROUND(AVG(heart_rate_bpm), 1)       AS avg_heart_rate,
        ROUND(AVG(spo2_pct), 1)             AS avg_spo2,
        ROUND(AVG(respiration_rate_bpm), 1) AS avg_respiration,
        ROUND(AVG(temperature_c), 2)        AS avg_temperature,
        COUNT(*)                            AS readings
    FROM lake.lakehouse.vitals
    WHERE patient_id IN (
        '55555555-5555-5555-5555-555555555555',
        '66666666-6666-6666-6666-666666666666',
        '77777777-7777-7777-7777-777777777777'
    )
    GROUP BY 1, 2
)
SELECT
    h.hour_bucket AS shift_hour,
    p.full_name,
    h.avg_heart_rate,
    h.avg_spo2,
    h.avg_respiration,
    h.avg_temperature,
    h.readings
FROM hourly h
JOIN mysql.clinical.patients p
    ON p.patient_id = h.patient_id
ORDER BY h.hour_bucket, p.full_name