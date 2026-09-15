-- ============================================================================
-- Lesson I2 — "Is that reading a real desaturation, or device noise?"
--
-- Business question
--   A spikey reading at 03:15 looks alarming, but the bed is on a monitor
--   with known measurement noise (Milestone 8). We want to compare the RAW
--   reading against a SMOOTHED reading (a centered 7-reading moving average,
--   i.e. roughly +/- 15 seconds at a 5-second cadence) to tell transient
--   spikes apart from sustained trends.
--
-- Concepts taught
--   * Moving-average window: AVG() OVER (PARTITION BY ...
--     ORDER BY ... ROWS BETWEEN n PRECEDING AND n FOLLOWING)
--   * The idea that smoothing trades away sharpness for stability -- in the
--     chart you will SEE spikes appear and vanish in the smoothed line
--   * A paired comparison: for each reading, how far it is from its window
--
-- We compare Naomi (the desaturating patient) against Ivy (the stable
-- control) -- same device profile, very different physiology.
-- ============================================================================

WITH smoothed AS (
    SELECT
        v.event_time,
        p.full_name,
        v.spo2_pct,
        ROUND(AVG(v.spo2_pct) OVER (
            PARTITION BY v.patient_id
            ORDER BY v.event_time
            ROWS BETWEEN 3 PRECEDING AND 3 FOLLOWING
        ), 2) AS spo2_ma
    FROM lake.lakehouse.vitals v
    JOIN mysql.clinical.patients p
        ON p.patient_id = v.patient_id
    WHERE v.patient_id IN (
        '55555555-5555-5555-5555-555555555555',
        '77777777-7777-7777-7777-777777777777'
    )
)
SELECT
    event_time,
    full_name,
    ROUND(spo2_pct, 1) AS raw_spo2,
    spo2_ma,
    ROUND(spo2_pct - spo2_ma, 2) AS deviation_from_average
FROM smoothed
ORDER BY event_time, full_name