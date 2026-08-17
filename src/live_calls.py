"""In-memory registry + SSE fan-out for calls in progress.

The dashboard has no way to see a call while it's happening — everything in
main.py's handle_media_stream is a local variable that dies with the socket,
and transcripts only land in CockroachDB turn by turn. This module is the
missing piece: main.py calls the functions below at specific points in the
live call, and any number of dashboard tabs can subscribe to a stream of what
changed.

Design invariants, both load-bearing:

1. Single process, no lock. Every mutator below runs on the asyncio event
   loop thread (main.py's hooks are all inside `async def` bodies), and none
   of them `await` mid-mutation, so there's no interleaving to guard against.
   This is correct today because the app runs as one uvicorn process with no
   --workers (see DEPLOYMENT.md). If that ever changes, this registry needs
   to move to something shared (Redis pub/sub, etc.) — half the dashboard's
   SSE subscribers would otherwise silently stop seeing updates.

2. A broadcast can never break a live phone call. Every function the call
   path invokes is wrapped in @_safe, which logs and swallows. Losing a
   dashboard update is fine; losing a caller is not.
"""
import asyncio
import json
import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger("live_calls")

HEARTBEAT_SECONDS = 15
SUBSCRIBER_QUEUE_MAX = 200
ENDED_CALL_RETENTION_SECONDS = 120
MAX_ACTIVE_CALLS = 20
LIVE_TURN_BUFFER = 40

_calls = {}  # stream_sid -> call record dict
_subscribers = set()  # set[asyncio.Queue[str | None]]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _safe(fn):
    """Log and swallow. See the invariant #2 in the module docstring — every
    public mutator is wrapped in this so a bug here can't take down a call."""
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            logger.exception("live_calls.%s failed — ignoring, the call is unaffected", fn.__name__)
            return None
    wrapper.__name__ = fn.__name__
    return wrapper


def _broadcast(event, data):
    """Fan a server-sent event out to every connected dashboard tab.

    The frame is serialized once, then handed to each subscriber's queue.
    `put_nowait` never blocks — a subscriber whose queue is full (a stalled
    tab, a dead connection FastAPI hasn't noticed yet) gets dropped rather
    than allowed to back-pressure the broadcaster, which runs on the same
    loop as the Twilio<->OpenAI audio relay.
    """
    frame = f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
    dead = []
    for q in _subscribers:
        try:
            q.put_nowait(frame)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        _drop_subscriber(q)


def _drop_subscriber(q):
    _subscribers.discard(q)
    try:
        q.put_nowait(None)  # best-effort: wake the generator so it exits promptly
    except asyncio.QueueFull:
        pass


def _schedule_eviction(stream_sid):
    """Keep an ended call around briefly so a dashboard opened right after it
    hangs up still sees "just ended -> summarizing -> summary" rather than
    nothing."""
    try:
        loop = asyncio.get_running_loop()
        loop.call_later(ENDED_CALL_RETENTION_SECONDS, _calls.pop, stream_sid, None)
    except RuntimeError:
        # No running loop (e.g. called from a script/test) — just drop it now.
        _calls.pop(stream_sid, None)


def _evict_oldest_ended_if_full():
    if len(_calls) < MAX_ACTIVE_CALLS:
        return
    ended = [c for c in _calls.values() if c["ended"]]
    if not ended:
        return
    oldest = min(ended, key=lambda c: c["ended_at"] or "")
    _calls.pop(oldest["stream_sid"], None)


# ---------- public mutators — called from main.py's live call path ----------


@_safe
def start_call(stream_sid, caller_number):
    _evict_oldest_ended_if_full()
    _calls[stream_sid] = {
        "stream_sid": stream_sid,
        "call_id": None,
        "caller_number": caller_number,
        "caller_name": None,
        "returning": False,
        "started_at": None,
        "speaker": "idle",
        "turns": [],
        "turn_count": 0,
        "total_tokens": 0,
        "duration_seconds": 0,
        "wrap_up": False,
        "ended": False,
        "ended_at": None,
        "reason": None,
        "summary_status": None,  # None while live; "pending" | "ready" | "failed" after
        "summary": None,
    }
    _broadcast("call_started", _calls[stream_sid])


@_safe
def set_started_at(stream_sid, started_at):
    """No broadcast — call_started already announced the call; this just
    aligns the dashboard's running-duration clock with the server's."""
    call = _calls.get(stream_sid)
    if call:
        call["started_at"] = started_at.isoformat()


@_safe
def set_call_id(stream_sid, call_id):
    call = _calls.get(stream_sid)
    if not call:
        return
    call["call_id"] = call_id
    _broadcast("call_identified", {
        "stream_sid": stream_sid,
        "call_id": call_id,
        "caller_name": call["caller_name"],
        "returning": call["returning"],
    })


@_safe
def set_returning_caller(stream_sid, customer):
    call = _calls.get(stream_sid)
    if not call:
        return
    call["returning"] = True
    call["caller_name"] = customer.get("full_name") or None
    _broadcast("call_identified", {
        "stream_sid": stream_sid,
        "call_id": call["call_id"],
        "caller_name": call["caller_name"],
        "returning": True,
    })


@_safe
def add_turn(stream_sid, speaker, text):
    call = _calls.get(stream_sid)
    if not call:
        return
    turn = {"speaker": speaker, "text": text, "at": _now_iso()}
    call["turns"].append(turn)
    del call["turns"][:-LIVE_TURN_BUFFER]  # keep only the most recent N
    call["turn_count"] += 1
    _broadcast("transcript_turn", {
        "stream_sid": stream_sid,
        "call_id": call["call_id"],
        "speaker": speaker,
        "text": text,
        "at": turn["at"],
        "turn_count": call["turn_count"],
    })


@_safe
def set_speaker(stream_sid, speaker, barge_in=False):
    call = _calls.get(stream_sid)
    if not call or call["speaker"] == speaker:
        return  # no-op guard: keeps this safe to call on every audio-delta edge
    call["speaker"] = speaker
    _broadcast("speaker_changed", {
        "stream_sid": stream_sid,
        "speaker": speaker,
        "barge_in": bool(barge_in),
        "at": _now_iso(),
    })


@_safe
def update_metrics(stream_sid, total_tokens, duration_seconds, wrap_up):
    call = _calls.get(stream_sid)
    if not call:
        return
    call["total_tokens"] = total_tokens
    call["duration_seconds"] = duration_seconds
    call["wrap_up"] = bool(wrap_up)
    _broadcast("metrics", {
        "stream_sid": stream_sid,
        "total_tokens": total_tokens,
        "duration_seconds": duration_seconds,
        "wrap_up": bool(wrap_up),
    })


@_safe
def end_call(stream_sid, reason):
    call = _calls.get(stream_sid)
    if not call or call["ended"]:
        return  # idempotent: main.py calls this from three different exit paths
    call["ended"] = True
    call["ended_at"] = _now_iso()
    call["reason"] = reason
    call["speaker"] = "idle"
    call["summary_status"] = "pending"
    _broadcast("call_ended", {
        "stream_sid": stream_sid,
        "call_id": call["call_id"],
        "reason": reason,
        "duration_seconds": call["duration_seconds"],
        "turn_count": call["turn_count"],
        "ended_at": call["ended_at"],
    })
    _schedule_eviction(stream_sid)


@_safe
def set_summary(stream_sid, extracted):
    call = _calls.get(stream_sid)
    if not call:
        return
    call["summary_status"] = "ready"
    call["summary"] = extracted
    _broadcast("summary_ready", {
        "stream_sid": stream_sid,
        "call_id": call["call_id"],
        **(extracted or {}),
    })


@_safe
def summary_failed(stream_sid):
    call = _calls.get(stream_sid)
    if not call:
        return
    call["summary_status"] = "failed"
    _broadcast("summary_failed", {"stream_sid": stream_sid, "call_id": call["call_id"]})


# ---------- read side — used by the dashboard, not the call path ----------


def snapshot():
    """Every call currently tracked (active or recently ended), newest-started
    first. Sent as the first event on every new SSE connection so a tab that
    opens mid-call catches up immediately."""
    return sorted(_calls.values(), key=lambda c: c["started_at"] or "", reverse=True)


async def subscribe():
    """An async generator of SSE frames for one dashboard connection.

    `retry: 3000` tells the browser's EventSource how fast to reconnect on
    its own if the connection drops — no client-side reconnect logic needed.
    The heartbeat comment does double duty: it keeps proxies (ngrok, Caddy)
    from idling the connection out, and it guarantees this generator wakes up
    at least every HEARTBEAT_SECONDS, which is when we'd notice the browser
    disconnected and run the `finally` cleanup below. Without it, a
    subscriber that goes quiet (rather than erroring) would leak until the
    next broadcast happened to hit its queue.
    """
    q = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_MAX)
    _subscribers.add(q)
    try:
        yield "retry: 3000\n\n"
        yield f"event: snapshot\ndata: {json.dumps({'calls': snapshot(), 'server_time': _now_iso()}, default=str)}\n\n"
        while True:
            try:
                frame = await asyncio.wait_for(q.get(), timeout=HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue
            if frame is None:
                break
            yield frame
    finally:
        _subscribers.discard(q)
