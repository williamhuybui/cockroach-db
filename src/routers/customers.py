"""
API endpoints for customer records.

This router supports customer management:

1. A customer may be created manually through POST /customers.
2. calls.py also creates or updates customers after call summarization.
3. Customers can be listed or retrieved by UUID.
4. A customer can be found by phone number.
5. Looking up a customer by phone number also returns their recent call history and conversation history from transcripts and calls tables.
6. Customer contact details can be updated.
7. A customer record cannot be deleted while they still have saved calls.

"""

from uuid import UUID

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
    CustomerCreate,
    CustomerUpdate,
    validate_phone_number,
)
from database import (
    get_database_connection,
    get_database_transaction,
)


# Group all customer endpoints under /customers.
router = APIRouter(
    prefix="/customers",
    tags=["customers"],
)

async def find_customer_by_phone(phone_number: str) -> dict | None:
    """
    Look up one customer by phone number, for use outside HTTP routes
    (main.py uses this to recognize a returning caller mid-call).

    Returns None on an invalid number or no match — never raises.
    """

    try:
        normalized_phone = validate_phone_number(phone_number)
    except ValueError:
        return None

    async with get_database_connection() as connection:
        cursor = await connection.execute(
            "SELECT * FROM customers WHERE phone_number = %s",
            (normalized_phone,),
        )
        row = await cursor.fetchone()

    return dict(row) if row else None

async def get_customer_memory(phone_number: str) -> dict | None:
    """
    Full context for a returning caller: profile + their last call +
    any pending (open) tasks. Used by main.py to prime the agent at
    the start of a call so it can tell a follow-up from a new request.
    """

    customer = await find_customer_by_phone(phone_number)

    if customer is None:
        return None

    async with get_database_connection() as connection:
        call_cursor = await connection.execute(
            """
            SELECT "timestamp", problem, problem_detail,
                   availability, urgency, summary
            FROM calls
            WHERE caller_number = %s
            ORDER BY "timestamp" DESC
            LIMIT 1
            """,
            (customer["phone_number"],),
        )
        last_call = await call_cursor.fetchone()

        tasks_cursor = await connection.execute(
            """
            SELECT description
            FROM tasks
            WHERE customer_id = %s AND status = 'open'
            ORDER BY created_at
            """,
            (customer["id"],),
        )
        open_tasks = await tasks_cursor.fetchall()

    customer["last_call"] = dict(last_call) if last_call else None
    customer["open_tasks"] = [row["description"] for row in open_tasks]

    return customer

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
async def create_customer(
    customer: CustomerCreate,
):
    """
    Create one customer manually.

    Customers are normally created or updated automatically when a
    completed call is saved. This endpoint supports cases where a
    customer must be created before a call is completed.
    """

    # Convert Pydantic's email type into a database-ready string.
    email = (
        str(customer.email)
        if customer.email is not None
        else None
    )

    try:
        async with get_database_transaction() as connection:
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
                RETURNING *
                """,
                (
                    customer.phone_number,
                    customer.full_name,
                    customer.address,
                    email,
                ),
            )

            row = await cursor.fetchone()

    except UniqueViolation as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A customer with this phone number "
                "already exists."
            ),
        ) from error

    if row is None:
        raise RuntimeError(
            "Customer insert returned no row."
        )

    return dict(row)


@router.get("")
async def list_customers(
    phone_number: str | None = None,
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
):
    """
    Return a list of customers.

    Results may be filtered by phone number.

    The newest customer records are returned first.
    """

    if phone_number is None:
        sql = """
            SELECT *
            FROM customers
            ORDER BY created_at DESC
            LIMIT %s
        """

        parameters = (
            limit,
        )

    else:
        # Validate the phone filter before querying CockroachDB.
        try:
            normalized_phone = validate_phone_number(
                phone_number
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
            FROM customers
            WHERE phone_number = %s
            ORDER BY created_at DESC
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


# Keep this fixed route before /{customer_id}.
@router.get(
    "/by-phone/{phone_number}"
)
async def get_customer_by_phone(
    phone_number: str,
):
    """
    Find one customer using their phone number.

    Return:
    - the customer record
    - up to 20 recent completed calls
    - up to 50 recent transcript turns
    """

    try:
        normalized_phone = validate_phone_number(
            phone_number
        )

    except ValueError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        ) from error

    async with get_database_connection() as connection:
        # Find the main customer record.
        customer_cursor = await connection.execute(
            """
            SELECT *
            FROM customers
            WHERE phone_number = %s
            """,
            (
                normalized_phone,
            ),
        )

        customer = await customer_cursor.fetchone()

        if customer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found.",
            )

        # Return the customer's newest completed calls.
        calls_cursor = await connection.execute(
            """
            SELECT *
            FROM calls
            WHERE caller_number = %s
            ORDER BY "timestamp" DESC
            LIMIT 20
            """,
            (
                normalized_phone,
            ),
        )

        recent_calls = await calls_cursor.fetchall()

        # Return the customer's newest conversation turns.
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
            WHERE caller_number = %s
            ORDER BY "timestamp" DESC
            LIMIT 50
            """,
            (
                normalized_phone,
            ),
        )

        recent_transcripts = (
            await transcripts_cursor.fetchall()
        )

    return {
        "customer": dict(customer),
        "recent_calls": [
            dict(row)
            for row in recent_calls
        ],
        "recent_transcripts": [
            dict(row)
            for row in recent_transcripts
        ],
    }


@router.get(
    "/{customer_id}"
)
async def get_customer(
    customer_id: UUID,
):
    """
    Return one customer using their database UUID.

    Return HTTP 404 when the customer does not exist.
    """

    async with get_database_connection() as connection:
        cursor = await connection.execute(
            """
            SELECT *
            FROM customers
            WHERE id = %s
            """,
            (
                customer_id,
            ),
        )

        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )

    return dict(row)


@router.patch(
    "/{customer_id}"
)
async def update_customer(
    customer_id: UUID,
    update: CustomerUpdate,
):
    """
    Update selected customer contact fields.

    Only fields included in the PATCH request are changed.

    The customer ID, phone number, and original creation time are not
    changed by this endpoint.
    """

    # Keep only fields supplied in the PATCH request.
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
        "full_name",
        "address",
        "email",
    )

    # Build SQL assignments only for supplied fields.
    for field_name in allowed_fields:
        if field_name not in changes:
            continue

        value = changes[field_name]

        # Convert Pydantic's email type into a database-ready string.
        if (
            field_name == "email"
            and value is not None
        ):
            value = str(value)

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
                "No supported customer fields were provided."
            ),
        )

    # Record when the customer information was last changed.
    assignments.append(
        "updated_at = now()"
    )

    values.append(
        customer_id
    )

    sql = f"""
        UPDATE customers
        SET {", ".join(assignments)}
        WHERE id = %s
        RETURNING *
    """

    async with get_database_transaction() as connection:
        cursor = await connection.execute(
            sql,
            tuple(values),
        )

        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )

    return dict(row)


@router.delete(
    "/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_customer(
    customer_id: UUID,
):
    """
    Delete one customer record.

    CockroachDB blocks deletion when completed calls still reference
    the customer. This protects call history from broken customer
    relationships.
    """

    try:
        async with get_database_transaction() as connection:
            cursor = await connection.execute(
                """
                DELETE FROM customers
                WHERE id = %s
                RETURNING id
                """,
                (
                    customer_id,
                ),
            )

            deleted_row = await cursor.fetchone()

    except ForeignKeyViolation as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This customer cannot be deleted because "
                "call records still reference them."
            ),
        ) from error

    if deleted_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )