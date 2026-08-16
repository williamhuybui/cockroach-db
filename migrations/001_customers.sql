-- One row per person who has called. Looked up by phone number.
CREATE TABLE IF NOT EXISTS customers (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    phone_number STRING NOT NULL,
    full_name STRING NULL,
    address STRING NULL,
    email STRING NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- True once a human sets/corrects the name from the dashboard, so a
    -- later extraction rerun never overwrites it with the transcript's
    -- version. Added live by 007_customers_name_locked.sql; declared here
    -- too so a fresh database matches an existing one (see
    -- migrations/README.md).
    name_is_manual BOOLEAN NOT NULL DEFAULT false,

    CONSTRAINT customers_pkey PRIMARY KEY (id),
    UNIQUE INDEX customers_phone_number_key (phone_number)
);
