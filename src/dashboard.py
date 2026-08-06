import csv
import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
# call logs have shown up in both locations because CALL_LOGS_DIR in config.py
# is a relative path resolved from whatever directory the server was started in.
CALL_LOG_DIRS = [BASE_DIR / "call_logs", REPO_ROOT / "call_logs"]
UPLOADS_DIR = REPO_ROOT / "uploads"
STATIC_DIR = BASE_DIR / "static"
CALLER_NAMES_FILE = REPO_ROOT / "caller_names.json"
NOTES_FILE = REPO_ROOT / "notes.json"
CLIENTS_FILE = REPO_ROOT / "clients.json"

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
    tags = []
    for pattern, tag in TOPIC_RULES:
        if pattern.search(text):
            tags.append(tag)
    return tags


def _safe_caller_dir(caller_number):
    digits = re.sub(r"[^0-9A-Za-z]", "", caller_number or "unknown")
    return digits or "unknown"


def _iter_csv_files():
    seen = set()
    for log_dir in CALL_LOG_DIRS:
        if not log_dir.is_dir():
            continue
        for path in sorted(log_dir.glob("*.csv")):
            if path.stem in seen:
                continue
            seen.add(path.stem)
            yield path


def _parse_conversation(path):
    stem = path.stem
    _, _, digits = stem.rpartition("_")
    fallback_caller = f"+{digits}" if digits else "unknown"

    messages = []
    caller_number = None
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            timestamp = row.get("timestamp", "")
            text = (row.get("text") or "").strip()
            speaker = row.get("speaker", "")
            row_caller = row.get("caller_number")
            if row_caller and not caller_number:
                caller_number = row_caller
            if not text:
                continue
            messages.append({"timestamp": timestamp, "speaker": speaker, "text": text})

    if not caller_number:
        caller_number = fallback_caller

    start_time = messages[0]["timestamp"] if messages else None
    end_time = messages[-1]["timestamp"] if messages else None
    duration_seconds = 0
    if start_time and end_time:
        try:
            duration_seconds = round(
                (datetime.fromisoformat(end_time) - datetime.fromisoformat(start_time)).total_seconds()
            )
        except ValueError:
            duration_seconds = 0

    preview = next((m["text"] for m in messages if m["speaker"] == "caller"), None)
    if preview is None:
        preview = messages[0]["text"] if messages else ""

    return {
        "id": stem,
        "caller_number": caller_number,
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": duration_seconds,
        "message_count": len(messages),
        "preview": preview[:160],
        "topics": generate_topics(messages),
        "messages": messages,
    }


def list_conversations():
    conversations = [_parse_conversation(path) for path in _iter_csv_files()]
    conversations.sort(key=lambda c: c["start_time"] or "", reverse=True)
    return conversations


def get_conversation(conversation_id):
    for path in _iter_csv_files():
        if path.stem == conversation_id:
            return _parse_conversation(path)
    return None


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


def _load_json_file(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_json_file(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_caller_names():
    return _load_json_file(CALLER_NAMES_FILE)


def _load_notes():
    return _load_json_file(NOTES_FILE)


def _save_notes(notes):
    _save_json_file(NOTES_FILE, notes)


def _load_clients():
    clients = _load_json_file(CLIENTS_FILE)
    if not clients and CALLER_NAMES_FILE.exists():
        # one-time migration from the earlier caller-name-only store
        legacy_names = _load_caller_names()
        clients = {phone: {"name": name, "email": "", "address": ""} for phone, name in legacy_names.items()}
        if clients:
            _save_json_file(CLIENTS_FILE, clients)
    return clients


def _save_clients(clients):
    _save_json_file(CLIENTS_FILE, clients)


def _client_record(clients, phone):
    record = clients.get(phone, {})
    return {
        "phone": phone,
        "name": record.get("name", ""),
        "email": record.get("email", ""),
        "address": record.get("address", ""),
    }


@router.get("/api/conversations")
async def api_list_conversations():
    return [{k: v for k, v in c.items() if k != "messages"} for c in list_conversations()]


@router.get("/api/conversations/{conversation_id}")
async def api_get_conversation(conversation_id: str):
    conversation = get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.get("/api/conversations/{conversation_id}/todos")
async def api_conversation_todos(conversation_id: str):
    conversation = get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return generate_todos(conversation["messages"])


@router.get("/api/todos")
async def api_all_todos():
    grouped = []
    for conversation in list_conversations():
        todos = generate_todos(conversation["messages"])
        if todos:
            grouped.append({
                "conversation_id": conversation["id"],
                "caller_number": conversation["caller_number"],
                "start_time": conversation["start_time"],
                "todos": todos,
            })
    return grouped


@router.post("/api/conversations/{conversation_id}/chat")
async def api_conversation_chat(conversation_id: str, body: ChatRequest):
    conversation = get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return search_conversation(conversation["messages"], body.message)


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


@router.get("/api/callers/names")
async def api_caller_names():
    clients = _load_clients()
    return {phone: record.get("name", "") for phone, record in clients.items() if record.get("name")}


@router.post("/api/callers/{caller_number}/name")
async def api_set_caller_name(caller_number: str, body: CallerNameRequest):
    clients = _load_clients()
    record = clients.setdefault(caller_number, {"name": "", "email": "", "address": ""})
    record["name"] = body.name.strip()
    _save_clients(clients)
    return {phone: r.get("name", "") for phone, r in clients.items() if r.get("name")}


@router.get("/api/clients")
async def api_list_clients():
    clients = _load_clients()
    stats = {}
    for conversation in list_conversations():
        phone = conversation["caller_number"]
        entry = stats.setdefault(phone, {"call_count": 0, "last_call": None})
        entry["call_count"] += 1
        if not entry["last_call"] or (conversation["start_time"] or "") > entry["last_call"]:
            entry["last_call"] = conversation["start_time"]

    phones = set(clients.keys()) | set(stats.keys())
    result = []
    for phone in phones:
        record = _client_record(clients, phone)
        record["call_count"] = stats.get(phone, {}).get("call_count", 0)
        record["last_call"] = stats.get(phone, {}).get("last_call")
        result.append(record)

    result.sort(key=lambda r: r["last_call"] or "", reverse=True)
    return result


@router.post("/api/clients")
async def api_create_client(body: NewClientRequest):
    phone = body.phone.strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")
    clients = _load_clients()
    clients[phone] = {"name": body.name.strip(), "email": body.email.strip(), "address": body.address.strip()}
    _save_clients(clients)
    return _client_record(clients, phone)


@router.get("/api/clients/{phone}")
async def api_get_client(phone: str):
    clients = _load_clients()
    return _client_record(clients, phone)


@router.post("/api/clients/{phone}")
async def api_update_client(phone: str, body: ClientRequest):
    clients = _load_clients()
    clients[phone] = {"name": body.name.strip(), "email": body.email.strip(), "address": body.address.strip()}
    _save_clients(clients)
    return _client_record(clients, phone)


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
