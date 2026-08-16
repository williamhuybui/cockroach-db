"""Dashboard API — reads calls, transcripts, and customers from CockroachDB.

Transcript turns are written by the live call path in main.py. Notes and
uploaded files have no tables yet, so they still live on disk
(notes.json / uploads/).
"""
import asyncio
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from psycopg2.errors import ForeignKeyViolation, UniqueViolation
from pydantic import BaseModel, ValidationError

import live_calls
from api_models import CallCreate
from calendar_service import delete_appointment_event, upsert_appointment_event
from config import COMPANY_TIMEZONE
from database import execute_sql, get_database_transaction
from post_call_extraction import extract_call_summary
from routers.calls import create_tasks_for_call, insert_call, update_call_from_extraction

# The simulate endpoint only ever writes to the in-memory live_calls registry
# (no DB, no Twilio, no OpenAI), but it's still an unauthenticated POST that
# fabricates a fake call — disable it in production explicitly rather than
# relying on nobody finding the URL.
LIVE_SIMULATE_ENABLED = os.getenv("LIVE_SIMULATE_ENABLED", "1") == "1"

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
STATIC_DIR = BASE_DIR / "static"
NOTES_FILE = REPO_ROOT / "notes.json"

router = APIRouter()


class NoCacheStaticFiles(StaticFiles):
    """StaticFiles that forces revalidation on every request.

    Plain StaticFiles only sends Last-Modified/ETag, which lets a browser's
    heuristic cache serve a stale dashboard.js/css straight from disk with
    *no* network request at all when a page is reloaded moments after an
    edit — a real bug can look identical to "the old file is still cached".
    `no-cache` still lets the browser send a conditional GET (so an
    unchanged file gets a cheap 304), it just stops it from skipping the
    request entirely.
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response

# ---------- conversations (one per call_id in the transcripts table) ----------


def _get_call_tags(call_ids):
    """Real topic tags from post-call extraction (calls.tags — an LLM-produced
    free-form list, see post_call_extraction.py), keyed by call_id. A call
    with no calls-table row yet (extraction hasn't run or failed) or a null
    tags column just isn't in the returned dict — callers should default to
    an empty list."""
    call_ids = list(call_ids)
    if not call_ids:
        return {}
    rows = execute_sql(
        "SELECT call_id, tags FROM calls WHERE call_id = ANY(%s)",
        (call_ids,),
    )
    return {r["call_id"]: (r["tags"] or []) for r in rows}


def _build_conversation(call_id, rows, tags=None):
    """Shape one call's transcript rows the way the frontend expects."""
    messages = [
        {
            "id": str(r["id"]),
            "timestamp": r["timestamp"].isoformat() if r["timestamp"] else "",
            "speaker": r["speaker"],
            "text": r["text"],
        }
        for r in rows
    ]

    start_time = messages[0]["timestamp"] if messages else None
    end_time = messages[-1]["timestamp"] if messages else None
    duration_seconds = 0
    if rows and rows[0]["timestamp"] and rows[-1]["timestamp"]:
        duration_seconds = round((rows[-1]["timestamp"] - rows[0]["timestamp"]).total_seconds())

    preview = next((m["text"] for m in messages if m["speaker"] == "caller"), None)
    if preview is None:
        preview = messages[0]["text"] if messages else ""

    # topics come from the caller (real LLM extraction, not derived here).
    # Action items (to-dos) live in the tasks table now — see
    # /api/action-items — not on this record at all.
    return {
        "id": call_id,
        "caller_number": rows[0]["caller_number"] if rows else "unknown",
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": duration_seconds,
        "message_count": len(messages),
        "preview": preview[:160],
        "topics": tags or [],
        "messages": messages,
    }


def list_conversations():
    """Every call in the transcripts table, newest first."""
    rows = execute_sql(
        """
        SELECT id, call_id, "timestamp", caller_number, speaker, text
        FROM transcripts
        ORDER BY call_id, "timestamp"
        """
    )

    grouped = {}
    for row in rows:
        grouped.setdefault(row["call_id"], []).append(row)

    tags_by_call = _get_call_tags(grouped.keys())
    conversations = [
        _build_conversation(cid, r, tags_by_call.get(cid)) for cid, r in grouped.items()
    ]
    conversations.sort(key=lambda c: c["start_time"] or "", reverse=True)
    return conversations


def get_conversation(conversation_id):
    rows = execute_sql(
        """
        SELECT id, call_id, "timestamp", caller_number, speaker, text
        FROM transcripts
        WHERE call_id = %s
        ORDER BY "timestamp"
        """,
        (conversation_id,),
    )
    if not rows:
        return None
    tags = _get_call_tags([conversation_id]).get(conversation_id)
    return _build_conversation(conversation_id, rows, tags)


# ---------- notes (still on disk — no notes table yet) ----------


def _load_notes():
    if not NOTES_FILE.exists():
        return {}
    try:
        return json.loads(NOTES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_notes(notes):
    NOTES_FILE.write_text(json.dumps(notes, indent=2), encoding="utf-8")


# ---------- action items (the tasks table) ----------
#
# These are the real, persisted follow-ups written by the post-call extraction
# (routers/calls.py create_tasks_for_call), with id and status, so they can
# actually be checked off from the dashboard.

# LEFT JOIN calls on purpose: tasks.call_id has no foreign key, and deleting a
# call leaves its tasks behind, so the call row may not exist.
_ACTION_ITEM_SELECT = """
    SELECT t.id::STRING   AS id,
           t.call_id,
           t.description,
           t.status,
           t.created_at,
           t.completed_at,
           t.scheduled_at,
           t.calendar_event_id,
           t.is_appointment,
           t.suggested_datetime,
           cu.phone_number AS caller_number,
           cu.full_name    AS caller_name,
           ca."timestamp"  AS call_time,
           ca.problem,
           ca.urgency,
           ca.availability
    FROM tasks t
    JOIN customers cu ON cu.id = t.customer_id
    LEFT JOIN calls ca ON ca.call_id = t.call_id
"""

# Open items first, then most recent call first within each group.
_ACTION_ITEM_ORDER = """
    ORDER BY (t.status = 'done'), COALESCE(ca."timestamp", t.created_at) DESC
"""


def _iso(value):
    return value.isoformat() if value else None


def _action_item_record(row):
    return {
        "id": row["id"],
        "call_id": row["call_id"],
        "description": row["description"],
        "status": row["status"],
        "created_at": _iso(row["created_at"]),
        "completed_at": _iso(row["completed_at"]),
        "scheduled_at": _iso(row["scheduled_at"]),
        "has_calendar_event": row["calendar_event_id"] is not None,
        "caller_number": row["caller_number"],
        "caller_name": row["caller_name"] or "",
        "call_time": _iso(row["call_time"]),
        "problem": row["problem"],
        "urgency": row["urgency"],
        "availability": row["availability"],
        # Both straight from the extraction LLM's own read of this item (see
        # post_call_extraction.py's todo_items schema) — no keyword/regex
        # classification after the fact. suggested_datetime only pre-fills
        # the Schedule sheet; scheduled_at above is the human-confirmed one.
        "is_appointment": row["is_appointment"],
        "suggested_datetime": _iso(row["suggested_datetime"]),
    }


def list_action_items(call_id=None, limit=200):
    if call_id:
        sql = f"{_ACTION_ITEM_SELECT} WHERE t.call_id = %s {_ACTION_ITEM_ORDER} LIMIT %s"
        params = (call_id, limit)
    else:
        sql = f"{_ACTION_ITEM_SELECT} {_ACTION_ITEM_ORDER} LIMIT %s"
        params = (limit,)
    return [_action_item_record(r) for r in execute_sql(sql, params)]


def _get_raw_action_item(task_id):
    """Like get_action_item, but the unshaped DB row — real datetimes and
    calendar_event_id included, for callers that need to write those back
    (e.g. api_update_action_item, when upserting a calendar event)."""
    rows = execute_sql(f"{_ACTION_ITEM_SELECT} WHERE t.id = %s", (task_id,))
    return rows[0] if rows else None


def get_action_item(task_id):
    row = _get_raw_action_item(task_id)
    return _action_item_record(row) if row else None


# ---------- request bodies ----------


class ActionItemUpdate(BaseModel):
    # Both optional and independent: the "mark done"/"reopen" button sends
    # only status, the Schedule sheet sends only scheduled_at. Omitted
    # fields are left as they were.
    status: Literal["open", "done"] | None = None
    # "YYYY-MM-DDTHH:MM" from the Schedule sheet's native date/time inputs,
    # interpreted as company-local time (config.COMPANY_TIMEZONE). Send null
    # explicitly to clear a previously scheduled slot.
    scheduled_at: str | None = None
    # Only used alongside scheduled_at, to size/annotate the calendar event —
    # neither is persisted on the task itself (no columns for them; the
    # calendar event is the only place they end up).
    duration_minutes: int | None = None
    note: str | None = None


class CallerNameRequest(BaseModel):
    name: str


class NoteRequest(BaseModel):
    text: str


class ClientRequest(BaseModel):
    name: str = ""
    email: str = ""
    address: str = ""


class NewClientRequest(ClientRequest):
    phone: str


# ---------- conversation endpoints ----------


@router.get("/api/conversations")
async def api_list_conversations():
    return [{k: v for k, v in c.items() if k != "messages"} for c in list_conversations()]


@router.get("/api/conversations/{conversation_id}")
async def api_get_conversation(conversation_id: str):
    conversation = get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.delete("/api/conversations/{conversation_id}")
async def api_delete_conversation(conversation_id: str):
    """Delete a call entirely: every transcript turn, its follow-up tasks, its
    calls-table summary row (if post-call extraction finished), and any local
    notes. This predates the calls/tasks tables and used to only touch
    transcripts, which left orphaned rows in both once they existed.
    """
    rows = execute_sql(
        "DELETE FROM transcripts WHERE call_id = %s RETURNING id",
        (conversation_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # tasks.call_id has no FK (see migrations/004_tasks.sql), so this needs to
    # be explicit — it won't cascade.
    tasks_deleted = execute_sql(
        "DELETE FROM tasks WHERE call_id = %s RETURNING id",
        (conversation_id,),
    )
    execute_sql("DELETE FROM calls WHERE call_id = %s", (conversation_id,))

    # Drop its notes too, so they don't dangle against a deleted call.
    notes = _load_notes()
    if notes.pop(conversation_id, None) is not None:
        _save_notes(notes)

    return {
        "deleted": conversation_id,
        "turns_deleted": len(rows),
        "tasks_deleted": len(tasks_deleted),
    }


@router.delete("/api/conversations/{conversation_id}/messages/{message_id}")
async def api_delete_message(conversation_id: str, message_id: str):
    """Delete a single transcript turn."""
    rows = execute_sql(
        "DELETE FROM transcripts WHERE call_id = %s AND id = %s RETURNING id",
        (conversation_id, message_id),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"deleted": message_id}


@router.post("/api/conversations/{call_id}/reextract")
async def api_reextract_conversation(call_id: str):
    """Re-run post-call extraction (post_call_extraction.py) for a call that
    already has transcript turns — wired to the dashboard's "re-run
    extraction" (⟳) button. Works whether or not the call already has a
    calls-table row (e.g. the live extraction never ran or failed).

    Never wipes out existing tasks: a rerun refreshes the calls-table fields
    (name/tags/urgency/summary/...), but a human may have already scheduled
    or completed a to-do item from the action items panel, so tasks are only
    (re)created here if the call currently has none at all.
    """
    caller_rows = execute_sql(
        "SELECT DISTINCT caller_number FROM transcripts WHERE call_id = %s",
        (call_id,),
    )
    if not caller_rows:
        raise HTTPException(status_code=404, detail="No transcript found for this call")
    caller_number = caller_rows[0]["caller_number"]

    extracted = await extract_call_summary(call_id)
    if not extracted:
        raise HTTPException(
            status_code=502,
            detail="Extraction failed or returned nothing — check server logs",
        )

    try:
        call = CallCreate(call_id=call_id, caller_number=caller_number, **extracted)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=str(error))

    already_has_call_row = bool(execute_sql("SELECT 1 FROM calls WHERE call_id = %s", (call_id,)))
    existing_task_count = execute_sql(
        "SELECT count(*) AS n FROM tasks WHERE call_id = %s", (call_id,)
    )[0]["n"]

    try:
        async with get_database_transaction() as connection:
            if already_has_call_row:
                _, customer_id = await update_call_from_extraction(connection, call)
                if existing_task_count == 0:
                    await create_tasks_for_call(connection, call, customer_id)
            else:
                # insert_call always creates tasks itself, so there's no
                # separate existing_task_count check on this branch.
                await insert_call(connection, call)
    except (UniqueViolation, ForeignKeyViolation) as error:
        raise HTTPException(status_code=409, detail=str(error))

    return get_conversation(call_id)


# ---------- action item endpoints ----------


@router.get("/api/action-items")
async def api_list_action_items(call_id: str | None = None, limit: int = 200):
    """Persisted follow-ups from the tasks table, open ones first."""
    return list_action_items(call_id=call_id, limit=max(1, min(limit, 500)))


@router.patch("/api/action-items/{task_id}")
async def api_update_action_item(task_id: str, body: ActionItemUpdate):
    """Close an action item (or reopen it), and/or schedule an appointment.

    `status`/`completed_at` are written together so they can never disagree
    — reopening nulls the timestamp. Scheduling upserts a Google Calendar
    event (best-effort, see calendar_service.py) and stores its id alongside
    scheduled_at, so re-scheduling updates that same event instead of
    creating a duplicate.
    """
    try:
        uuid.UUID(task_id)
    except ValueError:
        # Without this a typo'd id reaches psycopg2 and surfaces as a 500.
        raise HTTPException(status_code=400, detail="Invalid action item id")

    existing = _get_raw_action_item(task_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Action item not found")

    status = body.status if body.status is not None else existing["status"]

    scheduled_at = existing["scheduled_at"]
    calendar_event_id = existing["calendar_event_id"]

    # model_fields_set (not just "is None") distinguishes "field omitted" from
    # "field explicitly sent as null" — the latter clears a previously
    # scheduled slot.
    if "scheduled_at" in body.model_fields_set:
        if body.scheduled_at is None:
            if calendar_event_id:
                delete_appointment_event(calendar_event_id)
            scheduled_at = None
            calendar_event_id = None
        else:
            try:
                naive = datetime.fromisoformat(body.scheduled_at)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="scheduled_at must look like YYYY-MM-DDTHH:MM",
                )
            # The Schedule sheet's date/time inputs are company-local with no
            # offset — attach one before storing/sending to Google.
            scheduled_at = naive.replace(tzinfo=ZoneInfo(COMPANY_TIMEZONE))
            calendar_event_id = upsert_appointment_event(
                task_id=task_id,
                description=existing["description"],
                scheduled_at=scheduled_at,
                caller_name=existing["caller_name"],
                caller_number=existing["caller_number"],
                existing_event_id=calendar_event_id,
                duration_minutes=body.duration_minutes,
                note=body.note,
            )

    rows = execute_sql(
        """
        UPDATE tasks
        SET status = %s,
            completed_at = CASE WHEN %s = 'done' THEN now() ELSE NULL END,
            scheduled_at = %s,
            calendar_event_id = %s,
            updated_at = now()
        WHERE id = %s
        RETURNING id
        """,
        (status, status, scheduled_at, calendar_event_id, task_id),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Action item not found")

    # Return the same shape GET does, so the frontend can splice it into state.
    return get_action_item(task_id)


# ---------- live calls (SSE) ----------


@router.get("/api/live/stream")
async def api_live_stream():
    """Server-sent events for every call currently in progress.

    A plain GET, kept open — EventSource on the frontend, or `curl -N`. See
    live_calls.subscribe() for the event sequence and heartbeat behavior.
    """
    return StreamingResponse(
        live_calls.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            # Proxies (ngrok, Caddy, nginx) must not buffer an SSE response —
            # buffering would hold events until the buffer fills, defeating
            # the whole point of a live stream.
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/live/calls")
async def api_live_calls():
    """Same data as the stream's snapshot event, as a plain GET — the
    fallback path for a browser without EventSource support."""
    return {"calls": live_calls.snapshot(), "server_time": datetime.now().isoformat()}


async def _run_fake_call():
    """Scripted fake call for /api/live/simulate. Touches no DB, no Twilio, no
    OpenAI — purely exercises live_calls so the live view is testable without
    dialing the real number."""
    stream_sid = f"SIM{uuid.uuid4().hex[:12]}"
    caller_number = "+14175559999"

    live_calls.start_call(stream_sid, caller_number)
    live_calls.set_started_at(stream_sid, datetime.now())
    await asyncio.sleep(0.4)

    live_calls.set_call_id(stream_sid, "C-SIM")
    await asyncio.sleep(0.3)
    live_calls.set_returning_caller(stream_sid, {"full_name": "Simulated Caller"})
    await asyncio.sleep(0.3)

    script = [
        ("assistant", "Thanks for calling, this is the front desk. What can I help with?"),
        ("caller", "Hi, my roof is leaking near the chimney after the storm."),
        ("assistant", "Sorry to hear that. What's the property address?"),
        ("caller", "88 Test Lane. Can someone come take a look this week?"),
        ("assistant", "Absolutely, I'll get that scheduled and send a quote."),
    ]
    for i, (speaker, text) in enumerate(script):
        live_calls.set_speaker(stream_sid, speaker, barge_in=(i == 3))
        await asyncio.sleep(0.3)
        live_calls.add_turn(stream_sid, speaker, text)
        live_calls.update_metrics(stream_sid, total_tokens=120 * (i + 1), duration_seconds=i * 2, wrap_up=(i >= 3))
        await asyncio.sleep(0.5)

    live_calls.set_speaker(stream_sid, "idle")
    live_calls.end_call(stream_sid, "disconnected")
    await asyncio.sleep(0.6)
    live_calls.set_summary(stream_sid, {
        "problem": "Roof leak",
        "urgency": "Medium",
        "summary": "Simulated caller reported a roof leak near the chimney and wants a visit this week.",
        "todo_items": ["Schedule a visit", "Send a quote"],
        "tags": ["leak", "schedule"],
    })


@router.post("/api/live/simulate")
async def api_live_simulate():
    """Dev-only: run a scripted fake call through the live registry so the
    live view can be exercised without a real phone call."""
    if not LIVE_SIMULATE_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    asyncio.create_task(_run_fake_call())
    return {"started": True}


# ---------- notes endpoints ----------


@router.get("/api/conversations/{conversation_id}/notes")
async def api_list_notes(conversation_id: str):
    if not get_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return _load_notes().get(conversation_id, [])


@router.post("/api/conversations/{conversation_id}/notes")
async def api_add_note(conversation_id: str, body: NoteRequest):
    if not get_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Note text is required")

    notes = _load_notes()
    conversation_notes = notes.setdefault(conversation_id, [])
    conversation_notes.append({
        "id": uuid.uuid4().hex[:8],
        "text": text,
        "created_at": datetime.now().isoformat(),
    })
    _save_notes(notes)
    return conversation_notes


@router.delete("/api/conversations/{conversation_id}/notes/{note_id}")
async def api_delete_note(conversation_id: str, note_id: str):
    notes = _load_notes()
    conversation_notes = [n for n in notes.get(conversation_id, []) if n["id"] != note_id]
    notes[conversation_id] = conversation_notes
    _save_notes(notes)
    return conversation_notes


# ---------- clients (the customers table) ----------


def _client_record(row):
    return {
        "phone": row["phone_number"],
        "name": row["full_name"] or "",
        "email": row["email"] or "",
        "address": row["address"] or "",
        # True once a human has set/corrected the name from the dashboard —
        # see routers/calls.py's upsert_customer for the side that respects
        # this to stop post-call extraction from silently overwriting it.
        "name_is_manual": bool(row.get("name_is_manual")),
    }


def _get_customer(phone):
    rows = execute_sql("SELECT * FROM customers WHERE phone_number = %s", (phone,))
    return rows[0] if rows else None


@router.get("/api/callers/names")
async def api_caller_names():
    rows = execute_sql(
        "SELECT phone_number, full_name FROM customers WHERE full_name IS NOT NULL AND full_name != ''"
    )
    return {r["phone_number"]: r["full_name"] for r in rows}


@router.post("/api/callers/{caller_number}/name")
async def api_set_caller_name(caller_number: str, body: CallerNameRequest):
    name = body.name.strip()
    # A human explicitly setting the name here — lock it so a later
    # extraction rerun can't overwrite it (see routers/calls.py's
    # upsert_customer).
    execute_sql(
        """
        INSERT INTO customers (phone_number, full_name, name_is_manual)
        VALUES (%s, %s, true)
        ON CONFLICT (phone_number) DO UPDATE SET full_name = %s, name_is_manual = true, updated_at = now()
        """,
        (caller_number, name, name),
    )
    return await api_caller_names()


@router.get("/api/clients")
async def api_list_clients():
    """Every customer, plus call counts taken from the transcripts table."""
    customers = execute_sql("SELECT * FROM customers")
    stats = execute_sql(
        """
        SELECT caller_number,
               count(DISTINCT call_id) AS call_count,
               max("timestamp") AS last_call
        FROM transcripts
        GROUP BY caller_number
        """
    )
    stats_by_phone = {s["caller_number"]: s for s in stats}

    result = []
    for row in customers:
        record = _client_record(row)
        stat = stats_by_phone.pop(row["phone_number"], None)
        record["call_count"] = stat["call_count"] if stat else 0
        record["last_call"] = stat["last_call"].isoformat() if stat and stat["last_call"] else None
        result.append(record)

    # Callers who phoned in but aren't saved as customers yet.
    for phone, stat in stats_by_phone.items():
        result.append({
            "phone": phone,
            "name": "",
            "email": "",
            "address": "",
            "name_is_manual": False,
            "call_count": stat["call_count"],
            "last_call": stat["last_call"].isoformat() if stat["last_call"] else None,
        })

    result.sort(key=lambda r: r["last_call"] or "", reverse=True)
    return result


@router.post("/api/clients")
async def api_create_client(body: NewClientRequest):
    phone = body.phone.strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")
    return await api_update_client(phone, body)


@router.get("/api/clients/{phone}")
async def api_get_client(phone: str):
    row = _get_customer(phone)
    if not row:
        return {"phone": phone, "name": "", "email": "", "address": "", "name_is_manual": False}
    return _client_record(row)


@router.post("/api/clients/{phone}")
async def api_update_client(phone: str, body: ClientRequest):
    name = body.name.strip()
    # A human explicitly saving a non-empty name here — lock it so a later
    # extraction rerun can't overwrite it (see routers/calls.py's
    # upsert_customer). A blank name isn't a "correction", so it doesn't
    # lock — that would otherwise permanently block extraction from ever
    # filling one in.
    name_is_manual = bool(name)
    rows = execute_sql(
        """
        INSERT INTO customers (phone_number, full_name, email, address, name_is_manual)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (phone_number) DO UPDATE
            SET full_name = %s, email = %s, address = %s, name_is_manual = %s, updated_at = now()
        RETURNING *
        """,
        (
            phone,
            name,
            body.email.strip(),
            body.address.strip(),
            name_is_manual,
            name,
            body.email.strip(),
            body.address.strip(),
            name_is_manual,
        ),
    )
    return _client_record(rows[0])


@router.get("/api/clients/{phone}/conversations")
async def api_client_conversations(phone: str):
    conversations = [c for c in list_conversations() if c["caller_number"] == phone]
    return [{k: v for k, v in c.items() if k != "messages"} for c in conversations]


@router.get("/dashboard")
async def dashboard_page():
    return FileResponse(str(STATIC_DIR / "dashboard.html"))


@router.get("/live")
async def live_page():
    return FileResponse(str(STATIC_DIR / "live.html"))


def register_dashboard(app):
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", NoCacheStaticFiles(directory=str(STATIC_DIR)), name="dashboard-static")
    app.include_router(router)
