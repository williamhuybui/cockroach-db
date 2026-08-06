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
from config import TEMPERATURE, VOICE, SYSTEM_MESSAGE, LOG_EVENT_TYPES, SHOW_TIMING_MATH, CALL_LOGS_DIR, PORT, SILENCE_DURATION_MS, VERBOSE, GREETING_MODE
from greeting import greeting_twilio, greeting_openai
from database import configure_database
from embedding_service import configure_embedding_client, close_embedding_client

from contextlib import asynccontextmanager

from routers.health import router as health_router
from routers.transcripts import router as transcripts_router
from routers.customers import router as customers_router
from routers.calls import router as calls_router
from services.transcript_service import create_transcript_turn, generate_call_id

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

# Create the shared CockroachDB connection pool
# The pool will be opened when FastAPI starts.
database_pool = configure_database(DATABASE_URL)

# Create the shared OpenAI client used for transcript embeddings.
configure_embedding_client(OPENAI_API_KEY)

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
        # Close the OpenAI embedding client.
        await close_embedding_client()


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

            # Keep the CSV file as an optional backup.
            if csv_writer:
                csv_writer.writerow(
                    [
                        transcript_timestamp.isoformat(),
                        caller_number,
                        speaker,
                        cleaned_text,
                    ]
                )

                csv_file.flush()

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
                    "Transcript saved to CockroachDB: "
                    "call_id=%s speaker=%s transcript_id=%s",
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
            nonlocal stream_sid, latest_media_timestamp, csv_file, csv_writer, caller_number, call_id, response_start_timestamp_twilio, last_assistant_item
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

                        safe_caller = caller_number.replace('+', '')
                        csv_path = os.path.join(CALL_LOGS_DIR, f"{stream_sid}_{safe_caller}.csv")
                        csv_file = open(csv_path, mode='w', newline='', encoding='utf-8')
                        csv_writer = csv.writer(csv_file)
                        csv_writer.writerow(["timestamp", "caller_number", "speaker", "text"])
                    elif data['event'] == 'mark':
                        if mark_queue:
                            mark_queue.pop(0)
            except WebSocketDisconnect:
                if VERBOSE:
                    logger.info("Client disconnected.")
                if openai_ws.state.name == 'OPEN':
                    await openai_ws.close()
            finally:
                if csv_file:
                    csv_file.close()

        async def send_to_twilio():
            """Receive events from the OpenAI Realtime API, send audio back to Twilio."""
            nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio, call_id
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


async def initialize_session(openai_ws):
    """Control initial session with OpenAI."""
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
