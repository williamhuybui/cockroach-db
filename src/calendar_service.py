import logging
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()

logger = logging.getLogger("voice_assistant")

REPO_ROOT = Path(__file__).resolve().parent.parent

SCOPES = ["https://www.googleapis.com/auth/calendar"]
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")

# The server is normally started with `python src/main.py` from the repo
# root, but this module (and its __main__ block below) is also run directly
# with cwd=src/ — resolve a relative path against REPO_ROOT rather than cwd
# so GOOGLE_SERVICE_ACCOUNT_FILE works the same either way. An absolute path
# is left untouched.
_raw_service_account_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
GOOGLE_SERVICE_ACCOUNT_FILE = (
    str(REPO_ROOT / _raw_service_account_path)
    if _raw_service_account_path and not os.path.isabs(_raw_service_account_path)
    else _raw_service_account_path
)

DEFAULT_EVENT_DURATION = timedelta(hours=1)

_service = None
_warned_not_configured = False


def _get_service():
    global _service, _warned_not_configured

    if _service is not None:
        return _service

    if not GOOGLE_CALENDAR_ID or not GOOGLE_SERVICE_ACCOUNT_FILE:
        if not _warned_not_configured:
            logger.info(
                "Google Calendar not configured (GOOGLE_CALENDAR_ID / "
                "GOOGLE_SERVICE_ACCOUNT_FILE missing) — appointments will "
                "save without a calendar event."
            )
            _warned_not_configured = True
        return None

    try:
        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        _service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    except Exception:
        logger.exception(
            "Failed to load Google Calendar credentials from %s",
            GOOGLE_SERVICE_ACCOUNT_FILE,
        )
        return None

    return _service


def upsert_appointment_event(
    task_id,
    description,
    scheduled_at,
    caller_name=None,
    caller_number=None,
    existing_event_id=None,
    duration_minutes=None,
    note=None,
):

    service = _get_service()
    if service is None:
        return existing_event_id

    duration = timedelta(minutes=duration_minutes) if duration_minutes else DEFAULT_EVENT_DURATION
    who = caller_name or caller_number or "caller"
    description_parts = [description]
    if note:
        description_parts.append(note)
    description_parts.append(f"Caller: {who} ({caller_number or 'unknown'})")
    description_parts.append(f"Task ID: {task_id}")

    body = {
        "summary": f"Appointment: {who}",
        "description": "\n\n".join(description_parts),
        "start": {"dateTime": scheduled_at.isoformat()},
        "end": {"dateTime": (scheduled_at + duration).isoformat()},
    }

    try:
        if existing_event_id:
            event = (
                service.events()
                .update(calendarId=GOOGLE_CALENDAR_ID, eventId=existing_event_id, body=body)
                .execute()
            )
        else:
            event = service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=body).execute()
        return event["id"]
    except Exception:
        logger.exception("Google Calendar upsert failed for task_id=%s", task_id)
        return existing_event_id


def delete_appointment_event(event_id):
    """Best-effort delete — swallows failures (e.g. event already gone)."""
    service = _get_service()
    if service is None or not event_id:
        return
    try:
        service.events().delete(calendarId=GOOGLE_CALENDAR_ID, eventId=event_id).execute()
    except Exception:
        logger.exception("Google Calendar delete failed for event_id=%s", event_id)


if __name__ == "__main__":
    from datetime import datetime, timedelta as _timedelta

    service = _get_service()
    if service is None:
        print(
            "Calendar not configured — set GOOGLE_CALENDAR_ID and "
            "GOOGLE_SERVICE_ACCOUNT_FILE in .env, per the module docstring."
        )
    else:
        when = datetime.now().astimezone() + _timedelta(days=1)
        event_id = upsert_appointment_event(
            task_id="TEST-TASK",
            description="Roof inspection — test event from calendar_service.py",
            scheduled_at=when,
            caller_name="Jane Doe",
            caller_number="+15551234567",
        )
        print(f"Created/updated event {event_id} on {when}")
