# Architecture

OpenLine AI processes each call in two phases.

## 1. Live call

Twilio and OpenAI Realtime are bridged for the duration of the call: caller audio streams to OpenAI, generated audio streams back to Twilio, and each completed caller or assistant transcript turn is saved to CockroachDB and broadcast to the dashboard.

When the phone number matches an existing customer, FastAPI retrieves the customer's profile, most recent call, and open tasks from CockroachDB. That context is injected into the OpenAI Realtime session with instructions to confirm known information instead of collecting it again.

## 2. Post-call extraction

After disconnect, the completed transcript is sent to Groq for structured extraction. The result contains customer details, service problem, urgency, summary, tags, and follow-up tasks. FastAPI validates the result and writes it to the `customers`, `calls`, and `tasks` tables.

The operations dashboard displays live calls and completed records. Staff can review transcripts, manage customers and tasks, rerun extraction, and optionally create Google Calendar appointments.

## Runtime components

- **Twilio Voice:** incoming-call webhook and bidirectional media stream.
- **Caddy:** TLS termination and HTTPS/WSS reverse proxy.
- **FastAPI + Uvicorn:** voice bridge, caller context, APIs, extraction orchestration, and dashboard.
- **OpenAI Realtime:** live speech-to-speech conversation and transcription events.
- **Groq:** post-call structured-data extraction.
- **CockroachDB:** persistent customers, calls, transcripts, and tasks.
- **Google Calendar:** optional appointment synchronization.
- **Amazon Lightsail:** production host for Caddy, FastAPI, and the dashboard.

The high-level numbered flow is shown in [`docs/architecture.png`](docs/architecture.png).
