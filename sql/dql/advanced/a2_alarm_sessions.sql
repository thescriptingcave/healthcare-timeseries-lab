-- ============================================================================
-- Lesson A2 — "Turn 900 alarm ticks into 4 alarm events (sessionization)"
--
-- Business question
--   A device alarm that fires below 90% SpO2 would ring nearly every 5
--   seconds while Naomi is desaturating -- useless for a tired clinician.
--   The alarm system should collapse a continuous burst into ONE event, and
--   start a NEW event only after 2 minutes of quiet. How many real alarms
--   actually fired, and what did each one cover?
--
-- Concepts taught
--   * Sessionization / event burst collapsing -- window functions at their
--     most business-valuable
--   * Filtering down to only the "alarm" readings first
--   * LAG() on the filtered stream to measure the gap to the previous alarm
--   * A running SUM() that seeds a new session whenever the gap resets
--     (>= 120 seconds of quiet), otherwise continues the current one
--
-- Read the WITH chain top to bottom: hits (alarm ticks) -> gaps (time since
-- the last alarm) -> sessions (a bucket id per contiguous burst).
-- ============================================================================

WITH hits AS (
    SELECT
        event_time,
        spo2_pct
    FROM lake.lakehouse.vitals
    WHERE patient_id = '55555555-5555-5555-5555-555555555555'
      AND spo2_pct < 90
),
gapped AS (
    SELECT
        event_time,
        spo2_pct,
        date_diff(
            'second',
            LAG(event_time, 1) OVER (ORDER BY event_time),
            event_time
        ) AS seconds_since_last_alarm
    FROM hits
),
sessions AS (
    SELECT
        event_time,
        spo2_pct,
        SUM(
            CASE WHEN seconds_since_last_alarm IS NULL
                  OR seconds_since_last_alarm >= 120
                 THEN 1 ELSE 0 END
        ) OVER (
            ORDER BY event_time
            ROWS UNBOUNDED PRECEDING
        ) AS alarm_session
    FROM gapped
)
SELECT
    MIN(event_time)     AS alarm_started,
    MAX(event_time)     AS alarm_ended,
    MIN(spo2_pct)       AS lowest_spo2,
    ROUND(AVG(spo2_pct), 1) AS avg_spo2,
    COUNT(*)            AS alert_readings
FROM sessions
GROUP BY alarm_session
ORDER BY alarm_started