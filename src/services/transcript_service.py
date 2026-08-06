"""
Shared transcript creation logic.

Both the REST transcript router and the live Twilio WebSocket use
these functions so transcript records are created the same way.
"""

from datetime import datetime

from database import get_database_transaction
from embedding_service import create_embedding, to_vector_literal


async def generate_call_id() -> str:
    """
    Generate one unique call ID from the CockroachDB sequence.
    """

    async with get_database_transaction() as connection:
        result = await connection.execute(
            """
            SELECT nextval(
                'call_id_sequence'
            ) AS call_number
            """
        )

        row = await result.fetchone()

    return f"C{row['call_number']:03d}"


async def create_transcript_turn(
    *,
    call_id: str | None,
    timestamp: datetime,
    caller_number: str,
    speaker: str,
    text: str,
):
    """
    Create one transcript turn.

    When call_id is None, generate a new call ID first.
    """

    cleaned_text = text.strip()

    if not cleaned_text:
        raise ValueError("Transcript text cannot be blank.")

    if call_id is None:
        call_id = await generate_call_id()

    embedding = await create_embedding(cleaned_text)
    vector_literal = to_vector_literal(embedding)

    async with get_database_transaction() as connection:
        result = await connection.execute(
            """
            INSERT INTO transcripts (
                call_id,
                "timestamp",
                caller_number,
                speaker,
                text,
                embedding
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s::VECTOR
            )
            RETURNING
                id,
                call_id,
                "timestamp",
                caller_number,
                speaker,
                text,
                saved_to_db_at
            """,
            (
                call_id,
                timestamp,
                caller_number,
                speaker,
                cleaned_text,
                vector_literal,
            ),
        )

        return await result.fetchone()