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

`src/` is a FastAPI app that answers a call over **Twilio Voice**, streams the caller's audio to **OpenAI's Realtime API**, and streams the AI's voice back — a live, two-way conversation. Memory and business data are backed by **CockroachDB**.

To run it locally, see [`GETTING_STARTED.md`](GETTING_STARTED.md). If something's not working, see [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).

## Repo layout

- `ideation/` — pitch docs for candidate hackathon ideas.
- `meeting/` — meeting notes and team roles (`meeting/role-responsibility.md`).
- `src/` — the FastAPI + Twilio + OpenAI Realtime backend.
