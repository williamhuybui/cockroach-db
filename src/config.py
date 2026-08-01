# Server
PORT = 5050

# Model
TEMPERATURE = 0.7
VOICE = 'alloy'
LOG_EVENT_TYPES = [
    'error', 'response.content.done', 'rate_limits.updated',
    'response.done', 'input_audio_buffer.committed',
    'input_audio_buffer.speech_stopped', 'input_audio_buffer.speech_started',
    'session.created', 'session.updated'
]
SHOW_TIMING_MATH = False
CALL_LOGS_DIR = "call_logs"
SILENCE_DURATION_MS = 1000

# Logging
# True: log everything (connections, raw events, timing, etc.).
# False: log only "phone_number: time: conversation" lines.
VERBOSE = False

# Greeting
# "twilio": hardcoded <Say> greeting, played before the AI connects.
# "openai": AI greets the caller itself once the media stream connects.
# See greeting.py for the actual greeting text used by each mode.
GREETING_MODE = "twilio"

# Prompt
SYSTEM_MESSAGE = (
    "You are a helpful and bubbly AI assistant who loves to chat about "
)
