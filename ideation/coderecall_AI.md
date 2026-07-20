# CodeRecall AI — Token-Saving Memory for Developer Teams

*A shared AI memory layer for engineering teams that recalls previously solved problems, validated code fixes, and architecture decisions before ever calling an LLM — cutting token costs and keeping answers consistent.*

---

## The Problem

Development teams ask AI coding assistants the same or nearly the same questions over and over: how a webhook retry was implemented, why a service uses a particular timeout, how a flaky test was fixed, what the agreed pattern is for pagination. Each time, the assistant re-derives the answer from scratch, burning tokens and often producing a slightly different (sometimes worse) answer than the one the team already agreed on last month.

Knowledge that was hard-won in a debugging session, a design review, or a postmortem lives for a moment in a chat window and then evaporates. It is not written back into a place teammates — or their AI tools — can find it. When a developer leaves, or simply forgets, the team re-pays the cost of solving the same problem again.

This is a cost problem and a consistency problem at once: repeated LLM calls for previously-solved issues waste money, and independently-regenerated answers drift apart, so two engineers on the same team can end up with two different "correct" ways of doing the same thing.

Developers should not have to remember, search chat history, or re-explain context that the team has already solved.

---

## Who It Is For

Engineering teams and organizations using AI coding assistants as part of their daily workflow, especially:

- Teams with multiple developers or squads working in the same codebase(s)
- Teams paying for LLM API usage at scale (per-seat or per-token billing)
- On-call and support engineers who need fast, trusted answers under time pressure
- Teams onboarding new engineers who need access to prior decisions, not just documentation
- Organizations that want architecture decisions and code-fix rationale preserved beyond any one conversation

CodeRecall AI is not:

- A general-purpose coding assistant or code generator
- A replacement for version control, code review, or documentation systems
- An autonomous agent that ships code without human approval
- A static wiki or knowledge base that must be manually maintained
- A tool that guarantees correctness — it recalls what the team already validated, it does not independently verify code

---

## The Solution

1. **Ask naturally** — the developer poses a question or describes a problem, from chat, an IDE plugin, or a CLI.
2. **Recall before generating** — the agent embeds the query and searches shared team memory for similar previously-approved solutions, fixes, or decisions.
3. **Show what the team already knows** — if a sufficiently similar, still-valid match exists, the agent surfaces it first, with its confidence score, source, and last-validated date — before making any new LLM call.
4. **Developer judges the match** — accept as-is, adapt, or reject it.
5. **Escalate only when needed** — if there is no match, the match is rejected, marked outdated, or confidence is low, the agent performs a fresh AI search/generation.
6. **Improve the memory** — the new or corrected solution is reviewed by the developer and written back to shared memory, tagged and embedded for future retrieval.

```text
Developer asks a question
        ↓
Agent searches shared memory for similar solutions
        ↓
Match found and confident?
    ├── Yes → Show existing solution + confidence + source
    │              ↓
    │        Developer accepts / adapts / rejects
    │              ↓
    │        Accepted → done, token call avoided
    │              ↓
    │        Rejected/adapted → treated as new problem below
    │
    └── No / low confidence / outdated → Call LLM for a new solution
                   ↓
            Developer reviews and approves
                   ↓
            Solution saved back to shared memory
```

---

## Example

**Developer asks:**

> "How do we handle retries for our Stripe webhook handler? Getting duplicate charge events."

**CodeRecall AI proposes (from memory, before calling an LLM):**

- **Matched solution:** *Idempotent webhook retry pattern* (validated 6 weeks ago, `payments-service`)
- **Confidence:** 92% — same webhook provider, same duplicate-event symptom
- **Source:** Approved by @maria.k, linked to PR #482
- **Snippet:** Idempotency-key check against a `processed_events` table before handling the webhook body

```text
Match found in shared memory (confidence 92%)

Idempotent webhook retry pattern
Validated: 6 weeks ago · payments-service · PR #482

[Use this solution] [Ask AI for an updated version] [Not relevant]
```

If the developer selects **Use this solution**, no LLM call is made, and the snippet plus its rationale is inserted directly into their editor or chat. If they select **Ask AI for an updated version**, the agent calls the LLM with the old solution as context, then saves the refined result back to memory once approved.

---

## Product Workspace

```text
┌──────────────────────────────────────────────────────────────┐
│ CODERECALL AI                                                │
│ payments-service                               Team · ⚙      │
├──────────────────────────────────────────────────────────────┤
│ QUERY & RETRIEVAL                                             │
│ "How do we handle retries for our Stripe webhook handler?"   │
│ Match found · 92% confidence · saved ~1,800 tokens            │
│                    [Use solution] [Ask AI anyway] [Not this]  │
├──────────────────────────────────────────────────────────────┤
│ KNOWLEDGE TIMELINE                                            │
│                                                                │
│ 🚩 Mar 2      🚩 Apr 14       🚩 May 30      🚩 Jul 2       │
│ Retry pattern   Rate-limit fix  Schema change   Auth rewrite   │
│ adopted                                                        │
│                                                                │
│                         🚩 Jul 18                             │
│                    Pagination standard agreed                 │
├──────────────────────────────────────────────────────────────┤
│ RECENT SOLUTIONS                                              │
│                                                                │
│ Jul 19 · Idempotent webhook retry (reused)                ›   │
│ Jul 18 · Cursor-based pagination helper                   ›   │
│ Jul 15 · Flaky test: race condition in queue worker        ›   │
│ Jul 12 · Timeout value rationale for payment gateway        ›   │
│                                                                │
│                                             [View all]        │
├──────────────────────────────────────────────────────────────┤
│                         [💬 Ask a question] [Paste an error]  │
└──────────────────────────────────────────────────────────────┘
```

### 1. Query & Retrieval

This is the primary, always-visible output and should sit at the top of the page.

It displays:

- The developer's current question, verbatim
- Whether a matching solution was found in shared memory
- A confidence score for the match
- An estimated token/cost saving versus a fresh LLM call
- Actions: Use solution / Ask AI anyway / Not this

```text
QUERY & RETRIEVAL

"How do we handle retries for our Stripe webhook handler?"

Best match: Idempotent webhook retry pattern
Confidence: 92% · Last validated: 6 weeks ago
Estimated tokens saved: ~1,800 (this query)

[Use solution] [Ask AI for an updated version] [Not relevant]
```

If no match clears the confidence threshold, this panel instead shows:

```text
QUERY & RETRIEVAL

"How do we deduplicate events across two Kafka consumer groups?"

No confident match in shared memory (best match: 41%)

[Ask AI]
```

### 2. Knowledge Timeline

Its purpose is to answer:

> **What were the major decisions and turning points in this codebase's history?**

Suitable milestones include:

- A new architectural pattern adopted (e.g., idempotency keys, event sourcing)
- A significant bug fix that changed how a subsystem works
- A dependency or library migration
- A performance or security fix with broad impact
- A team-wide coding standard agreed upon
- A resolved incident/postmortem action item

Routine, one-off Q&A does not appear as a timeline flag — only changes that affect how the team builds going forward.

When the agent detects a possible milestone (e.g., three separate solved questions all reference the same new pattern), the developer decides how it should be recorded:

```text
Possible milestone

Cursor-based pagination adopted as team standard
Detected from: 3 related solved queries this week

[Add milestone] [Keep as regular solution] [Dismiss]
```

Selecting a milestone flag opens a details panel containing:

- Date and category
- Concise description of the decision
- Linked solutions/PRs that informed it
- Confirmation and edit history
- Whether it is surfaced when similar questions are asked
- Edit, remove, or deprecate actions

### 3. Recent Solutions

Recent Solutions contains the detailed, retrievable knowledge base entries. Each row is clickable.

```text
RECENT SOLUTIONS

Jul 19
Idempotent webhook retry pattern (reused, not regenerated)
Category: Bug fix · Repo: payments-service
Times reused: 4

Jul 18
Cursor-based pagination helper
Category: Code pattern · Repo: api-gateway
Related milestone: Pagination standard agreed

Jul 15
Flaky test: race condition in queue worker
Category: Test fix · Repo: order-service
Times reused: 1
```

Selecting a solution opens its details panel:

```text
Idempotent webhook retry pattern

Recorded:
Jul 19 (originally validated 6 weeks ago)

Original question:
"How do we handle retries for our Stripe webhook handler?
Getting duplicate charge events."

Approved solution:
Idempotency-key check against a processed_events
table before handling the webhook body.

Source: PR #482 · Approved by @maria.k
Confidence when last matched: 92%
Times reused: 4

[Edit] [Mark outdated] [Delete]
```

Recent Solutions answers:

> **What has the team already solved, and can I reuse it as-is?**

The knowledge timeline answers:

> **What changed about how we build things overall?**

### 4. Ask a Question / Paste an Error

Selecting **Ask a question** or **Paste an error** opens a capture panel.

```text
Ask CodeRecall AI

"Getting a duplicate charge event from our Stripe
webhook handler on retry. How have we handled this before?"

[Search memory]
```

CodeRecall AI then either surfaces a match or calls the LLM:

```text
Searching shared memory...

Found 1 strong match (92%) and 2 weaker matches (below threshold)

Best match: Idempotent webhook retry pattern
[Use solution] [Ask AI for an updated version] [Show weaker matches]
```

After the developer accepts, adapts, or generates a new solution:

- The solution is written into Recent Solutions.
- A recurring or high-impact solution may be proposed as a timeline milestone.
- The original question and any linked PR/commit stay attached to the entry.
- Reuse count and last-validated date update automatically.

The interaction should feel immediate:

```text
Ask
  ↓
Search memory
  ↓
Match shown (or LLM called if none)
  ↓
Developer accepts / adapts / rejects
  ↓
Memory updates, reuse count increments
  ↓
Milestone flag appears when a pattern recurs
```

### Temporary Panels

The workspace uses three overlays rather than separate navigation pages:

| Panel | Purpose |
|---|---|
| **Capture panel** | Question/error input, memory search, and LLM fallback |
| **Solution or milestone details panel** | Source entry, edit history, reuse stats, and inclusion in future matching |
| **Confidence review panel** | Compare the retrieved match against a freshly generated LLM answer side by side |

```text
                       CODERECALL AI HOME
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
     Ask a question    Select a solution     Review a milestone
          │                   │                   │
          ▼                   ▼                   ▼
    Capture panel       Details panel       Milestone panel
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
                     Same timeline workspace
```

## Agent Architecture

The developer sees one assistant, while three logical agents work behind it.

| Agent | Responsibility |
|---|---|
| **Recall Agent** | Embeds the incoming question, searches shared memory for similar validated solutions, and scores confidence |
| **Escalation Agent** | Calls the LLM only when no confident match exists, incorporating the closest prior solutions as context to keep answers consistent |
| **Memory Curation Agent** | Writes approved or corrected solutions back to memory, deduplicates near-identical entries, flags recurring patterns as milestones, and retires outdated entries |

```text
Developer
   │
   ▼
Recall Agent
   │
   ▼
Confident match? ──Yes──► Show solution ──► Accept/Adapt/Reject
   │No                                            │
   ▼                                               │
Escalation Agent (LLM call)                        │
   │                                               │
   ▼                                               ▼
Developer review/approval ──────────────► Memory Curation Agent
                                                    │
                                                    ▼
                                              CockroachDB
                                              ├── Solution library
                                              ├── Knowledge Timeline
                                              └── Reuse & confidence stats
```

The three logical agents may share the same underlying model with different prompts and tools.

---

## Persistent Memory Model

CockroachDB stores:

- Teams and repositories
- Developers (as attribution/source, not as gatekeepers of access)
- Questions and error text (original, verbatim)
- Approved solutions, fixes, and architecture decisions
- Links to source PRs, commits, and postmortems
- Confidence scores and match history
- Reuse counts and last-validated dates
- Deprecation/outdated flags
- Embeddings for semantic retrieval

Memory is essential because the agent must know:

- Whether a similar problem has already been solved
- Whether that solution is still considered valid
- How many times it has already been reused successfully
- What was rejected or superseded, and why
- Which recurring answers should be promoted to a team-wide standard

Without persistent memory, CodeRecall AI is only a one-time chatbot that re-derives every answer at full cost.

---

## Technology Mapping

| CockroachDB | AWS |
|---|---|
| Structured SQL memory for teams, repos, questions, solutions, and reuse history | Amazon Bedrock for embedding, retrieval-augmented generation, and fallback code generation |
| Distributed Vector Indexing for semantic search over prior questions and solutions | AWS Lambda for confidence scoring, approval logic, and database writes |
| Managed MCP Server or Agent Skills for controlled agent access to the solution library | API Gateway for the IDE plugin / chat backend |
| Transactional updates linking a source conversation or PR to a confirmed solution | Amazon CloudWatch for tracking token savings and reuse metrics over time |
| Persistent, cross-session record of validated team knowledge | Amazon S3 for optional exported knowledge-base snapshots |

The hackathon requires an agentic application using CockroachDB as the persistent memory layer on AWS and at least two designated CockroachDB tools.

---

## Safety Boundaries

CodeRecall AI may:

- Store developer-submitted questions, errors, and approved solutions
- Record architecture decisions and the rationale behind them
- Retrieve and rank prior solutions by similarity and confidence
- Estimate token/cost savings from reuse
- Flag a recurring solution as a possible team standard
- Call an LLM when memory has no confident answer

CodeRecall AI may not:

- Present a retrieved solution as correct without showing its confidence and source
- Auto-apply code changes without developer review
- Silently overwrite or delete a previously approved solution
- Treat an unreviewed LLM output as validated team knowledge
- Reuse a solution flagged as outdated without surfacing that warning
- Replace code review, testing, or security review

> **Memory proposes what the team already knows. The developer decides. CodeRecall AI remembers.**

---

### Compared with ChatGPT or Claude

General AI assistants can answer coding questions and even recall project context within a single conversation. CodeRecall AI provides a fixed, repeatable, team-wide workflow:

```text
Ask naturally
      ↓
Search shared team memory first
      ↓
Reuse a validated answer, or escalate to AI
      ↓
Developer approves
      ↓
Write back to shared memory
      ↓
Faster, cheaper, more consistent answers next time
```

Its advantage is not a better language model; it is a shared, persistent, validated memory that turns every solved problem into a team asset instead of a one-time answer.
