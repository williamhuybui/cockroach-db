import os
import csv
import json
import base64
import asyncio
import logging
import websockets
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.twiml.voice_response import VoiceResponse, Connect
from dotenv import load_dotenv
from config import (
    TEMPERATURE, VOICE, SYSTEM_MESSAGE, LOG_EVENT_TYPES, SHOW_TIMING_MATH,
    CALL_LOGS_DIR, PORT, SILENCE_DURATION_MS, VERBOSE, GREETING_MODE,
    VAD_TYPE, VAD_THRESHOLD, VAD_EAGERNESS,
    MAX_CONVERSATION_TOKENS, WRAP_UP_AT_PERCENT, MAX_CALL_DURATION_SECONDS,
)
from greeting import greeting_twilio, greeting_openai
from database import get_database_transaction, configure_database
from sms_service import configure_sms_client 
# from embedding_service import configure_embedding_client, close_embedding_client

from contextlib import asynccontextmanager

from routers.health import router as health_router
from routers.transcripts import router as transcripts_router
from routers.customers import router as customers_router
from routers.calls import router as calls_router
from services.transcript_service import create_transcript_turn, generate_call_id
from routers.customers import router as customers_router, find_customer_by_phone
from api_models import CallCreate
from database import configure_database, get_database_transaction
from routers.calls import insert_call
from pydantic import ValidationError

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
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")

if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER:
    configure_sms_client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER)
else:
    logger.warning("Twilio SMS credentials missing; post-call SMS is disabled.")

# Create the shared CockroachDB connection pool
# The pool will be opened when FastAPI starts.
database_pool = configure_database(DATABASE_URL)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Open the CockroachDB pool when FastAPI starts and close it when
    FastAPI stops.
    """

    # Start the database connections before accepting requests.
    await database_pool.open()

    try:
        # FastAPI serves requests while execution remains here.
        yield
    finally:
        # Release database connections during shutdown or restart.
        await database_pool.close()

# Create the FastAPI application and attach the startup/shutdown process.
app = FastAPI(lifespan=lifespan)

# Register the new database-backed REST endpoints
app.include_router(health_router)
app.include_router(transcripts_router)
app.include_router(customers_router)
app.include_router(calls_router)

# Basic application route
@app.get("/", response_class=JSONResponse)
async def index_page():
    return {"message": "Twilio Media Stream Server is running!"}

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
        wrap_up_nudged = False      
        ending_call = False  
        
        def log_conversation(speaker, text):
            if not text:
                return
            logger.info(f"{caller_number}: {datetime.now().isoformat()}: {speaker}: {text}")
            if csv_writer:
                csv_writer.writerow([datetime.now().isoformat(), caller_number, speaker, text])
                csv_file.flush()

        async def save_conversation_turn(speaker: str, text: str):
            """
            Save one completed caller or assistant transcript turn.
            """

            cleaned_text = text.strip()

            if not cleaned_text:
                return

            if call_id is None:
                logger.error(
                    "Cannot save transcript because call_id has not been generated."
                )
                return

            if not caller_number or caller_number == "unknown":
                logger.error(
                    "Cannot save transcript because caller_number is missing."
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
                saved_transcript = await create_transcript_turn(
                    call_id=call_id,
                    timestamp=transcript_timestamp,
                    caller_number=caller_number,
                    speaker=speaker,
                    text=cleaned_text,
                )

                if saved_transcript is None:
                    logger.warning("Transcript service returned no saved record.")
                    return

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
                        call_id = await generate_call_id()
                        call_started_at = datetime.now(timezone.utc)
                        logger.info(
                                    "Generated live call ID: "
                                    "twilio_stream=%s call_id=%s caller=%s",
                                    stream_sid,
                                    call_id,
                                    caller_number,
                        )
                        if VERBOSE:
                            logger.info(f"Incoming stream has started {stream_sid}")
                        response_start_timestamp_twilio = None
                        latest_media_timestamp = 0
                        last_assistant_item = None

                        if caller_number != "unknown":
                            returning_customer = await find_customer_by_phone(caller_number)
                            if returning_customer:
                                logger.info(
                                    "Returning caller matched: caller=%s customer_id=%s",
                                    caller_number, returning_customer["id"],
                                )
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
                if csv_file:
                    csv_file.close()

        async def send_to_twilio():
            """Receive events from the OpenAI Realtime API, send audio back to Twilio."""
            nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio, call_id, total_response_tokens, wrap_up_nudged, ending_call
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
                            if SHOW_TIMING_MATH:
                                logger.debug(f"Setting start timestamp for new response: {response_start_timestamp_twilio}ms")

                        await send_mark(websocket, stream_sid)

                    if event.get('type') == 'conversation.item.input_audio_transcription.completed':
                        await save_conversation_turn("caller", event.get('transcript', ''))

                    if event.get('type') == 'response.output_audio_transcript.done':
                        await save_conversation_turn("assistant", event.get('transcript', ''))

                    if event.get('type') == 'response.done':
                        usage = event.get('response', {}).get('usage', {}) or {}
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

                        # --- Handle tool calls ---
                        response_obj = event.get('response', {}) or {}
                        tool_calls = [
                            item for item in response_obj.get('output', [])
                            if item.get('type') == 'function_call'
                        ]

                        if ending_call:
                            await end_call_gracefully(websocket, openai_ws)

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
                                    await send_tool_result(openai_ws, tool_call_id, {"status": "ending_call"})

                                elif tool_name == 'save_call_summary':
                                    logger.info("Agent requested save_call_summary: %s", tool_args)
                                    await save_structured_call(call_id, caller_number, tool_args)
                                    await send_tool_result(openai_ws, tool_call_id, {"status": "saved"})

                            await openai_ws.send(json.dumps({"type": "response.create"}))
                

                    # Trigger an interruption. Your use case might work better using `input_audio_buffer.speech_stopped`, or combining the two.
                    if event.get('type') == 'input_audio_buffer.speech_started':
                        if VERBOSE:
                            logger.info("Speech started detected.")
                        if last_assistant_item:
                            if VERBOSE:
                                logger.info(f"Interrupting response with id: {last_assistant_item}")
                            await handle_speech_started_event()
            except Exception:
                logger.exception("Error in send_to_twilio")

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

async def send_returning_caller_context(openai_ws, customer):
    """Tell the agent what we already have on file for this caller."""
    known_bits = []
    if customer.get("full_name"):
        known_bits.append(f"name on file: {customer['full_name']}")
    if customer.get("address"):
        known_bits.append(f"address on file: {customer['address']}")

    if not known_bits:
        return

    context_note = (
        "This is a returning caller. We have this on file: "
        + "; ".join(known_bits)
        + ". Greet them by name if it feels natural, and confirm the "
        "name and address are still correct before proceeding — don't "
        "just assume it's unchanged."
    )

    await openai_ws.send(json.dumps({
        "type": "session.update",
        "session": {
            "type": "realtime",
            "instructions": SYSTEM_MESSAGE + "\n\n" + context_note,
        },
    }))

async def nudge_agent_to_wrap_up(openai_ws):
    """Ask the agent to start closing out the call soon."""
    await openai_ws.send(json.dumps({
        "type": "session.update",
        "session": {
            "type": "realtime",
            "instructions": (
                SYSTEM_MESSAGE
                + "\n\nThis call is running long. Wrap up the current "
                "topic, confirm any next steps, and say goodbye within "
                "your next couple of turns."
            ),
        },
    }))

async def end_call_gracefully(websocket, openai_ws):
    """
    Give the goodbye line time to finish playing over the phone, then
    close the media-stream connection.

    Closing this WebSocket makes Twilio's <Connect><Stream> verb end —
    since nothing follows <Connect> in the TwiML, the call itself hangs up.
    """
    # audio for the goodbye line was already streamed to Twilio in this
    # same response, before response.done fired — this just gives it a
    # moment to actually finish playing over the phone line.
    await asyncio.sleep(1.5)

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
    Build a CallCreate from the agent's save_call_summary tool call and
    insert it the same way POST /calls does.
    """
    try:
        call = CallCreate(
            call_id=call_id,
            caller_number=caller_number,
            **arguments,
        )
    except ValidationError:
        logger.exception(
            "save_call_summary arguments failed validation: call_id=%s args=%s",
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
                    "turn_detection": {"type": "server_vad", "silence_duration_ms": SILENCE_DURATION_MS},
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
                {
                    "type": "function",
                    "name": "save_call_summary",
                    "description": (
                        "Save a structured summary of this call for the business to "
                        "review. Call this once, right before end_call, with whatever "
                        "the caller was willing to share — it's fine to leave fields "
                        "out if unknown."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Caller's full name, or the property owner's name if calling on someone else's behalf.",
                            },
                            "email": {"type": "string", "description": "Caller's email, if provided."},
                            "address": {"type": "string", "description": "Property address needing service."},
                            "problem": {
                                "type": "string",
                                "description": "Short label, e.g. 'Roof leak', 'Missing shingles', 'Storm damage'.",
                            },
                            "problem_detail": {
                                "type": "string",
                                "description": "More specific detail: where, how long, likely cause.",
                            },
                            "availability": {"type": "string", "description": "Days/times that work for a visit or callback."},
                            "urgency": {
                                "type": "string",
                                "enum": ["Low", "Medium", "High", "Emergency"],
                            },
                            "calling_on_behalf_of": {
                                "type": "string",
                                "description": "Set only if the caller is calling on someone else's behalf.",
                            },
                            "summary": {
                                "type": "string",
                                "description": (
                                    "1-3 sentence plain-language summary for the business "
                                    "owner: what the caller needed and what was agreed."
                                ),
                            },
                        },
                        "required": ["summary", "urgency"],
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