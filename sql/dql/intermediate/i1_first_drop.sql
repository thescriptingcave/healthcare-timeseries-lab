-- ============================================================================
-- Lesson I1 — "Find the moment Naomi started to deteriorate"
--
-- Business question
--   The quality team wants the exact reading where Naomi's desaturation
--   began: the first tick where SpO2 crossed BELOW 94% after being at or
--   above it. Report the reading before and the reading after.
--
-- Concepts taught
--   * LAG(value, 1) OVER (...) -- look at the PREVIOUS row in a window
--   * PARTITION BY patient_id + ORDER BY event_time -- the window definition
--   * A "state transition" read: previous >= threshold AND current <
--     threshold. This is how you find the START of an event in data without
--     an event table -- you will meet the same idea again in the advanced
--     lessons and turn it into episode boundaries.
--
-- Try: raise the threshold to 90 and watch the crossing move later, closer
-- to the deep plateau.
-- ============================================================================

WITH tagged AS (
    SELECT
        event_time,
        spo2_pct,
        LAG(spo2_pct, 1) OVER (
            PARTITION BY patient_id
            ORDER BY event_time
        ) AS previous_spo2
    FROM lake.lakehouse.vitals
    WHERE patient_id = '55555555-5555-5555-5555-555555555555'
)
SELECT
    event_time,
    ROUND(previous_spo2, 1) AS spo2_before,
    ROUND(spo2_pct, 1)      AS spo2_after
FROM tagged
WHERE previous_spo2 >= 94 AND spo2_pct < 94
ORDER BY event_time