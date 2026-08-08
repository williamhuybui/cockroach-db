from config import COMPANY_NAME
# Two ways to handle the greeting:
# 1) Twilio's built-in <Say> verb
# Pro: the caller can't interrupt it, and it's easy to switch voices per language.
# Con: requires more hardcoded logic to design.
CALL_DURATION_MINUTES = 10

def greeting_twilio(response):
    """Add the hardcoded <Say> greeting lines to a TwiML VoiceResponse."""
    response.say(
        f"Thank you for calling {COMPANY_NAME}. "
        "This call may be recorded for staff training and quality "
        f"assurance. To help us serve everyone quickly, we try to keep "
        f"calls to about {CALL_DURATION_MINUTES} minutes — if we can't "
        "fully resolve your issue by then, I'll pass your details to a "
        "team member who will call you back.",
        voice="Google.en-US-Chirp3-HD-Aoede"
    )
    response.pause(length=1)
    response.say(
        "Quý khách có thể nói tiếng Việt nếu cần hỗ trợ.",
        voice="Google.vi-VN-Chirp3-HD-Aoede"
    )
    response.pause(length=1)
    response.say(
        "How can I help you today?"
    )

# 2) OpenAI Realtime API greeting
# Pro: stays in the same conversational flow as the rest of the call.
# Con: the caller can interrupt it, and it may say something unpredictable.
def greeting_openai():
    """Instruction text used to make the AI greet the caller first, once the
    media stream connects (see send_initial_conversation_item in main.py)."""
    return (
        f"Say: Thank you for calling {COMPANY_NAME}. This call may be "
        "recorded for staff training and quality assurance. To help us "
        f"serve everyone quickly, we try to keep calls to about "
        f"{CALL_DURATION_MINUTES} minutes — if we can't fully resolve "
        "your issue by then, I'll pass your details to a team member who "
        "will call you back. How can I help you today?"
    )