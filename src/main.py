import os
import csv
import json
import base64
import asyncio
import logging
import websockets
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.twiml.voice_response import VoiceResponse, Connect
from dotenv import load_dotenv
from config import (
    HARD_CUTOFF_GRACE_SECONDS, TEMPERATURE, VOICE, SYSTEM_MESSAGE, LOG_EVENT_TYPES, SHOW_TIMING_MATH,
    CALL_LOGS_DIR, PORT, SILENCE_DURATION_MS, VERBOSE, GREETING_MODE,
    VAD_TYPE, VAD_THRESHOLD, VAD_EAGERNESS, VAD_NOISE_REDUCTION,
    MAX_CONVERSATION_TOKENS, WRAP_UP_AT_PERCENT, MAX_CALL_DURATION_SECONDS,
)
from greeting import greeting_twilio, greeting_openai
from dashboard import register_dashboard
import live_calls
from database import (
    configure_database, get_database_transaction,
    save_transcript_turn, generate_call_id,
)
from sms_service import configure_sms_client
from contextlib import asynccontextmanager
from pydantic import ValidationError
from api_models import CallCreate
from routers.calls import insert_call
from routers.customers import get_customer_memory
from post_call_extraction import extract_call_summary

load_dotenv()

logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO').upper(),
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
)
logger = logging.getLogger("voice_assistant")

# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise ValueError('Missing the OpenAI API key.')

os.makedirs(CALL_LOGS_DIR, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("Missing DATABASE_URL.")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER:
    configure_sms_client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER)
else:
    logger.warning("Twilio SMS credentials missing; post-call SMS is disabled.")

# Create the shared CockroachDB "pool" (a no-op wrapper — see database.py's
# configure_database docstring for why there's no real pool anymore).
database_pool = configure_database(DATABASE_URL)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Open the CockroachDB pool when FastAPI starts and close it when
    FastAPI stops.
    """
    await database_pool.open()
    try:
        yield
    finally:
        await database_pool.close()

# Create the FastAPI application and attach the startup/shutdown process.
app = FastAPI(lifespan=lifespan)
register_dashboard(app)

STATIC_DIR = Path(__file__).resolve().parent / "static"

@app.get("/", response_class=HTMLResponse)
async def landing_page():
    """Public marketing front page — see /dashboard for the internal command center."""
    return FileResponse(str(STATIC_DIR / "landing.html"))

@app.get("/status", response_class=JSONResponse)
async def status_page():
    return {"message": "Twilio Media Stream Server is running!"}

@app.get("/health", response_class=JSONResponse)
async def health():
    """Confirm the app can query CockroachDB."""
    try:
        async with get_database_transaction() as connection:
            await connection.execute("SELECT 1")
    except Exception:
        logger.exception("CockroachDB health check failed.")
        return JSONResponse(
            status_code=503,
            content={"application": "degraded", "database": "disconnected"},
        )
    return {"application": "healthy", "database": "connected"}

# Twilio incoming-call route
@app.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    """Handle incoming call and return TwiML response to connect to Media Stream."""
    # I) The caller dials the Twilio number, and Twilio is configured with a
    #    webhook that routes here.
    form_data = await request.form()
    caller_number = form_data.get("From")
    called_number = form_data.get("To")
    logger.info(f"Incoming call from {caller_number} to {called_number}")

    # II) Build the TwiML response: play a greeting (flow depends on
    #     GREETING_MODE in config.py), then attach the media stream, passing
    #     the caller's number through as a custom parameter.
    #
    #     Example output:
    #       <Response>
    #         <Say>Hey there</Say>
    #         <Connect>
    #           <Stream url="wss://your-server.com/media-stream">
    #             <Parameter name="caller_number" value="+15551234567" />
    #           </Stream>
    #         </Connect>
    #       </Response>

    response = VoiceResponse()
    if GREETING_MODE == "twilio":
        greeting_twilio(response)
    else:
        greeting_openai()

    host = request.url.hostname
    connect = Connect()
    stream = connect.stream(url=f'wss://{host}/media-stream')
    stream.parameter(name="caller_number", value=caller_number or "unknown")
    response.append(connect)

    # III) Return the TwiML; Twilio will open a WebSocket to /media-stream to
    #      begin the conversation.
    return HTMLResponse(content=str(response), media_type="application/xml")

# Twilio/OpenAI media-stream WebSocket
@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle WebSocket connections between Twilio and OpenAI."""
    if VERBOSE:
        logger.info("Client connected")
    await websocket.accept()

    # Establish a connection to the OpenAI Realtime API
    # https://developers.openai.com/api/docs/guides/realtime-websocket?connection-example=python
    async with websockets.connect(
        f"wss://api.openai.com/v1/realtime?model=gpt-realtime&temperature={TEMPERATURE}",
        additional_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
    ) as openai_ws:
        await initialize_session(openai_ws)

        # Connection specific state
        stream_sid = None
        latest_media_timestamp = 0
        last_assistant_item = None
        mark_queue = []
        response_start_timestamp_twilio = None
        csv_file = None
        csv_writer = None
        caller_number = None
        call_id = None
        call_started_at = None
        total_response_tokens = 0
        duration_forced = False
        wrap_up_nudged = False
        ending_call = False

        def log_conversation(speaker, text, input_tokens="", output_tokens=""):
            if not text:
                return
            logger.info(f"{caller_number}: {datetime.now().isoformat()}: {speaker}: {text}")

        async def save_conversation_turn(speaker: str, text: str):
            """
            Save one completed caller or assistant transcript turn to CockroachDB.
            """

            cleaned_text = text.strip()

            if not cleaned_text:
                return

            if call_id is None:
                logger.error(
                    "Not saving to CockroachDB: no call_id was generated for this call."
                )
                return

            if not caller_number or caller_number == "unknown":
                logger.error(
                    "Not saving to CockroachDB: caller_number is missing."
                )
                return

            transcript_timestamp = datetime.now(timezone.utc)

            logger.info(
                "%s: %s: %s: %s",
                caller_number,
                transcript_timestamp.isoformat(),
                speaker,
                cleaned_text,
            )

            # stream_sid is read from the enclosing handle_media_stream scope
            # (receive_from_twilio sets it via its own `nonlocal`), so this
            # always sees the current value. Fired before the DB write so the
            # live view keeps working even if CockroachDB is unreachable.
            live_calls.add_turn(stream_sid, speaker, cleaned_text)

            if csv_writer and csv_file and not csv_file.closed:
                try:
                    csv_writer.writerow(
                        [
                            transcript_timestamp.isoformat(),
                            caller_number,
                            speaker,
                            cleaned_text,
                        ]
                    )

                    csv_file.flush()
                except ValueError:
                    logger.warning("CSV already closed; skipping backup write.")

            try:
                # to_thread keeps the blocking DB insert off the event loop —
                # otherwise it stalls the audio streaming for the whole call.
                saved_transcript = await asyncio.to_thread(
                    save_transcript_turn,
                    call_id,
                    transcript_timestamp,
                    caller_number,
                    speaker,
                    cleaned_text,
                )

                logger.info(
                    "DATABASE SAVE SUCCESS | call_id=%s | speaker=%s | transcript_id=%s",
                    saved_transcript["call_id"],
                    saved_transcript["speaker"],
                    saved_transcript["id"],
                )

            except Exception:
                logger.exception(
                    "Failed to save transcript to CockroachDB: "
                    "call_id=%s speaker=%s",
                    call_id,
                    speaker,
                )

        async def receive_from_twilio():
            """Receive audio data from Twilio and send it to the OpenAI Realtime API."""
            nonlocal stream_sid, latest_media_timestamp, csv_file, csv_writer, caller_number, call_id, call_started_at, response_start_timestamp_twilio, last_assistant_item
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    if data['event'] == 'media' and openai_ws.state.name == 'OPEN':
                        latest_media_timestamp = int(data['media']['timestamp'])
                        audio_append = {
                            "type": "input_audio_buffer.append",
                            "audio": data['media']['payload']
                        }
                        await openai_ws.send(json.dumps(audio_append))
                    elif data['event'] == 'start':
                        stream_sid = data['start']['streamSid']
                        caller_number = data['start'].get('customParameters', {}).get('caller_number', 'unknown')

                        # Fires before the generate_call_id DB round trip below (~485ms),
                        # so the dashboard's "someone is calling now" card isn't delayed
                        # by it.
                        live_calls.start_call(stream_sid, caller_number)

                        try:
                            call_id = await asyncio.to_thread(generate_call_id)
                            logger.info(
                                        "Generated live call ID: "
                                        "twilio_stream=%s call_id=%s caller=%s",
                                        stream_sid,
                                        call_id,
                                        caller_number,
                            )
                            live_calls.set_call_id(stream_sid, call_id)
                        except Exception:
                            # Don't let a CockroachDB hiccup take down the call. The
                            # conversation still works; its transcript just won't be
                            # recorded (see save_conversation_turn).
                            logger.exception(
                                "Failed to generate call_id from CockroachDB for stream %s. "
                                "This call's transcript will NOT be recorded.",
                                stream_sid,
                            )
                            call_id = None

                        call_started_at = datetime.now(timezone.utc)
                        live_calls.set_started_at(stream_sid, call_started_at)

                        if VERBOSE:
                            logger.info(f"Incoming stream has started {stream_sid}")
                        response_start_timestamp_twilio = None
                        latest_media_timestamp = 0
                        last_assistant_item = None

                        if caller_number != "unknown":
                            try:
                                returning_customer = await get_customer_memory(caller_number)
                            except Exception:
                                logger.exception(
                                    "Failed to look up returning-caller memory for %s.",
                                    caller_number,
                                )
                                returning_customer = None
                            if returning_customer:
                                logger.info(
                                    "Returning caller matched: caller=%s customer_id=%s",
                                    caller_number, returning_customer["id"],
                                )
                                live_calls.set_returning_caller(stream_sid, returning_customer)
                                await send_returning_caller_context(openai_ws, returning_customer)

                        safe_caller = caller_number.replace('+', '')
                        csv_path = os.path.join(CALL_LOGS_DIR, f"{stream_sid}_{safe_caller}.csv")
                        csv_file = open(csv_path, mode='w', newline='', encoding='utf-8')
                        csv_writer = csv.writer(csv_file)
                        csv_writer.writerow(["timestamp", "caller_number", "speaker", "text"])
                    elif data['event'] == 'mark':
                        if mark_queue:
                            mark_queue.pop(0)
            except (WebSocketDisconnect, RuntimeError):
                if VERBOSE:
                    logger.info("Client disconnected.")
                if openai_ws.state.name == 'OPEN':
                    await openai_ws.close()
            finally:
                # Authoritative end: this finally runs on every exit path out of
                # this loop, whether the caller hung up, an error occurred, or the
                # agent already ended it above. end_call() is idempotent, so it's
                # safe to call again here even if one of the other end_call sites
                # already fired for this stream_sid.
                live_calls.end_call(stream_sid, "disconnected")
                if csv_file:
                    csv_file.close()

        async def send_to_twilio():
            """Receive events from the OpenAI Realtime API, send audio back to Twilio."""
            nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio, call_id, total_response_tokens, wrap_up_nudged, ending_call, duration_forced
            try:
                async for openai_message in openai_ws:
                    event = json.loads(openai_message)
                    if VERBOSE and event['type'] in LOG_EVENT_TYPES:
                        logger.info(f"Received event: {event['type']} {event}")

                    if event.get('type') == 'response.output_audio.delta' and 'delta' in event:
                        audio_payload = base64.b64encode(base64.b64decode(event['delta'])).decode('utf-8')
                        audio_delta = {
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {
                                "payload": audio_payload
                            }
                        }
                        await websocket.send_json(audio_delta)

                        if event.get("item_id") and event["item_id"] != last_assistant_item:
                            response_start_timestamp_twilio = latest_media_timestamp
                            last_assistant_item = event["item_id"]
                            # This branch only fires on the FIRST audio delta of a new
                            # response item — already edge-detected — so this is safe
                            # to call here rather than on every delta.
                            live_calls.set_speaker(stream_sid, "assistant")
                            if SHOW_TIMING_MATH:
                                logger.debug(f"Setting start timestamp for new response: {response_start_timestamp_twilio}ms")

                        await send_mark(websocket, stream_sid)

                    if event.get('type') == 'conversation.item.input_audio_transcription.completed':
                        await save_conversation_turn("caller", event.get('transcript', ''))

                    if event.get('type') == 'response.output_audio_transcript.done':
                        await save_conversation_turn("assistant", event.get('transcript', ''))

                    if event.get('type') == 'response.done':
                        live_calls.set_speaker(stream_sid, "idle")

                        usage = event.get('response', {}).get('usage', {}) or {}

                        input_tokens = usage.get('input_tokens', '')
                        output_tokens = usage.get('output_tokens', '')
                        if usage:
                            log_conversation("usage", "response tokens", input_tokens, output_tokens)

                        total_response_tokens += usage.get('total_tokens', 0)

                        call_duration_seconds = None
                        if call_started_at:
                            call_duration_seconds = (datetime.now(timezone.utc) - call_started_at).total_seconds()

                        token_limit_hit = total_response_tokens >= MAX_CONVERSATION_TOKENS * WRAP_UP_AT_PERCENT
                        duration_limit_hit = (
                            MAX_CALL_DURATION_SECONDS is not None
                            and call_duration_seconds is not None
                            and call_duration_seconds >= MAX_CALL_DURATION_SECONDS
                        )

                        if not wrap_up_nudged and (token_limit_hit or duration_limit_hit):
                            wrap_up_nudged = True
                            logger.info(
                                "Nudging agent to wrap up: tokens=%s duration=%ss",
                                total_response_tokens, call_duration_seconds,
                            )
                            await nudge_agent_to_wrap_up(openai_ws)

                        live_calls.update_metrics(
                            stream_sid,
                            total_response_tokens,
                            int(call_duration_seconds or 0),
                            wrap_up_nudged,
                        )

                        duration_hard_limit_hit = (
                            MAX_CALL_DURATION_SECONDS is not None
                            and call_duration_seconds is not None
                            and call_duration_seconds >= MAX_CALL_DURATION_SECONDS
                        )
                        if not ending_call and not duration_forced and duration_hard_limit_hit:
                            duration_forced = True
                            logger.info("Max call duration reached (%ss); forcing wrap-up.", call_duration_seconds)
                            await force_end_call_now(openai_ws)
                            asyncio.create_task(enforce_hard_duration_cutoff())

                        # --- Handle tool calls ---
                        response_obj = event.get('response', {}) or {}
                        tool_calls = [
                            item for item in response_obj.get('output', [])
                            if item.get('type') == 'function_call'
                        ]

                        if ending_call:
                            await end_call_gracefully(websocket, openai_ws, mark_queue)

                        elif tool_calls:
                            for output_item in tool_calls:
                                tool_name = output_item.get('name')
                                tool_call_id = output_item.get('call_id')
                                try:
                                    tool_args = json.loads(output_item.get('arguments') or '{}')
                                except json.JSONDecodeError:
                                    logger.warning(
                                        "Could not parse tool arguments for %s: %s",
                                        tool_name, output_item.get('arguments'),
                                    )
                                    tool_args = {}

                                if tool_name == 'end_call':
                                    logger.info("Agent requested end_call: %s", tool_args)
                                    ending_call = True
                                    live_calls.end_call(stream_sid, tool_args.get("reason") or "agent_end_call")
                                    await send_tool_result(openai_ws, tool_call_id, {"status": "ending_call"})

                            # Needed even for end_call: the model frequently returns the
                            # function_call with NO accompanying audio/message in that
                            # same response (confirmed in production logs), relying on
                            # this follow-up turn to actually speak the goodbye line the
                            # system prompt asks for ("say ONE short, warm goodbye line
                            # right after"). Skipping this leaves a silent dead-air
                            # hangup instead. The real mid-sentence-cutoff bug was
                            # end_call_gracefully's fixed sleep, not this call — see
                            # its docstring.
                            await openai_ws.send(json.dumps({"type": "response.create"}))

                    # Trigger an interruption. Your use case might work better using `input_audio_buffer.speech_stopped`, or combining the two.
                    if event.get('type') == 'input_audio_buffer.speech_started':
                        if VERBOSE:
                            logger.info("Speech started detected.")
                        # Above the last_assistant_item check so this fires even when
                        # the agent isn't mid-response; barge_in flags the case where
                        # the caller interrupted it.
                        live_calls.set_speaker(stream_sid, "caller", barge_in=bool(last_assistant_item))
                        if last_assistant_item:
                            if VERBOSE:
                                logger.info(f"Interrupting response with id: {last_assistant_item}")
                            await handle_speech_started_event()
            except Exception:
                logger.exception("Error in send_to_twilio")

        async def enforce_hard_duration_cutoff():
            """
            Safety net: if the agent hasn't actually ended the call within the
            grace period after force_end_call_now(), close the connection
            ourselves — don't rely on the model cooperating.
            """
            nonlocal ending_call
            await asyncio.sleep(HARD_CUTOFF_GRACE_SECONDS)
            if not ending_call:
                logger.warning(
                    "Agent did not end the call after the forced wrap-up "
                    "instruction; closing the connection directly."
                )
                ending_call = True
                live_calls.end_call(stream_sid, "duration_cutoff")
                await end_call_gracefully(websocket, openai_ws, mark_queue)

        async def handle_speech_started_event():
            """Handle interruption when the caller's speech starts."""
            nonlocal response_start_timestamp_twilio, last_assistant_item
            if VERBOSE:
                logger.info("Handling speech started event.")
            if mark_queue and response_start_timestamp_twilio is not None:
                # How many ms of the AI's response actually played before the caller interrupted
                elapsed_time = latest_media_timestamp - response_start_timestamp_twilio
                if SHOW_TIMING_MATH:
                    logger.debug(f"Calculating elapsed time for truncation: {latest_media_timestamp} - {response_start_timestamp_twilio} = {elapsed_time}ms")

                if last_assistant_item:
                    if SHOW_TIMING_MATH:
                        logger.debug(f"Truncating item with ID: {last_assistant_item}, Truncated at: {elapsed_time}ms")

                    truncate_event = {
                        "type": "conversation.item.truncate",
                        "item_id": last_assistant_item,
                        "content_index": 0,
                        "audio_end_ms": elapsed_time
                    }
                    await openai_ws.send(json.dumps(truncate_event))

                await websocket.send_json({
                    "event": "clear",
                    "streamSid": stream_sid
                })

                mark_queue.clear()
                last_assistant_item = None
                response_start_timestamp_twilio = None

        async def send_mark(connection, stream_sid):
            if stream_sid:
                mark_event = {
                    "event": "mark",
                    "streamSid": stream_sid,
                    "mark": {"name": "responsePart"}
                }
                await connection.send_json(mark_event)
                mark_queue.append('responsePart')

        await asyncio.gather(receive_from_twilio(), send_to_twilio())

        # Post-call structured extraction — runs after the live conversation
        # has ended, using a separate model (see post_call_extraction.py)
        # instead of having the live OpenAI agent extract it itself mid-call.
        if call_id and caller_number and caller_number != "unknown":
            try:
                extracted = await extract_call_summary(call_id)
                if extracted:
                    await save_structured_call(call_id, caller_number, extracted)
                    live_calls.set_summary(stream_sid, extracted)
                else:
                    live_calls.summary_failed(stream_sid)
            except Exception:
                logger.exception(
                    "Post-call extraction/save failed for call_id=%s", call_id
                )
                live_calls.summary_failed(stream_sid)
        else:
            # No call_id (generate_call_id failed) or no usable caller_number —
            # extraction never runs, so tell the live view not to wait on a
            # summary that's never coming.
            live_calls.summary_failed(stream_sid)

async def send_initial_conversation_item(openai_ws, greeting_text):
    """Send initial conversation item if AI talks first."""
    initial_conversation_item = {
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": greeting_text
                }
            ]
        }
    }
    await openai_ws.send(json.dumps(initial_conversation_item))
    await openai_ws.send(json.dumps({"type": "response.create"}))

def build_realtime_session_update(instructions: str) -> dict:
    """
    Build a full session.update payload instead of an instructions-only
    one, so a mid-call update can never accidentally reset the voice or
    turn-detection settings the call started with.
    """
    return {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "instructions": instructions,
            "audio": {
                "input": {
                    "format": {"type": "audio/pcmu"},
                    "turn_detection": {
                        "type": VAD_TYPE,
                        "silence_duration_ms": SILENCE_DURATION_MS,
                    },
                    "noise_reduction": {"type": VAD_NOISE_REDUCTION},
                },
                "output": {
                    "format": {"type": "audio/pcmu"},
                    "voice": VOICE,
                },
            },
        },
    }

def describe_pending_request(customer: dict) -> str | None:
    """
    Build a line the agent can use to open with the caller's specific
    still-open request, mirroring: "I see you previously called about
    X, and it hasn't been Y yet." Returns None when there's nothing
    open to reference (either no history, or the last request is done).
    """

    open_tasks = customer.get("open_tasks") or []
    last_call = customer.get("last_call")

    if not open_tasks or not last_call:
        return None

    problem = last_call.get("problem") or "your previous request"
    pending_summary = "; ".join(open_tasks)

    return (
        f"I see you previously called about {problem}, and it looks "
        f"like it's still pending: {pending_summary}. Is that still "
        "what you're calling about, and is everything on file still "
        "correct?"
    )

async def send_returning_caller_context(openai_ws, customer):
    """
    Tell the agent exactly what's already on file for this caller and
    instruct it to confirm rather than re-collect: don't run the full
    intake again, just check what's changed.
    """
    known_fields = []
    if customer.get("full_name"):
        known_fields.append(f"name: {customer['full_name']}")
    if customer.get("address"):
        known_fields.append(f"address: {customer['address']}")
    if customer.get("email"):
        known_fields.append(f"email: {customer['email']}")

    last_call = customer.get("last_call")
    if last_call:
        if last_call.get("problem"):
            known_fields.append(f"problem: {last_call['problem']}")
        if last_call.get("problem_detail"):
            known_fields.append(f"problem detail: {last_call['problem_detail']}")
        if last_call.get("availability"):
            known_fields.append(f"availability given: {last_call['availability']}")
        if last_call.get("urgency"):
            known_fields.append(f"urgency noted: {last_call['urgency']}")

    if not known_fields and not customer.get("open_tasks"):
        return  # nothing useful on file — let the normal fresh intake run

    lines = [
        "This is a returning caller. Here is what's already on file — "
        "do NOT ask the caller for any of this again unless they tell "
        "you it has changed: "
        + ("; ".join(known_fields) if known_fields else "(no prior details on file)")
        + ".",
    ]

    pending = describe_pending_request(customer)

    if pending:
        lines.append(
            "Their previous request has not been completed yet. Open "
            f"by referencing it directly — for example: \"{pending}\" "
            "— rather than starting the intake over."
        )
    else:
        lines.append(
            "Their previous request appears to have been completed. "
            "Ask whether this call is about the same thing again or "
            "something new."
        )

    lines.append(
        "Only ask about information that is missing above, or that the "
        "caller tells you has changed. Do not repeat the full intake."
    )

    context_note = " ".join(lines)

    await openai_ws.send(json.dumps(
        build_realtime_session_update(SYSTEM_MESSAGE + "\n\n" + context_note)
    ))

async def nudge_agent_to_wrap_up(openai_ws):
    """Ask the agent to start closing out the call soon."""
    await openai_ws.send(json.dumps(
        build_realtime_session_update(
            SYSTEM_MESSAGE
            + "\n\nThis call is running long. Wrap up the current "
            "topic, confirm any next steps, and say goodbye within "
            "your next couple of turns."
        )
    ))


async def force_end_call_now(openai_ws):
    """
    Hard duration limit reached — stop being polite about it. Tell the
    agent to close the call THIS turn: one short line, then hang up, no
    more questions. Proactively trigger the turn instead of waiting for
    the caller to speak again.
    """
    await openai_ws.send(json.dumps(
        build_realtime_session_update(
            SYSTEM_MESSAGE
            + "\n\nThis call has reached its maximum allowed length. "
            "Do not ask any more questions or continue the "
            "conversation. Right now, say one brief, polite closing "
            "line (e.g. thank them and let them know the team has "
            "what they need or will follow up), then immediately call "
            "end_call."
        )
    ))
    await openai_ws.send(json.dumps({"type": "response.create"}))

async def end_call_gracefully(websocket, openai_ws, mark_queue=None, max_wait_seconds=8.0):
    """
    Give the goodbye line time to actually finish playing over the phone,
    then close the media-stream connection.

    Closing this WebSocket makes Twilio's <Connect><Stream> verb end —
    since nothing follows <Connect> in the TwiML, the call itself hangs up.

    mark_queue holds one entry per audio chunk sent to Twilio that hasn't
    been confirmed played back yet (send_mark appends, the 'mark' event
    handler in receive_from_twilio pops) — waiting for it to drain means we
    wait exactly as long as the goodbye line actually takes, short or long,
    instead of a fixed guess. A fixed 1.5s sleep here used to cut a longer
    goodbye off mid-sentence (and pointlessly delay a short one). Bounded by
    max_wait_seconds in case a mark is ever dropped, so a call can't hang
    open forever.
    """
    if mark_queue is not None:
        waited = 0.0
        poll_interval = 0.1
        while mark_queue and waited < max_wait_seconds:
            await asyncio.sleep(poll_interval)
            waited += poll_interval
    else:
        # No mark_queue available (e.g. called before the stream started) —
        # fall back to the old fixed guess rather than not waiting at all.
        await asyncio.sleep(1.5)

    # Small buffer for the final packet's network transit + actual playback
    # on the caller's phone after Twilio confirms the last mark.
    await asyncio.sleep(0.5)

    if openai_ws.state.name == 'OPEN':
        await openai_ws.close()

    try:
        await websocket.close()
    except RuntimeError:
        pass

async def send_tool_result(openai_ws, tool_call_id, result: dict):
    """Send a function's result back so the agent is unblocked and can continue."""
    if not tool_call_id:
        return
    await openai_ws.send(json.dumps({
        "type": "conversation.item.create",
        "item": {
            "type": "function_call_output",
            "call_id": tool_call_id,
            "output": json.dumps(result),
        },
    }))

async def save_structured_call(call_id, caller_number, arguments):
    """
    Build a CallCreate from the post-call extraction result (see
    post_call_extraction.py) and insert it the same way POST /calls does.
    """
    try:
        call = CallCreate(
            call_id=call_id,
            caller_number=caller_number,
            **arguments,
        )
    except ValidationError:
        logger.exception(
            "Post-call extraction result failed validation: call_id=%s args=%s",
            call_id, arguments,
        )
        return

    try:
        async with get_database_transaction() as connection:
            await insert_call(connection, call)
        logger.info("Saved structured call summary: call_id=%s", call_id)
    except Exception:
        logger.exception("Failed to save structured call summary: call_id=%s", call_id)

async def initialize_session(openai_ws):
    """Control initial session with OpenAI."""
    turn_detection = {"type": VAD_TYPE}
    if VAD_TYPE == "server_vad":
        turn_detection["silence_duration_ms"] = SILENCE_DURATION_MS
        turn_detection["threshold"] = VAD_THRESHOLD
    elif VAD_TYPE == "semantic_vad":
        turn_detection["eagerness"] = VAD_EAGERNESS

    session_update = {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "model": "gpt-realtime",
            "output_modalities": ["audio"],
            "audio": {
                "input": {
                    "format": {"type": "audio/pcmu"},
                    "turn_detection": turn_detection,
                    "noise_reduction": {"type": VAD_NOISE_REDUCTION},
                    "transcription": {"model": "whisper-1"}
                },
                "output": {
                    "format": {"type": "audio/pcmu"},
                    "voice": VOICE
                }
            },
            "instructions": SYSTEM_MESSAGE,
            "tools": [
                {
                    "type": "function",
                    "name": "end_call",
                    "description": (
                        "End the phone call. Call this when the caller has "
                        "clearly said goodbye, the task is fully handled, "
                        "the caller is abusive/spam, or the conversation is "
                        "stuck with no progress after a couple of redirects."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {
                                "type": "string",
                                "enum": [
                                    "caller_said_goodbye",
                                    "task_completed",
                                    "abusive_or_spam",
                                    "no_progress",
                                ],
                            }
                        },
                        "required": ["reason"],
                    },
                },
            ],
        }
    }
    if VERBOSE:
        logger.info(f"Sending session update: {json.dumps(session_update)}")
    await openai_ws.send(json.dumps(session_update))

    if GREETING_MODE == "openai":
        await send_initial_conversation_item(openai_ws, greeting_openai())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)