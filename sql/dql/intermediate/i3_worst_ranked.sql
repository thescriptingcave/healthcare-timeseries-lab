-- ============================================================================
-- Lesson I3 — "Where does every reading sit in its patient's distribution?"
--
-- Business question
--   Risk managers want to label EVERY SpO2 reading of the ward patients with
--   where it falls in that patient's OWN reading distribution: its worst-rank
--   (1 = the single lowest reading of the stay) and its decile.
--
-- Concepts taught
--   * RANK() vs ROW_NUMBER(): two equal readings get the SAME rank (think
--     of tied sports scores), row numbers never repeat
--   * NTILE(n): cut the patient's readings into n equal-sized buckets and
--     label each reading 1..n (1 = worst decile)
--   * The WHERE on window results is done OUTSIDE the window -- you cannot
--     filter ROW_NUMBER() or NTILE() inside their own SELECT -- so we wrap
--     the query in a CTE and filter there
--
-- Why this matters: a reading looks scary in raw numbers, but "this was in
-- Naomi's worst 2%" says something much stronger than "SpO2 was 89".
-- ============================================================================

WITH dist AS (
    SELECT
        p.full_name,
        v.spo2_pct,
        v.event_time,
        RANK() OVER (
            PARTITION BY v.patient_id
            ORDER BY v.spo2_pct ASC
        ) AS spo2_worst_rank,
        NTILE(10) OVER (
            PARTITION BY v.patient_id
            ORDER BY v.spo2_pct ASC
        ) AS spo2_decile
    FROM lake.lakehouse.vitals v
    JOIN mysql.clinical.patients p
        ON p.patient_id = v.patient_id
    WHERE v.patient_id IN (
        '55555555-5555-5555-5555-555555555555',
        '66666666-6666-6666-6666-666666666666',
        '77777777-7777-7777-7777-777777777777'
    )
)
SELECT
    full_name,
    ROUND(spo2_pct, 1) AS spo2,
    event_time,
    spo2_worst_rank,
    spo2_decile
FROM dist
WHERE spo2_worst_rank <= 3
ORDER BY full_name, spo2_worst_rank