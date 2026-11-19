-- 002: remember when each application last changed stage, in the applications row itself.
-- Until now this was computed on every read with MAX(entered_at) over stage_history.
-- This migration changes a table that already holds data, so existing rows are backfilled
-- from their own history and keep their timeline. Never edit this file once applied.

-- 1. Add the column. It must allow NULL for now: the existing rows have no value yet.
ALTER TABLE applications ADD last_stage_change DATETIME2(0) NULL;
GO
-- 2. Backfill: the newest stage_history row of each application.
--    Every application gets an 'applied' history row when it is created, so MAX is never
--    NULL in practice; COALESCE with date_applied is only a safety net for step 3.
--    (A separate batch, because SQL Server can't use a column in the batch that adds it.)
UPDATE a
   SET last_stage_change = COALESCE(
           (SELECT MAX(h.entered_at) FROM stage_history h WHERE h.application_id = a.id),
           CAST(a.date_applied AS DATETIME2(0)))
  FROM applications a;
GO
-- 3. Every row has a value now, so new rows must always have one too.
ALTER TABLE applications ALTER COLUMN last_stage_change DATETIME2(0) NOT NULL;
