# Front Desk That Never Sleeps — Progress Report

This document summarizes the work completed from the initial CockroachDB Cloud setup through the first successful live Twilio/OpenAI phone call with transcript persistence in CockroachDB.

## 1. Current status

### Completed

- Created a CockroachDB Cloud cluster via ccloud CLI to host the application database
- Created the `frontdesk` database with transcript, call, and customer tables
- Connected FastAPI to CockroachDB with a connection pool that opens at FastAPI startup and closes safely during shutdown
- Added OpenAI embeddings and enabled CockroachDB Distributed Vector Indexing on transcript embeddings for transcript semantic search
- Registered REST endpoints for CRUD, plus CSV uploads for health checks, transcripts, customers, and calls
- Ensured transcripts are stored before call summaries
- Created a shared `transcript_service.py` so REST requests and live Twilio calls use the same transcript-saving logic.
- Successfully completed a live phone conversation with the AI assistant that writes into CockroachDB
- Generated one call ID when the Twilio stream started and reused it for the complete phone call.


### Deferred

- Post-call summary and extraction AI agent.
- Automatic `POST /calls` after a live call ends.
- Automatic customer creation from the summarized call.
- Frontend, 3rd party tools integration.
- Production hosting on AWS Lightsail or another cloud platform.
- Production domain, Caddy, HTTPS termination, and systemd service.
- Production-grade active-call state management such as Redis.


## 2. Main technologies

- Python 3.11
- FastAPI
- Uvicorn
- Twilio Programmable Voice
- Twilio Media Streams
- ngrok
- OpenAI Realtime API
- OpenAI Embeddings API
- CockroachDB Cloud
- CockroachDB vector indexes
- psycopg 3
- psycopg-pool
- Pydantic
- pytest
- httpx
- Git Bash on Windows

## 3. Current project structure

```text
cockroach-db/
├── migrations/
│   ├── 000_enable_vector.sql
│   └── 001_initial_schema.sql
├── scripts/
│   └── migrate.py
├── src/
│   ├── api_models.py
│   ├── config.py
│   ├── database.py
│   ├── embedding_service.py
│   ├── greeting.py
│   ├── main.py
│   ├── mock_data/
│   │   ├── calls.csv
│   │   └── transcripts.csv
│   ├── routers/
│   │   ├── calls.py
│   │   ├── customers.py
│   │   ├── health.py
│   │   └── transcripts.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── transcript_service.py
│   └── tests/
│       └── test_mock_api_flow.py
├── .env
├── pytest.ini
├── requirements.txt
└── README.md
```

## 4. Database connection management

`src/database.py` creates one reusable asynchronous connection pool.

Main helpers:

```python
configure_database()
get_database_pool()
get_database_connection()
get_database_transaction()
```

The pool:

- is configured once,
- opens when FastAPI starts,
- reuses connections across requests and live transcript writes,
- commits successful transactions,
- rolls back failed transactions,
- closes during application shutdown.

## 5. Embedding service

`src/embedding_service.py` manages one shared OpenAI client.

Main functions:

```python
configure_embedding_client()
create_embedding()
create_embeddings()
to_vector_literal()
close_embedding_client()
```

Each transcript turn is converted into a 1,536-number vector using the configured embedding model. The vector is stored in:

```sql
transcripts.embedding VECTOR(1536)
```

The embedding is intentionally omitted from normal transcript API responses because it is machine-readable search data, not human-readable content.

## 11. Shared transcript service

`src/services/transcript_service.py` contains the reusable transcript creation logic.

Main functions:

```python
generate_call_id()
create_transcript_turn()
```

`generate_call_id()`:

- obtains the next CockroachDB sequence value,
- formats the value as `C001`, `C002`, and so on.

`create_transcript_turn()`:

- accepts an existing `call_id` or creates one when missing,
- cleans transcript text,
- creates the OpenAI embedding,
- converts the embedding into CockroachDB vector format,
- inserts the transcript row,
- returns the saved record.

## 6. Database schema

The schema creates:

```text
call_id_sequence
customers
calls
transcripts
```

### Transcript columns

```text
id
call_id
timestamp
caller_number
speaker
text
embedding
saved_to_db_at
```

Important constraints:

- `call_id` cannot be blank.
- `caller_number` cannot be blank.
- `speaker` must be `caller` or `assistant`.
- `text` cannot be blank.
- duplicate transcript turns are blocked by the combined identity constraint.

### Call columns

```text
call_id
customer_id
caller_number
timestamp
status
name
email
address
problem
problem_detail
availability
urgency
previous_call_id
calling_on_behalf_of
summary
ended_at
saved_to_db_at
```

### Customer columns

```text
id
phone_number
full_name
address
email
created_at
updated_at
```

## 7. Migrations

Run from the repository root:

```bash
source venv/Scripts/activate
python -m scripts.migrate
```

Expected migration output includes:

```text
CockroachDB vector support enabled.
CockroachDB schema created successfully.
Sequence found: call_id_sequence
Tables found: calls, customers, transcripts
All CockroachDB migrations completed successfully.
```

## 8. REST API status

### Health

```text
GET /health
```

### Transcripts

```text
POST   /transcripts
POST   /transcripts/semantic-search
GET    /transcripts
GET    /transcripts/{transcript_id}
PATCH  /transcripts/{transcript_id}
DELETE /transcripts/{transcript_id}
```

`POST /transcripts` and the live Twilio WebSocket now use the same transcript service.

### Calls

```text
POST   /calls
GET    /calls
GET    /calls/{call_id}
PATCH  /calls/{call_id}
DELETE /calls/{call_id}
```

`POST /calls` currently expects structured data supplied by a client or future summary agent.

### Customers

```text
POST   /customers
GET    /customers
GET    /customers/by-phone/{phone_number}
GET    /customers/{customer_id}
PATCH  /customers/{customer_id}
DELETE /customers/{customer_id}
```

## 9. Live call result

The live call successfully produced server logs for both speakers and then persisted the completed turns to CockroachDB.

Example conversation behavior:

```text
caller: The lightning just broke my roof. What should I do?
assistant: Make sure everyone is safe and contact emergency services if there is fire or immediate danger.
caller: Okay. Thank you. Have a good day.
assistant: You’re very welcome. Take care.
```

The final persistence flow is:

```text
OpenAI completed transcript event
        ↓
save_conversation_turn()
        ↓
create_transcript_turn()
        ↓
create_embedding()
        ↓
INSERT INTO transcripts
        ↓
transaction commit
```

## 10. CockroachDB verification

Use this query after a live call:

```sql
SELECT
    call_id,
    "timestamp",
    caller_number,
    speaker,
    text,
    embedding IS NOT NULL AS has_embedding,
    saved_to_db_at
FROM transcripts
ORDER BY saved_to_db_at DESC;
```

Expected result:

- multiple rows from the live call,
- one shared `call_id`,
- correct caller phone number,
- caller and assistant speaker labels,
- readable text,
- `has_embedding = true`,
- generated `saved_to_db_at` values.

Group validation:

```sql
SELECT
    call_id,
    count(*) AS transcript_turns,
    count(DISTINCT caller_number) AS phone_numbers
FROM transcripts
GROUP BY call_id
ORDER BY call_id;
```

One live phone call should have multiple transcript turns and one phone number.

## 10. Testing status

### Automated production-API test

Current test file:

```text
src/tests/test_mock_api_flow.py
```

Its current purpose is to:

```text
Read mock transcript data
        ↓
POST transcript turns through the production API
        ↓
Receive generated call IDs
        ↓
Retrieve saved transcripts
        ↓
Confirm transcript data was preserved
```

The completed-call portion should remain separate until the summary and extraction agent exists.

Run:

```bash
python -m pytest src/tests/test_mock_api_flow.py -v -s
```
