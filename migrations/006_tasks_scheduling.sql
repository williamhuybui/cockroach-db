-- Adds real appointment scheduling to tasks, replacing the old UI-only
-- schedule-sheet stub (see src/static/dashboard.js). Depends on: tasks
-- (004_tasks.sql).
--
-- Per migrations/README.md, 004_tasks.sql's CREATE TABLE was updated to
-- declare these columns too, so a fresh database and an existing one
-- converge.
--
-- scheduled_at: the slot chosen from the dashboard's Schedule sheet, stored
-- as an absolute UTC instant (the dashboard converts from the company's
-- local time, config.COMPANY_TIMEZONE, before saving).
-- calendar_event_id: the Google Calendar event id created for this
-- appointment (src/calendar_service.py), so re-scheduling updates the same
-- event instead of creating a duplicate. NULL if calendar integration isn't
-- configured — scheduling still works without it.
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMPTZ NULL;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS calendar_event_id STRING NULL;
