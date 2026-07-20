# TinyQuest AI — Personalized Learning Pet

*An AI pet with persistent memory that turns a child's interests, learning style, and skill progress into personalized learning quests, healthy habits, and fun rewards — with parents in full control of what it remembers.*

**Demo:** https://guide-quake-46421270.figma.site/

---

## The Problem

Most educational apps treat every child the same: the same lesson order, the same difficulty curve, the same hints, regardless of whether a child loves dinosaurs or soccer, learns best by reading or by doing, or already mastered fractions last month but still struggles with word problems.

Children lose motivation when content doesn't connect to what they care about, and they repeat the same mistakes when nothing remembers which hint actually helped last time. Healthy habits — reading time, movement breaks, sleep routines — are hard to reinforce without making them feel like chores.

Parents, meanwhile, want their child to have a personalized, encouraging learning experience, but they also want visibility and control over what an AI system is learning about their child and why — not a black box.

Children should get an experience that adapts to them. Parents should never have to wonder what the AI remembers or why it's not editable.

---

## Who It Is For

Parents of children roughly ages 7–11 who want:

- A personalized supplement to school learning (reading, math, science, habits)
- A fun, low-pressure way to reinforce healthy routines (movement, reading time, sleep)
- Visibility into their child's actual skill progress, not just app usage time
- Full control over what the AI remembers and can act on

TinyQuest AI is not:

- A replacement for a teacher, tutor, or school curriculum
- An open-ended chatbot the child can talk to about anything
- A social network or messaging platform for children
- A tool that makes decisions unsupervised by a parent
- A system that shares or sells a child's data or learning history

---

## The Solution

1. **Play and talk** — the child interacts with their AI pet through short, guided quests (voice or simple taps/text), not open-ended chat.
2. **Learn what matters to this child** — the pet notices stated interests, preferred learning style (reading, watching, doing), and how the child responds to different kinds of hints.
3. **Craft a personalized quest** — using skill progress and past mistakes, the pet proposes a quest themed around the child's interests, at the right difficulty.
4. **Track progress, not just completion** — correct answers, mistakes, which hints worked, and habit check-ins (movement, reading, sleep) are recorded.
5. **Celebrate and remember** — completed quests and mastered skills appear as milestones on a simple skill journey; small mistakes and everyday activity stay in Recent Activity.
6. **Keep parents in control** — a parent dashboard shows exactly what the pet has learned about the child, with the ability to view, edit, or delete any of it.

```text
Child plays/talks with the pet
        ↓
AI notices interests, learning style, skill level, effective hints
        ↓
Pet proposes a personalized quest
        ↓
Child completes quest (or asks for a hint)
        ↓
Skill Journey and Recent Activity update
        ↓
Parent dashboard reflects what changed and why
```

---

## Example

**Child says (or picks from simple prompts):**

> "I love dinosaurs! Fractions are hard though."

**TinyQuest AI proposes:**

- **Interest noted:** Dinosaurs
- **Skill focus:** Fractions (currently below grade-level benchmark)
- **Quest created:** "Dino Bone Dig" — split a dinosaur fossil into equal fraction pieces to help a paleontologist
- **Hint strategy:** Visual (pie-style bone slices) tried first, since the pet remembers this child responds better to visual hints than word-based ones

The child plays the quest. If they get stuck, the pet offers the visual hint first (since that has worked before), records whether it helped, and adjusts hint style for next time.

```text
New quest ready!

Dino Bone Dig 🦴
Skill: Fractions · Theme: Dinosaurs (your favorite!)

[Start quest] [Not right now]
```

---

## Product Workspace

```text
┌──────────────────────────────────────────────────────────────┐
│ TINYQUEST AI                                                  │
│ Ellie's Pet: Spark 🦕                          Parent view ⚙  │
├──────────────────────────────────────────────────────────────┤
│ TODAY'S QUEST                                                 │
│ Dino Bone Dig 🦴 · Fractions · ~10 min                        │
│ Themed around dinosaurs, Ellie's favorite!                    │
│                                    [Start quest] [Later]       │
├──────────────────────────────────────────────────────────────┤
│ SKILL JOURNEY                                                 │
│                                                                │
│ 🏆 Jun 3      🏆 Jun 20       🏆 Jul 5       🏆 Jul 18       │
│ Addition        Reading level   Multiplication  Fractions       │
│ mastered        up               mastered        started         │
│                                                                │
│                         🏆 Aug (next goal)                    │
│                    Fractions mastery                          │
├──────────────────────────────────────────────────────────────┤
│ RECENT ACTIVITY                                               │
│                                                                │
│ Jul 19 · Completed "Dino Bone Dig" · 2 hints used         ›   │
│ Jul 18 · Read for 20 minutes (habit streak: 5 days)       ›   │
│ Jul 17 · Missed a fraction question, visual hint helped   ›   │
│ Jul 15 · Said she loves dinosaurs and space               ›   │
│                                                                │
│                                             [View all]         │
├──────────────────────────────────────────────────────────────┤
│                    [🎤 Talk to Spark] [🎯 Start a quest]       │
└──────────────────────────────────────────────────────────────┘
```

### 1. Today's Quest

This is the primary, always-visible output and should sit at the top of the page.

It displays:

- The quest name and theme, tied to the child's stated interests
- The skill being practiced and current difficulty level
- Estimated time to complete
- Start / Later actions

```text
TODAY'S QUEST

Dino Bone Dig 🦴
Skill: Fractions · Theme: Dinosaurs
Estimated time: ~10 minutes

[Start quest] [Do this later]
```

If a habit check-in is also due, it appears alongside:

```text
HABIT CHECK-IN

Did you move your body today?
[Yes! 🏃] [Not yet] [Ask me later]
```

### 2. Skill Journey

Its purpose is to answer:

> **What has this child actually mastered, over time?**

Suitable milestones include:

- A skill or topic reaching mastery (e.g., addition, multiplication, a reading level)
- A new subject started
- A meaningful habit streak milestone (e.g., 5 days of reading)
- A learning style insight confirmed (e.g., "responds best to visual hints")
- A parent-set goal reached

Routine quest completions and small mistakes do not appear as milestones — only durable progress.

When the AI detects a possible milestone, it is shown to the parent (not decided unilaterally) before being added:

```text
Possible milestone

Fractions: consistent correct answers without hints
Detected from: last 4 quests

[Add to Skill Journey] [Not yet — keep practicing] [Dismiss]
```

Selecting a milestone opens a details panel containing:

- Date and skill category
- Supporting quest history
- Whether it is visible to the child as a celebration moment
- Parent edit or remove actions

### 3. Recent Activity

Recent Activity contains the detailed, day-to-day record. Each row is clickable and parent-visible.

```text
RECENT ACTIVITY

Jul 19
Completed "Dino Bone Dig"
Skill: Fractions · Hints used: 2 (both visual)
Result: Correct on final attempt

Jul 18
Read for 20 minutes
Category: Habit · Streak: 5 days

Jul 17
Missed a fraction question
Hint offered: Visual (pie-style) · Outcome: Helped
```

Selecting an activity opens its details panel:

```text
Completed "Dino Bone Dig"

Recorded:
Jul 19

What happened:
Ellie answered 3 of 5 fraction questions correctly
on the first try. Two questions needed a visual hint,
which she solved correctly afterward.

Learning note saved:
Visual hints continue to work better than
word-based hints for fractions.

Visible to Ellie: Yes (as an encouraging recap)

[View in detail] [Remove from record]
```

Recent Activity answers:

> **What has my child been doing and learning lately?**

The Skill Journey answers:

> **What has my child actually mastered over time?**

### 4. Talk to Spark / Start a Quest

Selecting **Talk to Spark** or **Start a quest** opens a guided capture panel — always structured, never an open-ended chat.

```text
Talk to Spark 🦕

"What's your favorite thing right now?"

[Dinosaurs] [Space] [Animals] [Something else...]
```

TinyQuest AI then proposes a personalized quest or habit nudge:

```text
Spark has an idea!

Since you love dinosaurs, want to try a
fraction quest about digging up dino bones?

[Let's go!] [Maybe later]
```

After a quest or check-in is completed:

- The activity appears in Recent Activity.
- A durable milestone may be proposed on the Skill Journey.
- The child sees a simple, encouraging recap and a reward (sticker, badge, or pet accessory).
- The parent dashboard reflects the same update in plain language.

The interaction should feel immediate and playful:

```text
Talk / play
  ↓
Spark notices interests, style, and skill level
  ↓
Personalized quest proposed
  ↓
Child completes quest, hints tracked
  ↓
Recent Activity updates, reward given
  ↓
Milestone appears when mastery is reached
```

### Temporary Panels

The workspace uses three overlays rather than separate navigation pages:

| Panel | Purpose |
|---|---|
| **Quest/talk panel** | Guided prompts, quest generation, and reward moment (child-facing) |
| **Activity or milestone details panel** | What happened, why, and whether it's visible to the child (parent-facing) |
| **Parent memory dashboard** | Full view of what the pet remembers, with edit/delete controls |

```text
                       TINYQUEST AI HOME
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
     Start a quest      Select an activity    Open parent dashboard
          │                   │                   │
          ▼                   ▼                   ▼
     Quest panel        Details panel        Memory dashboard
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
                     Same pet workspace
```

## Agent Architecture

The child sees one friendly pet, while three logical agents work behind it.

| Agent | Responsibility |
|---|---|
| **Quest Agent** | Turns a child's stated interests, skill level, and available time into a personalized, age-appropriate quest |
| **Learning Memory Agent** | Stores skill progress, past mistakes, effective hint styles, interests, and habit streaks, and decides what counts as a milestone |
| **Parent Dashboard Agent** | Translates raw memory into plain-language summaries for parents and enforces parent edit/delete controls over stored data |

```text
Child
   │
   ▼
Quest Agent
   │
   ▼
Quest completed / hint used / habit checked in
   │
   ▼
Learning Memory Agent
   │
   ▼
CockroachDB
   ├── Skill Journey
   ├── Recent Activity
   └── Parent Dashboard Agent
            │
            ▼
      Parent-facing summary + controls
```

The three logical agents may use the same underlying model with different prompts, tools, and content filters appropriate to each audience (child vs. parent).

---

## Persistent Memory Model

CockroachDB stores:

- Children profiles (age band, stated interests, learning style signals)
- Parents and their linked children
- Skill progress per topic and difficulty level
- Past mistakes and which hint style resolved them
- Quest history and completion outcomes
- Habit check-ins and streaks
- Milestones and rewards
- Parent-set goals and permissions
- Full edit/delete history of what a parent has changed or removed

Memory is essential because the agent must know:

- What this specific child is interested in and how they learn best
- Which skills are mastered versus still developing
- Which hints have actually worked before, so the same mistake isn't repeated
- What a parent has already reviewed, approved, or removed
- What is appropriate to celebrate with the child versus only show a parent

Without persistent memory, TinyQuest AI is only a generic quiz generator that starts over every session.

---

## Technology Mapping

| CockroachDB | AWS |
|---|---|
| Structured SQL memory for children, parents, skills, quests, and habit streaks | Amazon Bedrock for quest generation, hint personalization, and plain-language parent summaries |
| Distributed Vector Indexing for matching a child's interests and past mistakes to relevant quest content | Amazon Transcribe for optional voice interaction with the pet |
| Managed MCP Server or Agent Skills for controlled agent access to a child's learning record | AWS Lambda for milestone detection, reward logic, and database writes |
| Transactional updates linking a completed quest to updated skill and hint-effectiveness records | Amazon S3 for reward assets (badges, pet accessories) and exported progress reports |
| Persistent, longitudinal learning record the child (and their pet) carries across sessions | API Gateway for the mobile/web application backend |

The hackathon requires an agentic application using CockroachDB as the persistent memory layer on AWS and at least two designated CockroachDB tools.

---

## Safety Boundaries

TinyQuest AI may:

- Record a child's stated interests, learning style signals, and skill progress
- Track which hints were effective for a given child and skill
- Propose personalized, age-appropriate quests and habit nudges
- Celebrate milestones with the child using simple, encouraging language
- Show parents a full, plain-language record of what the pet has learned
- Let parents view, edit, or delete any stored memory about their child

TinyQuest AI may not:

- Engage in open-ended, unstructured conversation with a child
- Diagnose a learning disability or any medical/psychological condition
- Collect or infer sensitive information beyond what's needed for learning personalization
- Share, sell, or use a child's data for advertising
- Allow the child to message or connect with strangers
- Make changes to a child's stored profile without parent visibility
- Present a reward or milestone as earned if it was not actually completed by the child

> **The pet notices. The parent controls the memory. TinyQuest AI helps the child grow.**

---

### Compared with ChatGPT or Claude

General AI assistants can hold a conversation with a child and even remember context within a session. TinyQuest AI provides a fixed, repeatable, kid-safe workflow with parents in the loop:

```text
Child plays or talks (guided, not open-ended)
      ↓
Pet notices interests, style, and skill level
      ↓
Personalized quest or habit nudge proposed
      ↓
Progress and hint effectiveness recorded
      ↓
Parent dashboard reflects and controls all of it
      ↓
Next quest gets more personalized, not repetitive
```

Its advantage is not a better language model; it is a structured, parent-controlled, persistent memory purpose-built for how children actually learn over time.
