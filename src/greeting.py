
# Two ways to handle the greeting:
# 1) Twilio's built-in <Say> verb
# Pro: the caller can't interrupt it, and it's easy to switch voices per language.
# Con: requires more hardcoded logic to design.
def greeting_twilio(response):
    """Add the hardcoded <Say> greeting lines to a TwiML VoiceResponse."""
    response.say(
        "Thanks for calling our roofing team. Just so you know, I'm an AI "
        "assistant, and this call is recorded.",
        voice="Google.en-US-Chirp3-HD-Aoede"
    )
    response.pause(length=1)
    response.say(
        "I can't come out and fix anything myself, but I can take down what's "
        "going on and your address so we can get a technician scheduled to come "
        "take a look. What's going on with your roof?"
    )

# 2) OpenAI Realtime API greeting
# Pro: stays in the same conversational flow as the rest of the call.
# Con: the caller can interrupt it, and it may say something unpredictable.
def greeting_openai():
    """Instruction text used to make the AI greet the caller first, once the
    media stream connects (see send_initial_conversation_item in main.py)."""
    return (
        "Say: Thanks for calling our roofing team. I'm an AI assistant, and this "
        "call is recorded. I can't fix anything myself, but I can take down "
        "what's going on and get a technician scheduled to come take a look — "
        "what's going on with your roof?"
    )