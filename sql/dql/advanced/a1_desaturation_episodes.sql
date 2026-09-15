-- ============================================================================
-- Lesson A1 — "How many DISTINCT desaturation episodes did Naomi have?"
--
-- Business question
--   Naomi's SpO2 sat below 94% for the better part of an hour. But "below
--   94%" is not one single long event -- the trace dips, recovers, dips
--   again. The clinical reviewer wants each DISTINCT episode: when each one
--   started, when it ended, how long it lasted and how low it got.
--
-- Concepts taught
--   * The gap-and-islands pattern -- the single most useful time-series
--     technique in this whole course
--   * Step 1: turn each reading into a flag (low = 1 below threshold)
--   * Step 2: use LAG() to detect where the flag TRANSITIONS 0 -> 1
--   * Step 3: a running SUM() of those transitions gives every contiguous
--     icky stretch a shared bucket number (the "island")
--   * Step 4: GROUP BY the island and summarize
--
-- Try it yourself: replace 94 with 90 (a much deeper desaturation) and
-- watch the underlying episode split out -- and notice why it might still
-- fragment near the edges of the plateau.
-- ============================================================================

WITH flagged AS (
    SELECT
        patient_id,
        event_time,
        spo2_pct,
        CASE WHEN spo2_pct < 94 THEN 1 ELSE 0 END AS is_low,
        LAG(CASE WHEN spo2_pct < 94 THEN 1 ELSE 0 END, 1) OVER (
            PARTITION BY patient_id
            ORDER BY event_time
        ) AS previous_is_low
    FROM lake.lakehouse.vitals
    WHERE patient_id = '55555555-5555-5555-5555-555555555555'
),
islands AS (
    SELECT
        event_time,
        spo2_pct,
        is_low,
        SUM(
            CASE WHEN is_low = 1
                  AND (previous_is_low IS NULL OR previous_is_low = 0)
                 THEN 1 ELSE 0 END
        ) OVER (
            PARTITION BY patient_id
            ORDER BY event_time
            ROWS UNBOUNDED PRECEDING
        ) AS episode_id
    FROM flagged
)
SELECT
    MIN(event_time)                                    AS episode_start,
    MAX(event_time)                                    AS episode_end,
    date_diff('second', MIN(event_time), MAX(event_time))
                                                     AS duration_seconds,
    COUNT(*)                                          AS readings,
    ROUND(MIN(spo2_pct), 1)                           AS lowest_spo2,
    ROUND(AVG(spo2_pct), 1)                           AS avg_spo2
FROM islands
WHERE is_low = 1
GROUP BY episode_id
ORDER BY episode_start