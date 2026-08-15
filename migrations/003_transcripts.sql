-- One row per spoken turn, written live during the call by src/main.py.
--
-- call_id is deliberately NOT a foreign key to calls: turns are saved while the
-- call is still in progress, before the calls row exists.
CREATE TABLE IF NOT EXISTS transcripts (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    call_id STRING NOT NULL,
    "timestamp" TIMESTAMPTZ NOT NULL,
    caller_number STRING NOT NULL,
    speaker STRING NOT NULL,
    text STRING NOT NULL,
    saved_to_db_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT transcripts_pkey PRIMARY KEY (id)
);

-- The dashboard groups turns by call and orders them by time.
CREATE INDEX IF NOT EXISTS idx_transcripts_call_id ON transcripts (call_id, "timestamp");
CREATE INDEX IF NOT EXISTS idx_transcripts_caller_number ON transcripts (caller_number, "timestamp");
