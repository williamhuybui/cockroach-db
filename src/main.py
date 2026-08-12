import os
import csv
import json
import base64
import asyncio
import logging
import websockets
from datetime import datetime
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.twiml.voice_response import VoiceResponse, Connect
from twilio.rest import Client as TwilioRestClient
from dotenv import load_dotenv
from config import TEMPERATURE, VOICE, SYSTEM_MESSAGE, LOG_EVENT_TYPES, SHOW_TIMING_MATH, CALL_LOGS_DIR, PORT, SILENCE_DURATION_MS, VAD_THRESHOLD, VAD_PREFIX_PADDING_MS, VERBOSE, GREETING_MODE
from greeting import greeting_twilio, greeting_openai
from dashboard import register_dashboard, get_caller_context
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
# Optional: only needed for the AI to hang up the call itself (see end_call tool below).
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
os.makedirs(CALL_LOGS_DIR, exist_ok=True)

app = FastAPI()
register_dashboard(app)

@app.get("/", response_class=JSONResponse)
async def index_page():
    return {"message": "Twilio Media Stream Server is running!"}

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
        call_sid = None
        end_call_requested = False

        async def hang_up_call():
            """End the underlying Twilio call via the REST API (used by the end_call tool)."""
            if not call_sid:
                logger.warning("end_call requested but no CallSid captured yet; ignoring.")
                return
            if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN):
                logger.warning("end_call requested but TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN are not set; ignoring.")
                return
            twilio_client = TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            try:
                await asyncio.to_thread(twilio_client.calls(call_sid).update, status="completed")
                logger.info(f"Hung up call {call_sid} via end_call tool.")
            except Exception:
                logger.exception(f"Failed to hang up call {call_sid}.")

        def log_conversation(speaker, text):
            if not text:
                return
            logger.info(f"{caller_number}: {datetime.now().isoformat()}: {speaker}: {text}")
            if csv_writer:
                csv_writer.writerow([datetime.now().isoformat(), caller_number, speaker, text])
                csv_file.flush()

        async def receive_from_twilio():
            """Receive audio data from Twilio and send it to the OpenAI Realtime API."""
            nonlocal stream_sid, latest_media_timestamp, csv_file, csv_writer, caller_number, call_sid, response_start_timestamp_twilio, last_assistant_item
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
                        call_sid = data['start'].get('callSid')
                        caller_number = data['start'].get('customParameters', {}).get('caller_number', 'unknown')
                        if VERBOSE:
                            logger.info(f"Incoming stream has started {stream_sid}")
                        await update_session_context(openai_ws, caller_number)
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
            nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio, end_call_requested
            try:
                async for openai_message in openai_ws:
                    event = json.loads(openai_message)
                    if VERBOSE and event['type'] in LOG_EVENT_TYPES:
                        logger.info(f"Received event: {event['type']} {event}")

                    # The model calls this once it's said goodbye and the conversation
                    # is over. Don't hang up immediately — let the goodbye audio finish
                    # streaming to Twilio first (response.done below).
                    if event.get('type') == 'response.output_item.done':
                        item = event.get('item', {})
                        if item.get('type') == 'function_call' and item.get('name') == 'end_call':
                            end_call_requested = True

                    if event.get('type') == 'response.done' and end_call_requested:
                        # All of the goodbye's audio has been sent to Twilio, but it
                        # may not have finished playing to the caller yet. Twilio
                        # echoes back a 'mark' event for each chunk once it's
                        # actually played (see mark_queue / send_mark), so wait for
                        # that queue to drain before hanging up — otherwise we risk
                        # cutting the sentence off mid-word.
                        for _ in range(100):  # ~10s safety timeout
                            if not mark_queue:
                                break
                            await asyncio.sleep(0.1)
                        await hang_up_call()
                        return

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
                        log_conversation("caller", event.get('transcript', '').strip())

                    if event.get('type') == 'response.output_audio_transcript.done':
                        log_conversation("assistant", event.get('transcript', '').strip())

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

async def update_session_context(openai_ws, caller_number):
    """Once we know who's calling, patch the session's instructions with what we
    know about them, so the model can recognize a repeat caller and pick up where
    the previous conversation left off. Note: with GREETING_MODE == "openai", the
    very first greeting is generated in initialize_session() before this runs, so
    it won't have this context yet."""
    context = get_caller_context(caller_number)

    if context["call_count"]:
        lines = [
            f"This caller has called before and is known as {context['name'] or 'unnamed'}. "
            "Greet them by name and confirm you're speaking with the right person."
        ]
        if context["address"]:
            lines.append(f"Address on file: {context['address']}.")
        last_call = context["last_call"]
        if last_call:
            lines.append(
                f"Their most recent call was about: \"{last_call['preview']}\" "
                f"(topics: {', '.join(last_call['topics']) or 'none noted'})."
            )
            if last_call["notes"]:
                lines.append(f"Notes from that call: {'; '.join(last_call['notes'])}.")
    else:
        lines = ["This is a new caller — you have no history for them yet."]

    session_update = {
        "type": "session.update",
        "session": {"instructions": SYSTEM_MESSAGE + "\n\n" + "\n".join(lines)},
    }
    if VERBOSE:
        logger.info(f"Updating session with caller context: {json.dumps(session_update)}")
    await openai_ws.send(json.dumps(session_update))

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
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": VAD_THRESHOLD,
                        "prefix_padding_ms": VAD_PREFIX_PADDING_MS,
                        "silence_duration_ms": SILENCE_DURATION_MS,
                    },
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
                        "Call this once you have said goodbye and the conversation is "
                        "genuinely over, to hang up the call. Do not call it before "
                        "saying goodbye."
                    ),
                    "parameters": {"type": "object", "properties": {}, "required": []},
                }
            ],
            "tool_choice": "auto",
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
