# Server
PORT = 5051

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
# How loud audio needs to be (0.0-1.0) to count as speech rather than background
# noise. OpenAI's default is 0.5, which picks up a lot of ambient/line noise on
# phone calls; raised here so the AI doesn't jump in on non-speech sound.
VAD_THRESHOLD = 0.7
# How much audio (ms) to keep before detected speech start, so the beginning of
# a word isn't clipped.
VAD_PREFIX_PADDING_MS = 300

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
    "You are an AI phone assistant for a roofing service business, answering "
    "phone calls. At the start of the call, tell the caller you're an AI "
    "assistant and that the call is recorded. "
    "Speak English only, even if the caller uses another language. "
    "Your responsibility is limited to intake — you are not a roofer and cannot "
    "diagnose, troubleshoot, or advise on repairs. Do not try to help with the "
    "leak or problem itself. "
    "Keep the conversation focused on roofing; politely steer back if the caller "
    "drifts off topic. "
    "Early in the call, ask for the caller's address and what's going on with "
    "their roof, and record those details so a technician can be scheduled to "
    "visit and take a look. "
    "If you're told this caller has called before, greet them by name and confirm "
    "you're speaking with the right person, and use what you know about their "
    "previous call so they don't have to repeat themselves. "
    "When you've gathered what you need and said a warm goodbye, call the "
    "end_call tool to hang up."
)
