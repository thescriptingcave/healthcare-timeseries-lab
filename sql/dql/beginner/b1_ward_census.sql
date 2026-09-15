-- ============================================================================
-- Lesson B1 — "Who was on the ward on January 1st?"
--
-- Business question
--   The charge nurse wants a list of every patient who was admitted to the
--   ward on 2026-01-01, with name, MRN, demographics and their admission /
--   discharge window.
--
-- Concept taught
--   * Reading a table (SELECT from mysql.clinical)
--   * INNER JOIN across two tables in the SAME catalog (patients <-> encounters)
--   * ORDER BY for a stable, readable result
--
-- Why INNER JOIN?
--   We only want rows that exist in BOTH tables. A patient row without a
--   matching encounter row disappears, and an encounter without a patient
--   row disappears too. (Lesson B3 demonstrates LEFT JOIN, which is what you
--   reach for when you want to KEEP the patient row anyway.)
--
-- The two MRN-0000xx patients were created in Milestone 5; the three
-- MRN-0001xx patients (Naomi, Cole, Ivy) are this milestone's ward.
-- ============================================================================

SELECT
    p.full_name,
    p.mrn,
    p.age,
    p.sex,
    p.admitted_at,
    e.ended_at,
    e.status
FROM mysql.clinical.patients p
JOIN mysql.clinical.encounters e
    ON e.patient_id = p.patient_id
ORDER BY p.admitted_at