-- One row per completed call, holding the summary extracted after it ends.
-- Depends on: customers.

-- call_id is a human-readable primary key (C001, C002, ...) handed out by this
-- sequence. src/database.py generate_call_id() reads it with nextval() at the
-- start of every call, so it must exist before any call is recorded.
CREATE SEQUENCE IF NOT EXISTS call_id_sequence
    MINVALUE 1
    INCREMENT 1
    START 1;

CREATE TABLE IF NOT EXISTS calls (
    call_id STRING NOT NULL,
    customer_id UUID NOT NULL,
    caller_number STRING NOT NULL,
    "timestamp" TIMESTAMPTZ NOT NULL,
    status STRING NOT NULL DEFAULT 'completed',

    -- contact details as given on this particular call
    name STRING NULL,
    email STRING NULL,
    address STRING NULL,

    -- what the caller needed
    problem STRING NULL,
    problem_detail STRING NULL,
    availability STRING NULL,
    urgency STRING NULL,
    summary STRING NULL,
    tags STRING[] NULL,

    -- set when this call follows up on an earlier one
    previous_call_id STRING NULL,
    calling_on_behalf_of STRING NULL,

    ended_at TIMESTAMPTZ NULL,
    saved_to_db_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT calls_pkey PRIMARY KEY (call_id),
    CONSTRAINT calls_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES customers(id),
    CONSTRAINT calls_previous_call_id_fkey FOREIGN KEY (previous_call_id) REFERENCES calls(call_id)
);

CREATE INDEX IF NOT EXISTS idx_calls_caller_number ON calls (caller_number, "timestamp" DESC);
