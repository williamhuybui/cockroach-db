
# Two ways to handle the greeting:
# 1) Twilio's built-in <Say> verb
# Pro: the caller can't interrupt it, and it's easy to switch voices per language.
# Con: requires more hardcoded logic to design.
def greeting_twilio(response):
    """Add the hardcoded <Say> greeting lines to a TwiML VoiceResponse."""
    response.say(
        "Hey, welcome to The Front Desk That Never Sleeps.",
        voice="Google.en-US-Chirp3-HD-Aoede"
    )
    response.pause(length=1)
    response.say(
        "Anh Huy Bùi tạo ra mình. Cho nên mình có nói bậy là tại ảnh.",
        voice="Google.vi-VN-Chirp3-HD-Aoede"
    )
    response.pause(length=1)
    response.say(
        "Go ahead, ask me anything!"
    )

# 2) OpenAI Realtime API greeting
# Pro: stays in the same conversational flow as the rest of the call.
# Con: the caller can interrupt it, and it may say something unpredictable.
def greeting_openai():
    """Instruction text used to make the AI greet the caller first, once the
    media stream connects (see send_initial_conversation_item in main.py)."""
    return "Say: Hello There, I am an AI Assistant."