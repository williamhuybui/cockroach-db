# CareMemo — The Doctor Visit Summary That Builds Itself

*An AI voice agent with persistent memory that helps family caregivers capture important changes as they happen and arrive at medical appointments prepared.*

---

## The Problem

Family caregivers notice important changes between medical appointments—falls, sleep disruption, behavior changes, progress, clinician-directed medication changes, and questions for the doctor—but those details are often scattered across memory, messages, calendars, and paper notes.

By the next appointment, the caregiver must reconstruct what happened, when it happened, and what should be discussed. This affects a large population: AARP and the National Alliance for Caregiving reported that 63 million Americans were family caregivers in 2025.

Caregivers already perform the difficult work of observing and supporting a loved one. They should not also have to become medical note-takers.

---

## Who It Is For

Primary family caregivers supporting a parent, spouse, or loved one with recurring medical appointments related to:

- Dementia or Alzheimer’s disease
- Parkinson’s disease
- Stroke recovery
- Cancer treatment
- Surgery or injury recovery
- Mobility decline
- Other long-term conditions

CareMemo is not:

- An electronic health record
- A social network
- A professional home-care platform
- A diagnosis or treatment tool
- A medication recommendation system

---

## The Solution

1. **Speak naturally** — the caregiver records a short voice or text update.
2. **Capture what matters** — AI extracts visit-relevant observations, incidents, appointments, clinician-reported medication changes, progress, and questions.
3. **Confirm the details** — the caregiver approves, edits, or dismisses each item.
4. **See the major turning points** — confirmed milestones appear as flags on a simple care-journey visualizer, while detailed observations remain in Recent Updates.
5. **Arrive prepared** — the Next Visit Summary section uses confirmed milestones, recent updates, medication facts, and saved questions to generate a concise one-page PDF.

> **Talk between visits. Arrive prepared.**

```text
Caregiver speaks
        ↓
AI extracts important updates
        ↓
Caregiver confirms
        ↓
Timeline updates
        ↓
Appointment approaches
        ↓
CareMemo generates the visit summary
```

---

## Example

**Caregiver says:**

> “Mom fell yesterday, but she said nothing hurt. She has also been waking up around 2 AM this week. Her neurologist appointment is next Tuesday, and I want to remember to mention the sleep changes.”

**CareMemo proposes:**

- **Incident:** Fall yesterday; no injury reported
- **Observation:** Waking around 2 AM this week
- **Appointment:** Neurology visit next Tuesday
- **Question:** Mention recent sleep changes

The caregiver selects **Approve**, **Edit**, or **Dismiss**.

The confirmed items are saved to Recent Updates. Only major turning points—such as a significant fall, hospitalization, therapy completion, clinician-directed medication change, or major functional milestone—are proposed as timeline flags. Relevant confirmed items can be included in the next-visit summary.

---

## Product Workspace

```text
┌──────────────────────────────────────────────────────────────┐
│ CAREMEMO                                                     │
│ Mom’s Care                                     Profile · ⚙   │
├──────────────────────────────────────────────────────────────┤
│ NEXT VISIT SUMMARY                                           │
│ Neurologist · August 12 · 2:00 PM                            │
│ 5 confirmed updates · 2 questions saved                      │
│                             [Preview Summary] [Export PDF]    │
├──────────────────────────────────────────────────────────────┤
│ CARE JOURNEY                                                 │
│                                                              │
│ 🚩 May 10      🚩 June 4       🚩 July 2       🚩 Aug. 12  │
│ Last visit       Fall           PT completed     Next visit   │
│                                                              │
│                         🚩 July 18                            │
│                    Mobility milestone                        │
├──────────────────────────────────────────────────────────────┤
│ RECENT UPDATES                                               │
│                                                              │
│ July 19 · Night waking increased                         ›   │
│ July 18 · Walked to porch with walker                    ›   │
│ July 15 · Appetite improved                              ›   │
│ July 12 · Question saved for neurologist                 ›   │
│                                                              │
│                                             [View all]        │
├──────────────────────────────────────────────────────────────┤
│                         [🎤 Voice update] [Type update]       │
└──────────────────────────────────────────────────────────────┘
```

### 1. Next Visit Summary

This section is the practical output and should appear near the top of the page.

It displays:

- Provider and appointment date
- Number of confirmed updates since the last visit
- Number of saved questions
- Preview Summary button
- Export PDF button

```text
NEXT VISIT SUMMARY

Neurologist
August 12 at 2:00 PM

Since the last visit
• 5 confirmed updates
• 1 major incident
• 2 positive changes
• 2 questions saved

[Preview Summary] [Export PDF]
```

The one-page PDF should contain:

1. Care-recipient and caregiver information
2. Major changes since the previous visit
3. Relevant recent observations
4. Caregiver-entered medication facts and clinician-directed changes
5. Saved questions for the provider
6. Compact milestone list

### 2. Care Journey

Its purpose is to answer:

> **What were the major turning points in the care journey?**

Suitable milestones include:

- Diagnosis
- Hospital admission or discharge
- Significant fall or incident
- Therapy started or completed
- Clinician-directed medication start or change
- Major behavioral or functional change
- Important family care decision
- Meaningful goal achieved
- Previous and upcoming major medical visits

Routine observations do not appear as flags.

When the AI detects a possible milestone, the caregiver decides how it should be saved:

```text
Possible milestone

Physical therapy completed
Date: July 2

[Add milestone] [Keep as regular update] [Dismiss]
```

Selecting a milestone flag opens a details panel containing:

- Date and category
- Concise description
- Original caregiver entry
- Confirmation and edit history
- Whether it is included in the next-visit summary
- Edit, remove, or exclude actions

### 3. Recent Updates

Recent Updates contains the detailed information. Each row is clickable.

```text
RECENT UPDATES

July 19
Night waking around 2 AM
Category: Sleep observation
Included in next summary: Yes

July 18
Walked to porch using walker
Category: Positive progress
Related milestone: Mobility improvement

July 15
Appetite improved
Category: Observation
Included in next summary: Yes
```

Selecting an update opens its details panel:

```text
Night waking around 2 AM

Recorded:
July 19

Original caregiver entry:
“Mom woke up around 2 again last night.
That is the third time this week.”

Extracted information:
• Night waking
• Three occurrences this week

Upcoming visit summary:
Included

[Edit] [Exclude from summary] [Delete]
```

Recent Updates answers:

> **What has happened lately?**

The milestone visualizer answers:

> **What changed the overall journey?**

### 4. Voice and Text Capture

Selecting **Voice update** or **Type update** opens a capture panel.

```text
Add an update

“Mom fell yesterday, but she said she was not hurt.
She also slept poorly.”

[Stop and review]
```

CareMemo then proposes structured items:

```text
I found two possible updates:

Fall yesterday
No injury reported
[Approve] [Edit] [Dismiss]

Poor sleep
Date: This week
[Approve] [Edit] [Dismiss]
```

After approval:

- All confirmed items appear in Recent Updates.
- A major event may be proposed as a milestone flag.
- Relevant information is added to the upcoming visit summary.
- The original transcript remains linked to every extracted item.

The interaction should feel immediate:

```text
Speak
  ↓
Review
  ↓
Confirm
  ↓
Recent Updates refresh
  ↓
Major milestone flag appears when applicable
  ↓
Next Visit Summary updates
```

### Temporary Panels

The one-page workspace uses three overlays rather than separate navigation pages:

| Panel | Purpose |
|---|---|
| **Capture panel** | Voice/text input, extraction, clarification, and confirmation |
| **Update or milestone details panel** | Source entry, edits, category, and summary inclusion |
| **Summary preview panel** | Review the one-page next-visit summary and export it to PDF |

```text
                         CAREMEMO HOME
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
     Add update         Select an item      Prepare summary
          │                   │                   │
          ▼                   ▼                   ▼
    Capture panel       Details panel       Preview panel
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
                     Same timeline workspace
```

## Agent Architecture

The caregiver sees one assistant, while three logical agents work behind it.

| Agent | Responsibility |
|---|---|
| **Care Capture Agent** | Converts natural voice or text into proposed structured updates |
| **Longitudinal Memory Agent** | Stores confirmed events, links them to visits, and maintains the timeline |
| **Visit Summary Agent** | Retrieves relevant changes since the last visit and generates the one-page summary |

```text
Caregiver
   │
   ▼
Care Capture Agent
   │
   ▼
Approve / Edit / Dismiss
   │
   ▼
Longitudinal Memory Agent
   │
   ▼
CockroachDB
   ├── Visual Timeline
   └── Visit Summary Agent
            │
            ▼
       One-page PDF
```

The three logical agents may use the same underlying model with different prompts and tools.

---

## Persistent Memory Model

CockroachDB stores:

- Caregivers
- Care recipients
- Conversations
- Structured observations
- Incidents
- Appointments
- Medication records
- Provider questions
- Confirmation and edit history
- Generated visit summaries
- Embeddings for semantic retrieval

Memory is essential because the agent must know:

- What happened since the previous visit
- What the caregiver confirmed
- What was corrected or dismissed
- What was already included in an earlier summary
- Which questions remain open

Without persistent memory, CareMemo is only a one-time summarizer.

---

## Technology Mapping

| CockroachDB | AWS |
|---|---|
| Structured SQL memory for caregivers, visits, events, and confirmation history | Amazon Bedrock for conversation, extraction, classification, and summarization |
| Distributed Vector Indexing for retrieving related conversations and observations | Amazon Transcribe for speech-to-text |
| Managed MCP Server or Agent Skills for controlled agent access to care records | AWS Lambda for approval logic, validation, and database writes |
| Transactional updates linking the source conversation to confirmed events | Amazon S3 for generated PDFs or optional attachments |
| Persistent longitudinal record across appointment cycles | API Gateway for the application backend |

The hackathon requires an agentic application using CockroachDB as the persistent memory layer on AWS and at least two designated CockroachDB tools.

---

## Safety Boundaries

CareMemo may:

- Record caregiver-reported symptoms and observations
- Record incidents
- Store medication information supplied by the caregiver
- Record clinician-directed medication changes
- Save questions for a healthcare professional
- Generate a factual summary

CareMemo may not:

- Diagnose a condition
- Recommend treatment
- Recommend or change medication
- Infer that a medication caused a symptom
- Decide whether a situation is an emergency
- Replace clinical judgment
- Save AI-extracted information as fact without caregiver confirmation

> **The AI proposes. The caregiver confirms. CareMemo remembers.**

---

### Compared with ChatGPT or Claude

General AI assistants can discuss caregiving, remember project context, and generate summaries. CareMemo provides a fixed, repeatable workflow:

```text
Talk naturally
      ↓
Extract structured updates
      ↓
Confirm
      ↓
Maintain the timeline
      ↓
Generate the next visit summary
```

Its advantage is not a better language model; it is a purpose-built caregiver workflow.
