from config import COMPANY_NAME
# Two ways to handle the greeting:
# 1) Twilio's built-in <Say> verb
# Pro: the caller can't interrupt it, and it's easy to switch voices per language.
# Con: requires more hardcoded logic to design.
CALL_DURATION_MINUTES = 5

# Split in two so greeting_twilio can pause between them (a beat before "How
# can I help you today?" reads more natural over the phone) — GREETING_TEXT
# below joins them back into the one string every other caller of this
# module needs (transcript/live-feed display, the openai-mode instruction).
_GREETING_INTRO = (
    f"Thank you for calling {COMPANY_NAME}. "
    "This call may be recorded for staff training and quality "
    f"assurance. To help us serve everyone quickly, we try to keep "
    f"calls to about {CALL_DURATION_MINUTES} minutes — if we can't "
    "fully resolve your issue by then, I'll pass your details to a "
    "team member who will call you back."
)
_GREETING_QUESTION = "How can I help you today?"

# What the caller actually hears, as one string — in twilio mode this is
# logged as the call's opening transcript turn (see main.py's
# receive_from_twilio) since Twilio's own <Say> never produces one on its
# own; in openai mode it's the instruction handed to the model.
GREETING_TEXT = f"{_GREETING_INTRO} {_GREETING_QUESTION}"


def greeting_twilio(response):
    """Add the hardcoded <Say> greeting lines to a TwiML VoiceResponse."""
    response.say(_GREETING_INTRO, voice="Google.en-US-Chirp3-HD-Aoede")
    response.pause(length=1)
    response.say(_GREETING_QUESTION)

# 2) OpenAI Realtime API greeting
# Pro: stays in the same conversational flow as the rest of the call.
# Con: the caller can interrupt it, and it may say something unpredictable.
def greeting_openai():
    """Instruction text used to make the AI greet the caller first, once the
    media stream connects (see send_initial_conversation_item in main.py)."""
    return f"Say: {GREETING_TEXT}"