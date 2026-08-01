# Troubleshooting & Notes

## ngrok URL changed and the call doesn't connect

Every time you restart `ngrok http 5050`, it generates a new forwarding URL. Update the webhook under **Phone Numbers > Manage > Active Numbers** in the [Twilio Console](https://console.twilio.com/) each time, or use a paid ngrok plan with a static domain.

## "Missing the OpenAI API key" error on startup

`OPENAI_API_KEY` isn't set. Make sure `.env` exists in the repo root (not `src/`) and contains `OPENAI_API_KEY=...`, then restart the server.

## Call connects but there's no audio / it hangs up immediately

- Confirm the webhook path is `/incoming-call`, not just the bare ngrok URL.
- Confirm the local server is actually running on port 5050 (`PORT` in `src/config.py`) and ngrok is forwarding to that same port.
- Check the terminal running `python src/main.py` for errors — OpenAI Realtime API access issues usually show up here.

## Where are call transcripts?

Written to `src/call_logs/`, one entry per call.

## Have the AI speak first instead of the caller

Set `GREETING_MODE = "openai"` in `src/config.py` (default is `"twilio"`, a hardcoded greeting played before the AI connects). See `src/greeting.py` for the actual greeting text used by each mode.

## Interrupt handling

When the caller starts speaking mid-response, OpenAI sends `input_audio_buffer.speech_started`; the app clears the Twilio Media Stream buffer and sends OpenAI `conversation.item.truncate` so the AI stops and listens. If you need different behavior, look at the `input_audio_buffer.speech_stopped` event instead of (or combined with) `speech_started`.

## Outbound calling

Not supported by this app — it only handles inbound calls to your Twilio number.

## Verbose logging

Set `VERBOSE = True` in `src/config.py` to log everything (raw events, timing, connections). Default (`False`) logs only `phone_number: time: conversation` lines.
