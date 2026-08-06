-- ================================================================
-- Call ID Sequence
-- ================================================================

-- Generate a unique number whenever a new live call begins.
--
-- transcripts.py converts the number into a readable call ID:
-- 1  -> C001
-- 16 -> C016
--
-- CockroachDB prevents duplicate sequence values when multiple calls
-- begin at the same time.
CREATE SEQUENCE IF NOT EXISTS call_id_sequence
START WITH 1;


-- ================================================================
-- Customers
-- ================================================================

-- Store one customer profile for each unique phone number.
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    phone_number STRING NOT NULL UNIQUE,
    full_name STRING NULL,
    address STRING NULL,
    email STRING NULL,

    created_at TIMESTAMPTZ
        NOT NULL
        DEFAULT now(),

    updated_at TIMESTAMPTZ
        NOT NULL
        DEFAULT now(),

    CONSTRAINT customers_phone_not_blank
        CHECK (
            length(trim(phone_number)) > 0
        )
);


-- ================================================================
-- Calls
-- ================================================================

-- Store one summarized record for each completed phone call.
--
-- The call_id is generated when transcript collection begins and
-- reused when the summarized call record is saved.
--
-- Examples:
-- C001
-- C002
-- C003
CREATE TABLE IF NOT EXISTS calls (
    call_id STRING PRIMARY KEY,

    customer_id UUID NULL
        REFERENCES customers(id)
        ON DELETE SET NULL,

    caller_number STRING NOT NULL,

    -- When the call began.
    "timestamp" TIMESTAMPTZ NOT NULL,

    -- Current lifecycle status of the call.
    status STRING
        NOT NULL
        DEFAULT 'completed',

    -- Contact information extracted from the completed transcript.
    name STRING NULL,
    email STRING NULL,
    address STRING NULL,

    -- Roofing request information extracted from the transcript.
    problem STRING NULL,
    problem_detail STRING NULL,
    availability STRING NULL,
    urgency STRING NULL,

    -- Link a follow-up call to an earlier summarized call.
    previous_call_id STRING NULL
        REFERENCES calls(call_id)
        ON DELETE SET NULL,

    -- Used when someone calls for another person.
    calling_on_behalf_of STRING NULL,

    -- Structured summary created from the completed transcript.
    summary STRING NULL,

    -- When the phone call ended.
    ended_at TIMESTAMPTZ NULL,

    -- When the summarized call record was saved to CockroachDB.
    saved_to_db_at TIMESTAMPTZ
        NOT NULL
        DEFAULT now(),

    CONSTRAINT calls_id_not_blank
        CHECK (
            length(trim(call_id)) > 0
        ),

    CONSTRAINT calls_caller_not_blank
        CHECK (
            length(trim(caller_number)) > 0
        ),

    CONSTRAINT calls_status_valid
        CHECK (
            status IN (
                'active',
                'completed',
                'failed',
                'disconnected'
            )
        ),

    CONSTRAINT calls_urgency_valid
        CHECK (
            urgency IS NULL
            OR urgency IN (
                'Low',
                'Medium',
                'High',
                'Emergency'
            )
        ),

    CONSTRAINT calls_previous_not_self
        CHECK (
            previous_call_id IS NULL
            OR previous_call_id != call_id
        ),

    CONSTRAINT calls_end_not_before_start
        CHECK (
            ended_at IS NULL
            OR ended_at >= "timestamp"
        )
);


-- Support customer call-history queries.
CREATE INDEX IF NOT EXISTS
    calls_caller_timestamp_idx
ON calls (
    caller_number,
    "timestamp" DESC
);


-- Support customer ID lookups.
CREATE INDEX IF NOT EXISTS
    calls_customer_id_idx
ON calls (
    customer_id
);


-- Support follow-up call lookups.
CREATE INDEX IF NOT EXISTS
    calls_previous_call_idx
ON calls (
    previous_call_id
);


-- ================================================================
-- Transcripts
-- ================================================================

-- Store each caller or assistant transcript turn as one row.
--
-- Transcript rows are saved before the summarized calls row exists.
-- Therefore, transcripts.call_id is intentionally not a foreign key.
CREATE TABLE IF NOT EXISTS transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Generated when the call begins and reused for every transcript
    -- turn throughout that call.
    call_id STRING NOT NULL,

    -- When the caller or assistant spoke.
    "timestamp" TIMESTAMPTZ NOT NULL,

    caller_number STRING NOT NULL,
    speaker STRING NOT NULL,
    text STRING NOT NULL,

    -- OpenAI text-embedding-3-small vector.
    embedding VECTOR(1536) NULL,

    -- When this transcript turn was saved to CockroachDB.
    saved_to_db_at TIMESTAMPTZ
        NOT NULL
        DEFAULT now(),

    CONSTRAINT transcripts_call_id_not_blank
        CHECK (
            length(trim(call_id)) > 0
        ),

    CONSTRAINT transcripts_caller_not_blank
        CHECK (
            length(trim(caller_number)) > 0
        ),

    CONSTRAINT transcripts_speaker_valid
        CHECK (
            speaker IN (
                'assistant',
                'caller'
            )
        ),

    CONSTRAINT transcripts_text_not_blank
        CHECK (
            length(trim(text)) > 0
        ),

    -- Prevent the same transcript turn from being saved twice.
    CONSTRAINT transcripts_identity_unique
        UNIQUE (
            call_id,
            "timestamp",
            speaker,
            text
        )
);


-- Support chronological transcript queries for one caller.
CREATE INDEX IF NOT EXISTS
    transcripts_caller_timestamp_idx
ON transcripts (
    caller_number,
    "timestamp"
);


-- Support retrieving the complete transcript for one call.
CREATE INDEX IF NOT EXISTS
    transcripts_call_timestamp_idx
ON transcripts (
    call_id,
    "timestamp"
);


-- Support semantic transcript searches using cosine distance.
CREATE VECTOR INDEX IF NOT EXISTS
    transcripts_embedding_idx
ON transcripts (
    embedding vector_cosine_ops
);