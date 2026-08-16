"""
Post-call structured extraction — separate from the live conversation.

The live agent (OpenAI Realtime, see main.py) only handles the phone
conversation itself and decides when to hang up (the `end_call` tool).
Once a call actually ends, this module reads the full transcript back
from CockroachDB and asks a Groq-hosted, open-weight model (Llama 3.3 by
default — see GROQ_MODEL in config.py) to extract the same structured
fields the live agent used to fill in itself via `save_call_summary`.

Groq's API is free-tier and OpenAI-compatible, so this uses a plain
`requests` POST rather than adding a new SDK dependency — the project
already depends on `requests` for other things.
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from config import GROQ_API_URL, GROQ_MODEL, GROQ_REQUEST_TIMEOUT_SECONDS
from database import get_transcript_for_call

load_dotenv()

logger = logging.getLogger("voice_assistant")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("Missing the Groq API key (GROQ_API_KEY).")

# Mirrors the JSON schema the live agent's old save_call_summary tool used —
# same fields, same enum values — so the rest of the pipeline (CallCreate
# validation, insert_call) doesn't need to change at all.
EXTRACTION_SYSTEM_PROMPT = """You review a transcript of a phone call between a caller and the front-desk assistant for a roofing and storm-restoration company. Extract a structured summary for the office staff to review.

Respond with ONLY a JSON object (no other text) using these fields. Omit a field entirely if the transcript doesn't clearly give you that information — never guess or invent a value:

- name (string): caller's full name, or the property owner's name if calling on someone else's behalf.
- email (string): caller's email, if mentioned.
- address (string): property address needing service.
- problem (string): short label, e.g. "Roof leak", "Missing shingles", "Storm damage".
- problem_detail (string): more specific detail — where, how long, likely cause.
- availability (string): days/times that work for a visit or callback. The call's date is given below the
  transcript — if the caller uses a relative day ("today", "this Friday", "tomorrow", "next Tuesday"), resolve
  it against THAT call date (not any other date) into an actual calendar date, and include the resolved date
  WITH ITS YEAR plus the time in this field, e.g. "Friday, August 21, 2026, after 5 PM", not just "Friday after
  5 PM" or "today after 5 PM". If no day/time is mentioned at all, leave this field out.
- urgency (string, REQUIRED): one of "Low", "Medium", "High", "Emergency" — your best assessment even if nothing else is known.
- calling_on_behalf_of (string): set only if the caller is calling on someone else's behalf.
- summary (string, REQUIRED): 1-3 sentence plain-language summary for the business owner — what the caller needed and what was agreed.
- tags (array of strings): short topic labels, e.g. "schedule", "quote", "follow-up", "emergency", "complaint".
- todo_items (array of objects): concrete next steps the business still needs to do. Omit or leave empty if nothing
  is left. Each object has:
    - description (string, REQUIRED): the next step itself, e.g. "Send a quote", "Call back to confirm visit time".
    - is_appointment (boolean, REQUIRED): true if this step is about scheduling, confirming, or rescheduling an
      in-person visit/appointment; false for anything else (sending a quote, a callback with no visit, etc).
    - suggested_datetime (string): only when is_appointment is true AND the caller and agent actually settled on a
      specific date and time for that visit. Resolve it the same way as above — against the call's own date given
      below the transcript, never any other date — into ISO 8601 "YYYY-MM-DDTHH:MM" (24-hour time), e.g.
      "2026-08-21T17:00". Omit this field entirely if no specific date/time was agreed (e.g. "we'll call back to
      confirm a time" has is_appointment true but no suggested_datetime).

"summary" and "urgency" are the only required fields — always include your best assessment for those two."""


def _build_transcript_text(turns: list[dict]) -> str:
    return "\n".join(f"{turn['speaker']}: {turn['text']}" for turn in turns)


def _extract_fields_with_groq(transcript_text: str, call_date: datetime) -> dict:
    """Blocking call to Groq's OpenAI-compatible chat completions endpoint.
    Run this via asyncio.to_thread — never call it directly from async code.

    call_date is the call's own start time, given to the model so it can
    resolve a relative day ("this Friday") into an actual calendar date —
    it has no other way to know what day the call happened on.
    """
    # %-d (no leading zero) is a glibc/macOS strftime extension, not portable
    # to Windows — strip the zero manually instead so this can't ever raise.
    date_line = f"Call date: {call_date.strftime('%A, %B %d, %Y').replace(' 0', ' ')}"
    response = requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": f"{date_line}\n\nCall transcript:\n\n{transcript_text}"},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        },
        timeout=GROQ_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)


async def extract_call_summary(call_id: str) -> dict | None:
    """
    Pull the full transcript for call_id and ask Groq to extract the same
    structured fields save_call_summary used to fill in live. Returns a
    raw field dict (main.py's save_structured_call validates it against
    CallCreate the same way it always has), or None if there's no
    transcript to work with or extraction fails for any reason — this is
    a best-effort enrichment step, not something that should ever take
    down the call itself.
    """

    turns = await asyncio.to_thread(get_transcript_for_call, call_id)

    if not turns:
        logger.warning(
            "No transcript turns found for call_id=%s; skipping post-call extraction.",
            call_id,
        )
        return None

    transcript_text = _build_transcript_text(turns)
    # First turn's timestamp is when the call started — used so the model can
    # resolve "this Friday"/"tomorrow" into a real date. Fall back to now()
    # only if a turn somehow has no timestamp.
    call_date = turns[0].get("timestamp") or datetime.now(timezone.utc)

    try:
        extracted = await asyncio.to_thread(_extract_fields_with_groq, transcript_text, call_date)
    except Exception:
        logger.exception("Groq post-call extraction request failed for call_id=%s", call_id)
        return None

    logger.info("Groq post-call extraction succeeded for call_id=%s", call_id)
    return extracted


if __name__ == "__main__":
    # Quick manual test against a made-up transcript — no CockroachDB needed,
    # just a valid GROQ_API_KEY in your .env:
    #   cd src && python post_call_extraction.py
    example_turns = [
        {"speaker": "caller", "text": "Hi, I have a leak in my roof and it's kind of an emergency."},
        {"speaker": "agent", "text": "Sorry to hear that. Can I get your name and address?"},
        {"speaker": "caller", "text": "It's Jane Doe, 123 Maple St. Can you also give me an estimate for a full replacement?"},
        {"speaker": "agent", "text": "I'll have someone call you back with pricing and get an appointment scheduled."},
        {"speaker": "caller", "text": "Thanks, appreciate it."},
    ]

    example_transcript_text = _build_transcript_text(example_turns)
    print("--- transcript sent to Groq ---")
    print(example_transcript_text)
    print("--- extracted fields ---")
    print(json.dumps(_extract_fields_with_groq(example_transcript_text, datetime.now(timezone.utc)), indent=2))