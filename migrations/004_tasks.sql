-- Follow-up work for the business owner, generated from a call.
-- Depends on: customers.
CREATE TABLE IF NOT EXISTS tasks (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    call_id STRING NOT NULL,
    customer_id UUID NOT NULL,
    description STRING NOT NULL,
    status STRING NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT tasks_pkey PRIMARY KEY (id),
    CONSTRAINT tasks_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES customers(id),
    INDEX idx_tasks_status (status),
    INDEX idx_tasks_customer (customer_id)
);
