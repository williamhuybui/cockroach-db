-- Replaces the old regex-derived APPOINTMENT_RULE classification (matched
-- against the task description after the fact) with fields the post-call
-- extraction LLM sets directly per to-do item (see post_call_extraction.py's
-- todo_items schema and routers/calls.py's create_tasks_for_call).
-- Depends on: tasks (004_tasks.sql).
--
-- Per migrations/README.md, 004_tasks.sql's CREATE TABLE was updated to
-- declare these columns too, so a fresh database and an existing one
-- converge.
--
-- is_appointment: true if the LLM judged this item to be about scheduling,
-- confirming, or rescheduling an in-person visit.
-- suggested_datetime: the specific date/time the LLM resolved from the
-- transcript, if the caller and agent settled on one. Pre-fills the
-- dashboard's Schedule sheet only — a human still has to click Save, which
-- writes the real scheduled_at (see dashboard.py's api_update_action_item).
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS is_appointment BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS suggested_datetime TIMESTAMPTZ NULL;
