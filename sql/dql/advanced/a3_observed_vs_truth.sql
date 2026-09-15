-- ============================================================================
-- Lesson A3 — "Can we trust the monitor? Benchmark device readings
--              against the true trace"
--
-- Business question
--   The bedside monitor is a measurement instrument (Milestone 8): it adds
--   noise, rounds values, occasionally drops a reading. During one critical
--   stretch its SpO2 was 2 points lower than the true physiology. How big
--   is the observed-vs-truth error in practice, minute by minute?
--
-- Concepts taught
--   * WHY we also loaded a truth table: lake.lakehouse.vitals_truth holds
--     the exact simulated physiology for every tick, so fidelity can be
--     MEASURED (the same alignment idea as the Milestone 9 notebook)
--   * RESAMPLING to a coarser grain with date_trunc + median (the median
--     is robust to the occasional spike that a mean would drag around)
--   * A clean cross-catalog join: observed (vitals) and truth
--     (vitals_truth) meeting on their shared (minute, patient) buckets
--   * A final grouped aggregate computing MAE (mean absolute error)
--
-- We focus on Naomi -- the patient whose trace mattered most that night.
-- ============================================================================

WITH observed AS (
    SELECT
        date_trunc('minute', event_time) AS minute_bucket,
        approx_percentile(spo2_pct, 0.5) AS observed_spo2
    FROM lake.lakehouse.vitals
    WHERE patient_id = '55555555-5555-5555-5555-555555555555'
    GROUP BY 1
),
truth AS (
    SELECT
        date_trunc('minute', event_time) AS minute_bucket,
        approx_percentile(spo2_pct, 0.5) AS true_spo2
    FROM lake.lakehouse.vitals_truth
    WHERE patient_id = '55555555-5555-5555-5555-555555555555'
    GROUP BY 1
)
SELECT
    o.minute_bucket,
    o.observed_spo2,
    t.true_spo2,
    ROUND(o.observed_spo2 - t.true_spo2, 3) AS bias,
    ROUND(ABS(o.observed_spo2 - t.true_spo2), 3) AS abs_error
FROM observed o
JOIN truth t
    ON t.minute_bucket = o.minute_bucket
ORDER BY o.minute_bucket