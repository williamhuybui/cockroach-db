"""
API endpoints for summarized call records.

This router supports the completed-call workflow:

1. transcripts.py stores live transcript turns in CockroachDB.
2. The first transcript turn receives a unique call_id.
3. All later transcript turns reuse that call_id.
4. After the call ends, an AI agent should extracts information such as customer name,
   address, roofing problem, availability, urgency, and summary
5. POST /calls receives the summary and the same call_id.
6. The router confirms that matching transcript turns exist.
7. The router creates or updates the customer.
8. The router saves one completed call record.
9. The completed call can be read, updated, or deleted.

This router does not generate call IDs. It reuses the call ID already assigned by transcripts.py.
"""

import re

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Response,
    status,
)
from psycopg2.errors import (
    ForeignKeyViolation,
    UniqueViolation,
)

from api_models import (
    CallCreate,
    CallUpdate,
    TodoItem,
    validate_phone_number,
)
from database import (
    get_database_connection,
    get_database_transaction,
)


# Group all completed-call endpoints under /calls.
router = APIRouter(
    prefix="/calls",
    tags=["calls"],
)


# Valid call IDs use formats such as C001, C016, and C1000.
CALL_ID_PATTERN = re.compile(
    r"^C\d{3,}$"
)


def validate_call_id(
    call_id,
):
    """
    Clean and validate a call ID.

    Lowercase values are changed to uppercase.

    Examples:
        c001 -> C001
        C016 -> C016

    Invalid values raise ValueError.
    """

    cleaned_call_id = (
        call_id.strip().upper()
    )

    if not CALL_ID_PATTERN.fullmatch(
        cleaned_call_id
    ):
        raise ValueError(
            "Call ID must use a format such as C001."
        )

    return cleaned_call_id

def validate_route_call_id(
    call_id,
):
    """
    Validate a call ID received through a URL.

    Convert a regular ValueError into an HTTP 422 response so the
    API returns a clear validation error instead of a server error.
    """

    try:
        return validate_call_id(
            call_id
        )

    except ValueError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        ) from error


async def verify_transcripts_exist(
    connection,
    call,
):
    """
    Confirm that transcript turns exist for the summarized call.

    Also confirm that the call's caller number matches the caller
    number stored with its transcript turns.

    This prevents a summary from being attached to another call or
    another caller's transcript history.
    """

    cursor = await connection.execute(
        """
        SELECT
            caller_number,
            min("timestamp") AS call_started_at
        FROM transcripts
        WHERE call_id = %s
        GROUP BY caller_number
        """,
        (call.call_id,),
    )

    transcript_group = await cursor.fetchone()

    # A completed call cannot be created without source transcripts.
    if transcript_group is None:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "No transcript turns exist for this call_id."
            ),
        )

    # The summary must use the same caller number as the transcripts.
    if (
        transcript_group["caller_number"]
        != call.caller_number
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "caller_number does not match the "
                "stored transcript turns."
            ),
        )


async def upsert_customer(
    connection,
    call,
):
    """
    Create or update the customer linked to the completed call.

    A new customer is created when the phone number is not found.

    When the phone number already exists, new non-empty values may
    update the customer's name, address, or email.

    Return the customer ID used by the calls table.
    """

    email = (
        str(call.email)
        if call.email is not None
        else None
    )

    cursor = await connection.execute(
        """
        INSERT INTO customers (
            phone_number,
            full_name,
            address,
            email
        )
        VALUES (
            %s,
            %s,
            %s,
            %s
        )
        ON CONFLICT (phone_number)
        DO UPDATE SET
            -- A human-corrected name (dashboard Clients tab / drawer "Edit
            -- name") wins over anything extraction pulls from the
            -- transcript, permanently, until the correction itself is
            -- changed from the dashboard again.
            full_name = CASE
                WHEN customers.name_is_manual THEN customers.full_name
                ELSE COALESCE(excluded.full_name, customers.full_name)
            END,
            address = COALESCE(
                excluded.address,
                customers.address
            ),
            email = COALESCE(
                excluded.email,
                customers.email
            ),
            updated_at = now()
        RETURNING id
        """,
        (
            call.caller_number,
            call.name,
            call.address,
            email,
        ),
    )

    customer = await cursor.fetchone()

    if customer is None:
        raise RuntimeError(
            "Customer insert returned no row."
        )

    return customer["id"]

async def create_tasks_for_call(
    connection,
    call,
    customer_id,
):
    """
    Create one open task per actionable to-do item on this call.

    This is what the dashboard shows the business owner: things still
    to be done before the caller's request is finished (e.g. an
    appointment isn't confirmed yet). If the agent didn't return
    explicit todo_items but did report a problem, fall back to one
    generic follow-up task so nothing falls through the cracks.

    is_appointment and suggested_datetime come straight from the
    extraction LLM's own read of each item (see post_call_extraction.py) —
    there's no keyword/regex classification after the fact. suggested_datetime
    only ever pre-fills the dashboard's Schedule sheet; a human still has to
    click Save to actually book it into scheduled_at.
    """

    todo_items = call.todo_items or []

    if not todo_items and call.problem:
        todo_items = [TodoItem(description=f"Follow up on: {call.problem}")]

    for item in todo_items:
        await connection.execute(
            """
            INSERT INTO tasks (
                call_id,
                customer_id,
                description,
                is_appointment,
                suggested_datetime
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                call.call_id,
                customer_id,
                item.description,
                item.is_appointment,
                item.suggested_datetime,
            ),
        )

async def insert_call(
    connection,
    call,
):
    """
    Save one completed and summarized call.

    The function:

    1. Validates the call ID.
    2. Validates the previous call ID when provided.
    3. Confirms that matching transcript turns exist.
    4. Creates or updates the customer.
    5. Inserts the completed call into CockroachDB.

    The call ID must match the ID previously used by transcripts.py.
    """

    # Standardize and validate the transcript-generated call ID.
    call.call_id = validate_call_id(
        call.call_id
    )

    # Validate the linked earlier call when this is a follow-up.
    if call.previous_call_id:
        call.previous_call_id = (
            validate_call_id(
                call.previous_call_id
            )
        )

    # Confirm that this summary belongs to stored transcript turns.
    await verify_transcripts_exist(
        connection,
        call,
    )

    # Create or update the customer and receive its database ID.
    customer_id = await upsert_customer(
        connection,
        call,
    )

    email = (
        str(call.email)
        if call.email is not None
        else None
    )

    # Save one structured record for the completed call.
    # Save one structured record for the completed call.
    cursor = await connection.execute(
        """
        INSERT INTO calls (
            call_id,
            customer_id,
            caller_number,
            "timestamp",
            status,
            name,
            email,
            address,
            problem,
            problem_detail,
            availability,
            urgency,
            tags,
            previous_call_id,
            calling_on_behalf_of,
            summary,
            ended_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        RETURNING *
        """,
        (
            call.call_id,
            customer_id,
            call.caller_number,
            call.timestamp,
            call.status,
            call.name,
            email,
            call.address,
            call.problem,
            call.problem_detail,
            call.availability,
            call.urgency,
            call.tags,
            call.previous_call_id,
            call.calling_on_behalf_of,
            call.summary,
            call.ended_at,
        ),
    )

    row = await cursor.fetchone()

    if row is None:
        raise RuntimeError(
            "Call insert returned no row."
        )

    # Create the to-do items the dashboard will show for this call.
    await create_tasks_for_call(
        connection,
        call,
        customer_id,
    )

    return row


async def update_call_from_extraction(
    connection,
    call,
):
    """
    Overwrite an EXISTING call's extracted fields with a fresh extraction
    result (the dashboard's "re-run extraction" button — see
    dashboard.py's api_reextract_conversation).

    Unlike insert_call, this never touches the tasks table itself — the
    caller decides whether to (re)create to-do items, since a rerun
    shouldn't silently wipe out tasks a human has already scheduled or
    completed from the dashboard. Returns (row, customer_id) so the caller
    can make that call.
    """

    call.call_id = validate_call_id(
        call.call_id
    )

    await verify_transcripts_exist(
        connection,
        call,
    )

    # Re-upserting keeps the customer record in sync too — COALESCE in its
    # ON CONFLICT means a less-complete rerun can't blank out a name/address/
    # email a previous extraction already found.
    customer_id = await upsert_customer(
        connection,
        call,
    )

    email = (
        str(call.email)
        if call.email is not None
        else None
    )

    # Deliberately only the fields extraction actually produces — no status,
    # timestamp, caller_number, or previous_call_id here, so this can never
    # clobber values a rerun's prompt doesn't even try to set.
    cursor = await connection.execute(
        """
        UPDATE calls
        SET name = %s,
            email = %s,
            address = %s,
            problem = %s,
            problem_detail = %s,
            availability = %s,
            urgency = %s,
            tags = %s,
            calling_on_behalf_of = %s,
            summary = %s,
            customer_id = %s
        WHERE call_id = %s
        RETURNING *
        """,
        (
            call.name,
            email,
            call.address,
            call.problem,
            call.problem_detail,
            call.availability,
            call.urgency,
            call.tags,
            call.calling_on_behalf_of,
            call.summary,
            customer_id,
            call.call_id,
        ),
    )

    row = await cursor.fetchone()

    if row is None:
        raise RuntimeError(
            "Call update returned no row."
        )

    return row, customer_id


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
async def create_call(
    call: CallCreate,
):
    """
    Save the summarized result after a call ends.

    The request must provide the same call_id and caller_number used
    by the stored transcript turns.

    The customer is created or updated automatically.
    """

    try:
        async with get_database_transaction() as connection:
            row = await insert_call(
                connection,
                call,
            )

    except ValueError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        ) from error

    except UniqueViolation as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A summarized call with this call_id "
                "already exists."
            ),
        ) from error

    except ForeignKeyViolation as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "previous_call_id does not exist."
            ),
        ) from error

    return dict(row)


@router.get("")
async def list_calls(
    caller_number: str | None = None,
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
):
    """
    Return a list of completed calls.

    Results may be filtered by caller number.

    The newest calls are returned first.
    """

    # Return all calls when no phone filter is provided.
    if caller_number is None:
        sql = """
            SELECT *
            FROM calls
            ORDER BY "timestamp" DESC
            LIMIT %s
        """

        parameters = (
            limit,
        )

    else:
        # Validate and normalize the caller-number filter.
        try:
            normalized_phone = validate_phone_number(
                caller_number
            )

        except ValueError as error:
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=str(error),
            ) from error

        sql = """
            SELECT *
            FROM calls
            WHERE caller_number = %s
            ORDER BY "timestamp" DESC
            LIMIT %s
        """

        parameters = (
            normalized_phone,
            limit,
        )

    async with get_database_connection() as connection:
        cursor = await connection.execute(
            sql,
            parameters,
        )

        rows = await cursor.fetchall()

    return [
        dict(row)
        for row in rows
    ]


@router.get(
    "/{call_id}"
)
async def get_call(
    call_id: str,
):
    """
    Return one completed call and all of its transcript turns.

    The call record provides the structured summary.

    The transcript records provide the full conversation history.
    """

    normalized_call_id = (
        validate_route_call_id(
            call_id
        )
    )

    async with get_database_connection() as connection:
        # Retrieve the completed call record.
        call_cursor = await connection.execute(
            """
            SELECT *
            FROM calls
            WHERE call_id = %s
            """,
            (
                normalized_call_id,
            ),
        )

        call = await call_cursor.fetchone()

        if call is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail="Call not found.",
            )

        # Retrieve all transcript turns linked by the same call ID.
        transcripts_cursor = await connection.execute(
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
            WHERE call_id = %s
            ORDER BY "timestamp"
            """,
            (
                normalized_call_id,
            ),
        )

        transcripts = (
            await transcripts_cursor.fetchall()
        )

    return {
        "call": dict(call),
        "transcripts": [
            dict(row)
            for row in transcripts
        ],
    }


@router.patch(
    "/{call_id}"
)
async def update_call(
    call_id: str,
    update: CallUpdate,
):
    """
    Update selected fields on one completed call.

    Only fields included in the PATCH request are changed.

    The call ID, customer ID, caller number, and original database
    save time are not changed by this endpoint.
    """

    normalized_call_id = (
        validate_route_call_id(
            call_id
        )
    )

    # Keep only values included in the PATCH request.
    changes = update.model_dump(
        exclude_unset=True
    )

    if not changes:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail="At least one field is required.",
        )

    assignments = []
    values = []

    allowed_fields = (
        "status",
        "summary",
        "ended_at",
        "problem",
        "problem_detail",
        "availability",
        "urgency",
        "calling_on_behalf_of",
        "previous_call_id",
    )

    # Build SQL assignments only for supplied fields.
    for field_name in allowed_fields:
        if field_name not in changes:
            continue

        value = changes[field_name]

        # Validate a new follow-up link before saving it.
        if (
            field_name == "previous_call_id"
            and value is not None
        ):
            try:
                value = validate_call_id(
                    value
                )

            except ValueError as error:
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail=str(error),
                ) from error

            # A call cannot point to itself as its previous call.
            if value == normalized_call_id:
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail=(
                        "A call cannot reference itself "
                        "as previous_call_id."
                    ),
                )

        assignments.append(
            f"{field_name} = %s"
        )

        values.append(
            value
        )

    if not assignments:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "No supported call fields were provided."
            ),
        )

    values.append(
        normalized_call_id
    )

    sql = f"""
        UPDATE calls
        SET {", ".join(assignments)}
        WHERE call_id = %s
        RETURNING *
    """

    try:
        async with get_database_transaction() as connection:
            cursor = await connection.execute(
                sql,
                tuple(values),
            )

            row = await cursor.fetchone()

    except ForeignKeyViolation as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "previous_call_id does not exist."
            ),
        ) from error

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found.",
        )

    return dict(row)


@router.delete(
    "/{call_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_call(
    call_id: str,
):
    """
    Delete one completed call record.

    Transcript turns remain in CockroachDB because transcripts.call_id
    is not a foreign key to calls.call_id.

    This prevents deletion of the summarized record from automatically
    removing the source conversation.
    """

    normalized_call_id = (
        validate_route_call_id(
            call_id
        )
    )

    async with get_database_transaction() as connection:
        cursor = await connection.execute(
            """
            DELETE FROM calls
            WHERE call_id = %s
            RETURNING call_id
            """,
            (
                normalized_call_id,
            ),
        )

        deleted_row = await cursor.fetchone()

    if deleted_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found.",
        )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )