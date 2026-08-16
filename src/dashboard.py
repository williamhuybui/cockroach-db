"""Dashboard API — reads calls, transcripts, and customers from CockroachDB.

Transcript turns are written by the live call path in main.py. Notes and
uploaded files have no tables yet, so they still live on disk
(notes.json / uploads/).
"""
import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import execute_sql

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
UPLOADS_DIR = REPO_ROOT / "uploads"
STATIC_DIR = BASE_DIR / "static"
NOTES_FILE = REPO_ROOT / "notes.json"

router = APIRouter()

TODO_RULES = [
    (re.compile(r"\bquote\b", re.I), "Send a quote"),
    (re.compile(r"\bestimate\b", re.I), "Send an estimate"),
    (re.compile(r"\bphoto|picture\b", re.I), "Review submitted photos"),
    (re.compile(r"\bappointment\b", re.I), "Schedule an appointment"),
    (re.compile(r"\bschedule\b", re.I), "Schedule an appointment"),
    (re.compile(r"\bcall(ing)? (me |him |her |them )?back\b", re.I), "Return the call"),
    (re.compile(r"\bfollow[- ]up\b", re.I), "Follow up with caller"),
    (re.compile(r"\bprice|pricing\b", re.I), "Provide pricing details"),
]

TOPIC_RULES = [
    (re.compile(r"\bquote\b", re.I), "Quote"),
    (re.compile(r"\bestimate\b", re.I), "Estimate"),
    (re.compile(r"\bphoto|picture\b", re.I), "Photos"),
    (re.compile(r"\bappointment|schedule\b", re.I), "Appointment"),
    (re.compile(r"\bcall(ing)? (me |him |her |them )?back\b", re.I), "Callback"),
    (re.compile(r"\bfollow[- ]up\b", re.I), "Follow-up"),
    (re.compile(r"\bprice|pricing\b", re.I), "Pricing"),
    (re.compile(r"\brepair|fix|leak|broken\b", re.I), "Repair"),
    (re.compile(r"\breplace|replacement\b", re.I), "Replacement"),
    (re.compile(r"\bemergency|urgent\b", re.I), "Urgent"),
    (re.compile(r"\bcomplain|complaint|unhappy|refund\b", re.I), "Complaint"),
    (re.compile(r"\bthanks?\b|thank you", re.I), "Thanks"),
]


def generate_topics(messages):
    text = " ".join(m["text"] for m in messages)
    return [tag for pattern, tag in TOPIC_RULES if pattern.search(text)]


def generate_todos(messages):
    todos = []
    seen_tasks = set()
    for message in messages:
        for pattern, task in TODO_RULES:
            if task in seen_tasks:
                continue
            if pattern.search(message["text"]):
                seen_tasks.add(task)
                todos.append({"task": task, "source": message["text"][:200]})
    return todos


def search_conversation(messages, query):
    query = (query or "").strip()
    if not query:
        return {"reply": "Type something to search for in this conversation.", "matches": []}

    needle = query.lower()
    matches = [m for m in messages if needle in m["text"].lower()]
    if matches:
        reply = f'Found {len(matches)} mention(s) of "{query}":'
    else:
        reply = f'No matches found for "{query}" in this conversation.'
    return {"reply": reply, "matches": matches}


def _safe_caller_dir(caller_number):
    digits = re.sub(r"[^0-9A-Za-z]", "", caller_number or "unknown")
    return digits or "unknown"


# ---------- conversations (one per call_id in the transcripts table) ----------


def _build_conversation(call_id, rows):
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

    # topics and todos are derived from `messages` we already have in memory, so
    # they cost nothing extra and save the frontend a request per conversation.
    return {
        "id": call_id,
        "caller_number": rows[0]["caller_number"] if rows else "unknown",
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": duration_seconds,
        "message_count": len(messages),
        "preview": preview[:160],
        "topics": generate_topics(messages),
        "todos": generate_todos(messages),
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

    conversations = [_build_conversation(cid, r) for cid, r in grouped.items()]
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
    return _build_conversation(conversation_id, rows)


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


# ---------- request bodies ----------


class ChatRequest(BaseModel):
    message: str


class CallerNameRequest(BaseModel):
    name: str


class NoteRequest(BaseModel):
    text: str


class RenameUploadRequest(BaseModel):
    old_name: str
    new_name: str


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
    """Delete a whole call's transcript (every turn) from CockroachDB."""
    rows = execute_sql(
        "DELETE FROM transcripts WHERE call_id = %s RETURNING id",
        (conversation_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Drop its notes too, so they don't dangle against a deleted call.
    notes = _load_notes()
    if notes.pop(conversation_id, None) is not None:
        _save_notes(notes)

    return {"deleted": conversation_id, "turns_deleted": len(rows)}


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


@router.get("/api/conversations/{conversation_id}/todos")
async def api_conversation_todos(conversation_id: str):
    conversation = get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return generate_todos(conversation["messages"])


@router.get("/api/todos")
async def api_all_todos():
    """Action items across every call. The dashboard gets these from
    /api/conversations now; this stays for direct/API use."""
    return [
        {
            "conversation_id": c["id"],
            "caller_number": c["caller_number"],
            "start_time": c["start_time"],
            "todos": c["todos"],
        }
        for c in list_conversations()
        if c["todos"]
    ]


@router.post("/api/conversations/{conversation_id}/chat")
async def api_conversation_chat(conversation_id: str, body: ChatRequest):
    conversation = get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return search_conversation(conversation["messages"], body.message)


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


# ---------- uploads (still on disk) ----------


@router.get("/api/uploads/{caller_number}")
async def api_list_uploads(caller_number: str):
    upload_dir = UPLOADS_DIR / _safe_caller_dir(caller_number)
    if not upload_dir.is_dir():
        return []
    files = []
    for path in sorted(upload_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.is_file():
            stat = path.stat()
            files.append({
                "name": path.name,
                "size": stat.st_size,
                "uploaded_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
    return files


@router.post("/api/uploads/{caller_number}")
async def api_upload_file(caller_number: str, file: UploadFile = File(...)):
    upload_dir = UPLOADS_DIR / _safe_caller_dir(caller_number)
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = Path(file.filename or "upload").name
    dest = upload_dir / filename
    if dest.exists():
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        dest = upload_dir / f"{stamp}_{filename}"

    with dest.open("wb") as out:
        out.write(await file.read())

    return await api_list_uploads(caller_number)


@router.post("/api/uploads/{caller_number}/rename")
async def api_rename_upload(caller_number: str, body: RenameUploadRequest):
    upload_dir = UPLOADS_DIR / _safe_caller_dir(caller_number)
    old_path = upload_dir / Path(body.old_name).name
    if not old_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    new_name = Path(body.new_name).name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="New name is required")

    new_path = upload_dir / new_name
    if new_path != old_path and new_path.exists():
        raise HTTPException(status_code=409, detail="A file with that name already exists")

    old_path.rename(new_path)
    return await api_list_uploads(caller_number)


# ---------- clients (the customers table) ----------


def _client_record(row):
    return {
        "phone": row["phone_number"],
        "name": row["full_name"] or "",
        "email": row["email"] or "",
        "address": row["address"] or "",
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
    execute_sql(
        """
        INSERT INTO customers (phone_number, full_name)
        VALUES (%s, %s)
        ON CONFLICT (phone_number) DO UPDATE SET full_name = %s, updated_at = now()
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
        return {"phone": phone, "name": "", "email": "", "address": ""}
    return _client_record(row)


@router.post("/api/clients/{phone}")
async def api_update_client(phone: str, body: ClientRequest):
    rows = execute_sql(
        """
        INSERT INTO customers (phone_number, full_name, email, address)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (phone_number) DO UPDATE
            SET full_name = %s, email = %s, address = %s, updated_at = now()
        RETURNING *
        """,
        (
            phone,
            body.name.strip(),
            body.email.strip(),
            body.address.strip(),
            body.name.strip(),
            body.email.strip(),
            body.address.strip(),
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


def register_dashboard(app):
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="dashboard-static")
    app.include_router(router)
