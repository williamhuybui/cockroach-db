# The Front Desk That Never Sleeps

*An AI phone agent with persistent memory, built for service businesses that can't staff their phones 24/7.*

---

## Inspiration

A homeowner's roof starts leaking. They search, find three local roofers, and call all three. Two go to voicemail. One picks up — and wins the job, often just because they answered first, not because they were the best.

This happens constantly, and it's expensive for small service businesses:

- **62%** of small business calls go unanswered
- **85%** of missed callers never call back — they just call the next contractor
- A small roofing contractor loses an estimated **$45K–$120K a year** to missed calls alone
- These businesses are already paying **$79–$228 per lead** in marketing — they're winning the click and losing the job on the very next step: the phone

We talked directly with a roofing business owner about this problem, which is what pushed us toward roofing as our pilot industry — speed-to-lead is everything in home services, and the first contractor to respond wins **70–80%** of jobs. We wanted to build something that closes that gap: an agent that never misses a call and never forgets a caller.

## What It Does

The Front Desk That Never Sleeps answers every call to a roofing business, 24/7, and behaves like a real front-desk employee who remembers everyone who's ever called in:

1. **Answers instantly** — day or night, no hold music, no voicemail.
2. **Has a real conversation** — asks about the roofing problem, timeline, and severity, and stays on-topic (politely redirects unrelated questions and declines out-of-scope services like plumbing).
3. **Recognizes returning callers** — looks the caller up by phone number and recalls their name, address, and prior conversations instead of starting over.
4. **Flags emergencies** — detects urgent situations (active leaks, storm damage, structural risk) and prioritizes them.
5. **Captures everything** — name, address, email, problem details, availability, and (in future work) photos/files the caller sends.
6. **Hands off cleanly** — sends a follow-up SMS summarizing the call and creates action items (call back, schedule a visit) for the business owner.
7. **Gives the owner a command center** — a dashboard listing every call and client, with searchable transcripts, auto-detected to-dos, notes, and uploaded files per caller.

## How We Built It

- **Telephony & voice**: Twilio Programmable Voice + Media Streams route each call into our FastAPI backend over a WebSocket.
- **Conversation intelligence**: OpenAI's Realtime API (`gpt-realtime`) handles live, two-way audio conversation with mid-call interruption support, so the caller can talk over the agent naturally.
- **Persistent memory**: CockroachDB Cloud stores every customer, call, and transcript turn. Transcript text is embedded (OpenAI `text-embedding-3-small`, 1536 dimensions) and indexed with CockroachDB's **Distributed Vector Indexing** for semantic transcript search.
- **Backend**: Python + FastAPI, with a shared `transcript_service` module so both the live call path and our REST API save transcripts through identical logic — one call_id (generated from a CockroachDB sequence) ties every turn of a conversation together.
- **Dashboard**: a lightweight HTML/CSS/JS "Command Center" for the business owner — a calls table with filters and stats, a per-call drawer (transcript, to-dos, notes, search, files), and a client-level view of everyone who's ever called.
- **Messaging**: Twilio SMS for the post-call follow-up text (in progress — Brand Registration underway).

We split ownership across the team by focus area (frontend, backend, infra/deployment, research, presentation) with clear driver/passenger roles, and ran a weekly knowledge-sharing check-in to keep everyone synced.

## Architecture at a Glance

```
Caller
  │  (phone call)
  ▼
Twilio Voice ──webhook──► FastAPI /incoming-call
  │  (Media Stream, WebSocket)
  ▼
FastAPI /media-stream  ◄──────────────►  OpenAI Realtime API (gpt-realtime)
  │  (each completed turn)
  ▼
transcript_service.py
  │  ├─ generate_call_id()   → CockroachDB sequence
  │  └─ create_transcript_turn()
  ▼
CockroachDB Cloud
  ├─ transcripts  (per turn, + vector embedding for semantic search)
  ├─ calls        (per conversation: name, address, problem, urgency, summary)
  └─ customers    (per phone number: recognized across every future call)
  ▲
  │  REST API (FastAPI routers: /transcripts /calls /customers /health)
  ▼
Command Center Dashboard (HTML/CSS/JS)
  → Calls view, Clients view, per-call transcript/to-do/notes/files
  → Post-call SMS via Twilio (in progress)
```

Two CockroachDB capabilities anchor the "agentic memory" story: **Distributed Vector Indexing** for semantic search over past conversations, and the structured `customers`/`calls`/`transcripts` schema that lets the agent recognize a caller and recall context the instant they call back — with the AWS Bedrock/Lambda/S3/Connect layer planned for production hosting.

## Challenges We Faced

- **Keeping the agent on-topic**: getting the system prompt to stay strictly scoped to roofing/restoration — declining plumbing requests, redirecting small talk, but still sounding warm — took real iteration and live-call testing.
- **Ending calls gracefully**: designing a way for the agent to track token usage and proactively wrap up a conversation as it approached a limit, rather than being cut off mid-sentence.
- **Schema design under real constraints**: transcripts have to be saved *before* a call summary exists (since the summary is generated only after the call ends), so `transcripts.call_id` is intentionally not a foreign key to `calls` — a small but important design decision to avoid dropping live data.
- **Live audio interruption handling**: making the agent stop speaking cleanly when a caller talks over it, without losing or duplicating audio.
- **Voice/language/memory consistency**: early bugs with inconsistent voice selection and background noise interference during live calls.
- **Coordinating a distributed team**: syncing infra, backend, and frontend work (CockroachDB connection, mock data, dashboard, SMS) that all depended on each other, across people's different schedules.
- **Twilio SMS Brand Registration**: a real-world compliance step that turned out to be a bottleneck for shipping the post-call follow-up text.

## What We Learned

- How to design a schema around *when* data actually becomes available in a live system (transcripts arrive turn-by-turn; structured summaries only exist after the call ends) rather than assuming a clean, all-at-once write.
- How CockroachDB's Distributed Vector Indexing fits into a real agentic memory pipeline — not just storing conversation history, but making it semantically searchable.
- How much guardrail and prompt-engineering work goes into making a voice agent behave reliably in a live call versus a text chat.
- The value of a shared "driver/passenger" ownership model for splitting fast-moving, interdependent work across a small team on a tight hackathon timeline.

## Built With

`python` · `fastapi` · `cockroachdb` · `cockroachdb-distributed-vector-indexing` · `twilio` · `twilio-programmable-voice` · `twilio-media-streams` · `openai-realtime-api` · `openai-embeddings` · `psycopg` · `pydantic` · `javascript` · `html` · `css` · `ngrok` · `pytest` · `aws` *(planned: amazon-bedrock, aws-lambda, amazon-s3, amazon-connect)*

## Try It Out

- **GitHub repo**: [link]
- **Live demo / test number**: [Twilio number or hosted link — pending deployment]
- **Dashboard**: [link, once deployed]

*(Placeholders above — fill in once AWS deployment and the public repo link are finalized.)*
