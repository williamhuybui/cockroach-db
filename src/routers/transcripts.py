"""
API endpoints for call transcripts.

This router supports the live transcript workflow:

1. The first transcript turn may arrive without a call_id.
2. transcript_service.py generates a unique call_id.
3. Later transcript turns reuse the same call_id.
4. transcript_service.py saves each completed transcript turn.
5. Stored transcripts can be read, updated, or deleted.

Both POST /transcripts and the live Twilio WebSocket use the same
transcript service.
"""

from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Response,
    status,
)
from psycopg.errors import UniqueViolation

from api_models import (
    TranscriptCreate,
    TranscriptUpdate,
    validate_call_id,
    validate_phone_number,
)
from database import (
    get_database_connection,
    get_database_transaction,
)
from services.transcript_service import create_transcript_turn


# Group all transcript endpoints under /transcripts.
router = APIRouter(
    prefix="/transcripts",
    tags=["transcripts"],
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
async def create_transcript(
    transcript: TranscriptCreate,
):
    """
    Save one live transcript turn to CockroachDB.

    When call_id is missing, transcript_service.py generates a new
    call ID. Later transcript turns must reuse the returned ID.
    """

    try:
        row = await create_transcript_turn(
            call_id=transcript.call_id,
            timestamp=transcript.timestamp,
            caller_number=transcript.caller_number,
            speaker=transcript.speaker,
            text=transcript.text,
        )

    except UniqueViolation as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This transcript turn already exists.",
        ) from error

    if row is None:
        raise RuntimeError(
            "Transcript insert returned no row."
        )

    return dict(row)


@router.get("")
async def list_transcripts(
    caller_number: str | None = None,
    call_id: str | None = None,
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
):
    """
    Return transcript turns, optionally filtered by caller number or
    call ID.
    """

    conditions = []
    values = []

    if caller_number is not None:
        try:
            normalized_phone = validate_phone_number(
                caller_number
            )

        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
            ) from error

        conditions.append(
            "caller_number = %s"
        )

        values.append(
            normalized_phone
        )

    if call_id is not None:
        try:
            cleaned_call_id = validate_call_id(
                call_id
            )

        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
            ) from error

        conditions.append(
            "call_id = %s"
        )

        values.append(
            cleaned_call_id
        )

    where_clause = ""

    if conditions:
        where_clause = (
            "WHERE " + " AND ".join(conditions)
        )

    values.append(limit)

    sql = f"""
        SELECT
            id,
            call_id,
            "timestamp",
            caller_number,
            speaker,
            text,
            saved_to_db_at
        FROM transcripts
        {where_clause}
        ORDER BY "timestamp"
        LIMIT %s
    """

    async with get_database_connection() as connection:
        cursor = await connection.execute(
            sql,
            tuple(values),
        )

        rows = await cursor.fetchall()

    return [
        dict(row)
        for row in rows
    ]


@router.get("/{transcript_id}")
async def get_transcript(
    transcript_id: UUID,
):
    """
    Return one transcript turn using its UUID.
    """

    async with get_database_connection() as connection:
        cursor = await connection.execute(
            """
            SELECT
                id,
                call_id,
                "timestamp",
                caller_number,
                speaker,
                text,
                saved_to_db_at
            FROM transcripts
            WHERE id = %s
            """,
            (transcript_id,),
        )

        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found.",
        )

    return dict(row)


@router.patch("/{transcript_id}")
async def update_transcript(
    transcript_id: UUID,
    update: TranscriptUpdate,
):
    """
    Update selected transcript fields.
    """

    changes = update.model_dump(
        exclude_unset=True
    )

    if not changes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one field is required.",
        )

    required_fields = (
        "call_id",
        "timestamp",
        "caller_number",
        "speaker",
        "text",
    )

    for field_name in required_fields:
        if (
            field_name in changes
            and changes[field_name] is None
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field_name} cannot be null.",
            )

    assignments = []
    values = []

    allowed_fields = (
        "call_id",
        "timestamp",
        "caller_number",
        "speaker",
        "text",
    )

    for field_name in allowed_fields:
        if field_name not in changes:
            continue

        column_name = (
            '"timestamp"'
            if field_name == "timestamp"
            else field_name
        )

        assignments.append(
            f"{column_name} = %s"
        )

        values.append(
            changes[field_name]
        )

    values.append(
        transcript_id
    )

    sql = f"""
        UPDATE transcripts
        SET {", ".join(assignments)}
        WHERE id = %s
        RETURNING
            id,
            call_id,
            "timestamp",
            caller_number,
            speaker,
            text,
            saved_to_db_at
    """

    try:
        async with get_database_transaction() as connection:
            cursor = await connection.execute(
                sql,
                tuple(values),
            )

            row = await cursor.fetchone()

    except UniqueViolation as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The updated transcript duplicates "
                "an existing transcript."
            ),
        ) from error

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found.",
        )

    return dict(row)


@router.delete(
    "/{transcript_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_transcript(
    transcript_id: UUID,
):
    """
    Delete one transcript turn using its UUID.
    """

    async with get_database_transaction() as connection:
        cursor = await connection.execute(
            """
            DELETE FROM transcripts
            WHERE id = %s
            RETURNING id
            """,
            (transcript_id,),
        )

        deleted_row = await cursor.fetchone()

    if deleted_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found.",
        )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )