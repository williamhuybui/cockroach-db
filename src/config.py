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

# Embedding configuration
# Model used later to generate transcript embeddings for semantic search.
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
# This must match the VECTOR(1536) column in CockroachDB.
OPENAI_EMBEDDING_DIMENSIONS = 1536
# Maximum time to wait for an OpenAI embedding request.
OPENAI_REQUEST_TIMEOUT_SECONDS = 30

# Database connection pool
# Allow up to 3 concurrent connections to the database
DATABASE_POOL_MIN_SIZE = 1
DATABASE_POOL_MAX_SIZE = 3

# Prompt
SYSTEM_MESSAGE = (
    "You are a helpful and bubbly AI assistant who loves to chat about "
)
