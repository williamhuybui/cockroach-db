"""
Shared Twilio SMS client for post-call follow-up texts.

1. main.py provides TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER.
2. configure_sms_client() creates one shared Twilio REST client.
3. routers/calls.py calls send_call_summary_sms() after a completed
   call is saved.
"""

import asyncio
import logging

from twilio.rest import Client

logger = logging.getLogger(__name__)

sms_client: Client | None = None
sms_from_number: str | None = None


def configure_sms_client(account_sid: str, auth_token: str, from_number: str) -> Client:
    global sms_client, sms_from_number

    if not account_sid or not auth_token or not from_number:
        raise ValueError(
            "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER are all required."
        )

    if sms_client is None:
        sms_client = Client(account_sid, auth_token)
        sms_from_number = from_number

    return sms_client


async def send_call_summary_sms(to_number: str, message: str) -> None:
    """
    Send one follow-up SMS. Never raises — a failed text should not
    fail the call-saving request. Twilio's client is sync, so this
    runs it in a thread to avoid blocking the event loop.
    """

    if sms_client is None:
        logger.warning("SMS client not configured; skipping follow-up text.")
        return

    try:
        await asyncio.to_thread(
            sms_client.messages.create,
            to=to_number,
            from_=sms_from_number,
            body=message,
        )
    except Exception:
        logger.exception("Failed to send follow-up SMS to %s", to_number)