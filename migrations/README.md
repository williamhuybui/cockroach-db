# Migrations

One `.sql` file per table. `scripts/migrate.py` runs every file in this folder
in filename order, so the number prefix controls that order.

```bash
python scripts/migrate.py
```

Every file uses `IF NOT EXISTS`, so running it again is safe and does nothing.

## Adding a new table

1. Create `NNN_<table_name>.sql`, numbering it **after** any table it
   references — foreign keys need their target to exist already.
2. Wrap everything in `IF NOT EXISTS` so re-running stays safe.
3. Note dependencies in a comment at the top of the file.
4. Run `python scripts/migrate.py`. It prints each file it applies and then
   lists the tables now in the database.

## Current order

| File | Creates | Depends on |
|---|---|---|
| `001_customers.sql` | `customers` | — |
| `002_calls.sql` | `calls`, plus the `call_id_sequence` that mints its `C001`-style key | `customers`, itself (`previous_call_id`) |
| `003_transcripts.sql` | `transcripts` | — (`call_id` is intentionally not an FK) |
| `004_tasks.sql` | `tasks` | `customers` |
| `005_tasks_completed_at.sql` | alters `tasks` — adds `completed_at` | `tasks` |
| `006_tasks_scheduling.sql` | alters `tasks` — adds `scheduled_at`, `calendar_event_id` | `tasks` |
| `007_customers_name_locked.sql` | alters `customers` — adds `name_is_manual` | `customers` |
| `008_tasks_appointment_fields.sql` | alters `tasks` — adds `is_appointment`, `suggested_datetime` | `tasks` |

Note that `001` and `004` declare their indexes **inline** inside
`CREATE TABLE`, so re-running them will never add an index to a table that
already exists. Add new indexes as standalone `CREATE INDEX IF NOT EXISTS`
statements in a new numbered file.

## Changing an existing table

These files only *create* tables — they won't alter one that already exists.
To change a live table, add a new numbered file with the `ALTER TABLE`
statement and update the `CREATE TABLE` above it to match, so a fresh database
and an existing one end up the same.
