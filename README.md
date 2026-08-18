# The Front Desk That Never Sleeps

An AI phone agent with persistent memory, built for service businesses that can't staff their phones 24/7. When a homeowner's roof starts leaking, they call three roofers — whoever answers first usually wins the job. This agent answers every call, every time, and remembers every caller.

Built for the [CockroachDB × AWS Hackathon — Build with Agentic Memory](https://cockroachdb-ai.devpost.com/) (deadline Aug 18, 2026). Full pitch: [`ideation/the-front-desk-that-never-sleep.md`](ideation/the-front-desk-that-never-sleep.md).

## What it does

1. **Answers every call** — instantly, day or night, greeting the caller like a real front desk would.
2. **Asks smart questions** — clarifies what the caller needs using the business's own service and pricing data.
3. **Remembers the caller** — repeat callers get recognized, with full history, no re-explaining.
4. **Captures everything** — photos, addresses, and quotes sent during the call get stored and linked to the caller's record.
5. **Hands off cleanly** — the conversation is summarized and sent to the owner to follow up.

## How it works

`src/` is a FastAPI app that answers a call over **Twilio Voice**, streams the caller's audio to **OpenAI's Realtime API**, and streams the AI's voice back — a live, two-way conversation. Every spoken turn is written to the `transcripts` table in **CockroachDB** as the call happens, with a CSV copy in `call_logs/` as a backup.

A companion dashboard (`/dashboard`) reads those tables: it lists calls and clients, and per call lets you read/search the transcript, delete turns, add notes, review auto-detected action items, and manage caller-uploaded files.

To run it locally, see [`GETTING_STARTED.md`](GETTING_STARTED.md).

## Repo layout

- `src/` — the app.
  - `main.py` — Twilio webhook + WebSocket media-stream handler, writes transcripts live.
  - `dashboard.py` — `/api/*` endpoints and the `/dashboard` page.
  - `database.py` — CockroachDB access (`execute_sql`, `generate_call_id`, `save_transcript_turn`).
  - `config.py`, `greeting.py` — server settings, system prompt, greeting text.
  - `static/` — landing page (`/`) and dashboard frontend.
- `migrations/` — one `.sql` file per table; see [`migrations/README.md`](migrations/README.md) to add one.
- `scripts/` — `migrate.py` (create the tables), `query.py` (ad-hoc SQL as a DataFrame), `backfill_call_extraction.py` (run post-call extraction for calls that never got one).
- `mock_data/` — generators and CSV fixtures for the demo callers.
- `ideation/` — pitch docs for candidate hackathon ideas.
- `meeting/` — meeting notes and team roles.
- `call_logs/`, `uploads/`, `notes.json` — generated at runtime, gitignored.
