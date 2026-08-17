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
    -- Set when the item is closed from the dashboard, nulled if reopened.
    -- Added live by 005_tasks_completed_at.sql; declared here too so a fresh
    -- database matches an existing one (see migrations/README.md).
    completed_at TIMESTAMPTZ NULL,
    -- Appointment slot chosen from the dashboard's Schedule sheet, and the id
    -- of the Google Calendar event it created (NULL if calendar integration
    -- isn't configured, see src/calendar_service.py). Added live by
    -- 006_tasks_scheduling.sql; declared here too for the same reason as
    -- completed_at above.
    scheduled_at TIMESTAMPTZ NULL,
    calendar_event_id STRING NULL,
    -- The extraction LLM's own judgment of whether this item is about
    -- scheduling a visit, and the date/time it resolved if one was settled
    -- on — no keyword/regex classification after the fact. Added live by
    -- 008_tasks_appointment_fields.sql; declared here too for the same
    -- reason as completed_at above.
    is_appointment BOOLEAN NOT NULL DEFAULT false,
    suggested_datetime TIMESTAMPTZ NULL,

    CONSTRAINT tasks_pkey PRIMARY KEY (id),
    CONSTRAINT tasks_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES customers(id),
    INDEX idx_tasks_status (status),
    INDEX idx_tasks_customer (customer_id)
);
