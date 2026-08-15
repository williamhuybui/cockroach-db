-- One row per person who has called. Looked up by phone number.
CREATE TABLE IF NOT EXISTS customers (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    phone_number STRING NOT NULL,
    full_name STRING NULL,
    address STRING NULL,
    email STRING NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT customers_pkey PRIMARY KEY (id),
    UNIQUE INDEX customers_phone_number_key (phone_number)
);
