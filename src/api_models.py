"""
Pydantic models and shared validation for the FastAPI application.

This file defines the data accepted by the API:

1. TranscriptCreate validates each live transcript turn.
2. TranscriptUpdate validates partial transcript changes.
3. SemanticSearchRequest validates transcript searches.
4. CustomerCreate validates manually created customers.
5. CustomerUpdate validates customer profile changes.
6. CallCreate validates the completed call summary.
7. CallUpdate validates partial changes to completed calls.

The models clean incoming values before the routers use them.

Important rules:

- Phone numbers must use E.164 format.
- Call IDs must use a format such as C001.
- The first transcript may omit call_id.
- Later transcripts must reuse the generated call_id.
- Completed calls must provide the transcript-generated call_id.
- Blank required text is rejected.
- Blank optional text is stored as None.
- Unexpected request fields are rejected.
"""

import re

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


# Valid phone numbers use E.164 format.
#
# Examples:
# +14175551001
# +84901234567
PHONE_PATTERN = re.compile(
    r"^\+[1-9]\d{7,14}$"
)


# Valid call IDs include C followed by at least three digits.
#
# Examples:
# C001
# C016
# C1000
CALL_ID_PATTERN = re.compile(
    r"^C\d{3,}$"
)


# Allowed speaker values for transcript turns.
TranscriptSpeaker = Literal[
    "assistant",
    "caller",
]


# Allowed urgency values for completed calls.
CallUrgency = Literal[
    "Low",
    "Medium",
    "High",
    "Emergency",
]


# Allowed completed-call status values.
CallStatus = Literal[
    "active",
    "completed",
    "failed",
    "disconnected",
]


class APIModel(BaseModel):
    """
    Shared configuration for all API models.

    Unexpected fields are rejected instead of being silently ignored.
    """

    model_config = ConfigDict(
        extra="forbid",
    )


def validate_phone_number(
    phone_number: str,
) -> str:
    """
    Clean and validate a phone number.

    The number must use E.164 format, including the leading plus sign.
    """

    cleaned_phone_number = (
        phone_number.strip()
    )

    if not PHONE_PATTERN.fullmatch(
        cleaned_phone_number
    ):
        raise ValueError(
            "Use E.164 format, for example +14175551001."
        )

    return cleaned_phone_number


def validate_call_id(
    call_id: str,
) -> str:
    """
    Clean and validate a required call ID.

    Lowercase values are changed to uppercase.

    Examples:
        c001 -> C001
        C016 -> C016
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


def clean_optional_call_id(
    call_id: str | None,
) -> str | None:
    """
    Clean and validate an optional call ID.

    None remains None. A provided value must use the C001 format.
    """

    if call_id is None:
        return None

    return validate_call_id(
        call_id
    )


def validate_required_text(
    text: str,
) -> str:
    """
    Remove surrounding spaces and reject blank text.
    """

    cleaned_text = text.strip()

    if not cleaned_text:
        raise ValueError(
            "Value cannot be blank."
        )

    return cleaned_text


def clean_optional_text(
    text: str | None,
) -> str | None:
    """
    Clean optional text.

    Blank optional text is converted to None.
    """

    if text is None:
        return None

    cleaned_text = text.strip()

    if not cleaned_text:
        return None

    return cleaned_text


# -------------------------------------------------------------------
# Transcript models
# -------------------------------------------------------------------

class TranscriptCreate(APIModel):
    """
    Request body for saving one live transcript turn.

    The first transcript turn may omit call_id. The transcript router
    then gets a unique sequence number from CockroachDB and returns a
    call ID such as C001.

    Every later turn in the same call must reuse that call ID.

    CockroachDB generates:
    - transcript UUID
    - saved_to_db_at
    """

    # Omitted only for the first transcript turn.
    call_id: str | None = None

    # Time when this transcript turn occurred.
    timestamp: datetime

    # Phone number associated with the live call.
    caller_number: str

    # Identifies who spoke this turn.
    speaker: TranscriptSpeaker

    # Exact text from this conversation turn.
    text: str = Field(
        min_length=1,
    )

    @field_validator("call_id")
    @classmethod
    def check_optional_call_id(
        cls,
        call_id,
    ):
        """
        Validate call_id when it is supplied.
        """

        return clean_optional_call_id(
            call_id
        )

    @field_validator("caller_number")
    @classmethod
    def check_phone_number(
        cls,
        caller_number,
    ):
        """
        Validate the transcript caller number.
        """

        return validate_phone_number(
            caller_number
        )

    @field_validator("text")
    @classmethod
    def check_text(
        cls,
        text,
    ):
        """
        Remove surrounding spaces and reject blank transcript text.
        """

        return validate_required_text(
            text
        )


class TranscriptUpdate(APIModel):
    """
    Request body for updating one transcript turn.

    All fields are optional because PATCH changes only the fields sent
    in the request.

    The router regenerates the embedding when text changes.
    """

    call_id: str | None = None
    timestamp: datetime | None = None
    caller_number: str | None = None
    speaker: TranscriptSpeaker | None = None
    text: str | None = None

    @field_validator("call_id")
    @classmethod
    def check_optional_call_id(
        cls,
        call_id,
    ):
        """
        Validate call_id when it is supplied.
        """

        return clean_optional_call_id(
            call_id
        )

    @field_validator("caller_number")
    @classmethod
    def check_optional_phone_number(
        cls,
        caller_number,
    ):
        """
        Validate caller_number when it is supplied.
        """

        if caller_number is None:
            return None

        return validate_phone_number(
            caller_number
        )

    @field_validator("text")
    @classmethod
    def check_optional_text(
        cls,
        text,
    ):
        """
        Validate transcript text when it is supplied.
        """

        if text is None:
            return None

        return validate_required_text(
            text
        )


class TranscriptResponse(APIModel):
    """
    One transcript turn returned by the API.

    The embedding is not included in normal responses.
    """

    id: UUID
    call_id: str
    timestamp: datetime
    caller_number: str
    speaker: TranscriptSpeaker
    text: str
    saved_to_db_at: datetime


class SemanticSearchRequest(APIModel):
    """
    Request body for transcript semantic search.

    The query is converted into an OpenAI embedding and compared with
    stored transcript embeddings in CockroachDB.
    """

    query: str = Field(
        min_length=1,
    )

    # Return between 1 and 20 matching transcript turns.
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
    )

    @field_validator("query")
    @classmethod
    def check_query(
        cls,
        query,
    ):
        """
        Clean and reject a blank search query.
        """

        return validate_required_text(
            query
        )


# -------------------------------------------------------------------
# Customer models
# -------------------------------------------------------------------

class CustomerCreate(APIModel):
    """
    Request body for manually creating one customer.

    Customers are also created or updated automatically when calls.py
    saves a completed call.
    """

    phone_number: str
    full_name: str | None = None
    address: str | None = None
    email: EmailStr | None = None

    @field_validator("phone_number")
    @classmethod
    def check_phone_number(
        cls,
        phone_number,
    ):
        """
        Validate the customer's phone number.
        """

        return validate_phone_number(
            phone_number
        )

    @field_validator(
        "full_name",
        "address",
    )
    @classmethod
    def clean_optional_customer_text(
        cls,
        text,
    ):
        """
        Clean optional customer text fields.
        """

        return clean_optional_text(
            text
        )


class CustomerUpdate(APIModel):
    """
    Request body for updating customer contact information.

    The customer ID and phone number are not changed through this
    model.
    """

    full_name: str | None = None
    address: str | None = None
    email: EmailStr | None = None

    @field_validator(
        "full_name",
        "address",
    )
    @classmethod
    def clean_optional_customer_text(
        cls,
        text,
    ):
        """
        Clean optional customer text fields.
        """

        return clean_optional_text(
            text
        )


class CustomerResponse(APIModel):
    """
    One customer record returned by the API.
    """

    id: UUID
    phone_number: str
    full_name: str | None = None
    address: str | None = None
    email: EmailStr | None = None
    created_at: datetime
    updated_at: datetime


# -------------------------------------------------------------------
# Call models
# -------------------------------------------------------------------

class CallCreate(APIModel):
    """
    Request body for saving one completed and summarized call.

    The call_id must be the same ID generated when transcript
    collection began.

    The request is sent after:
    - the call ends
    - transcript turns are stored
    - summarization is complete
    - structured details are extracted
    """

    # Reuse the ID assigned by transcripts.py.
    call_id: str

    # Must match the caller number stored in the transcript turns.
    caller_number: str

    # Time when the phone call began.
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        )
    )

    name: str | None = None
    email: EmailStr | None = None
    address: str | None = None

    problem: str | None = None
    problem_detail: str | None = None
    availability: str | None = None

    urgency: CallUrgency | None = None

    # Links a follow-up call to an earlier completed call.
    previous_call_id: str | None = None

    # Records the person for whom this caller is calling.
    calling_on_behalf_of: str | None = None

    # AI-generated summary created after the call ends.
    summary: str | None = None

    # Time when the phone call ended.
    ended_at: datetime | None = None

    # The normal value for a summarized call is completed.
    status: CallStatus = "completed"

    @field_validator("call_id")
    @classmethod
    def check_call_id(
        cls,
        call_id,
    ):
        """
        Validate the transcript-generated call ID.
        """

        return validate_call_id(
            call_id
        )

    @field_validator("previous_call_id")
    @classmethod
    def check_previous_call_id(
        cls,
        previous_call_id,
    ):
        """
        Validate the earlier call ID when this is a follow-up call.
        """

        return clean_optional_call_id(
            previous_call_id
        )

    @field_validator("caller_number")
    @classmethod
    def check_caller_number(
        cls,
        caller_number,
    ):
        """
        Validate the completed call's caller number.
        """

        return validate_phone_number(
            caller_number
        )

    @field_validator(
        "name",
        "address",
        "problem",
        "problem_detail",
        "availability",
        "calling_on_behalf_of",
        "summary",
    )
    @classmethod
    def clean_optional_call_text(
        cls,
        text,
    ):
        """
        Clean optional completed-call text fields.
        """

        return clean_optional_text(
            text
        )

    @model_validator(mode="after")
    def validate_call_relationships(
        self,
    ):
        """
        Validate relationships between completed-call fields.

        A call cannot reference itself as its previous call.
        The end time cannot be earlier than the start time.
        """

        if (
            self.previous_call_id is not None
            and self.previous_call_id == self.call_id
        ):
            raise ValueError(
                "A call cannot reference itself as "
                "previous_call_id."
            )

        if (
            self.ended_at is not None
            and self.ended_at < self.timestamp
        ):
            raise ValueError(
                "ended_at cannot be earlier than timestamp."
            )

        return self


class CallUpdate(APIModel):
    """
    Request body for updating one completed call.

    All fields are optional because PATCH changes only the fields sent
    in the request.
    """

    status: CallStatus | None = None

    summary: str | None = None
    ended_at: datetime | None = None

    problem: str | None = None
    problem_detail: str | None = None
    availability: str | None = None

    urgency: CallUrgency | None = None

    calling_on_behalf_of: str | None = None
    previous_call_id: str | None = None

    @field_validator("previous_call_id")
    @classmethod
    def check_previous_call_id(
        cls,
        previous_call_id,
    ):
        """
        Validate previous_call_id when it is supplied.
        """

        return clean_optional_call_id(
            previous_call_id
        )

    @field_validator(
        "summary",
        "problem",
        "problem_detail",
        "availability",
        "calling_on_behalf_of",
    )
    @classmethod
    def clean_optional_call_text(
        cls,
        text,
    ):
        """
        Clean optional completed-call text fields.
        """

        return clean_optional_text(
            text
        )


class CallResponse(APIModel):
    """
    One summarized call returned by the API.
    """

    call_id: str
    customer_id: UUID
    caller_number: str
    timestamp: datetime
    status: CallStatus

    name: str | None = None
    email: EmailStr | None = None
    address: str | None = None

    problem: str | None = None
    problem_detail: str | None = None
    availability: str | None = None
    urgency: CallUrgency | None = None

    previous_call_id: str | None = None
    calling_on_behalf_of: str | None = None
    summary: str | None = None
    ended_at: datetime | None = None
    saved_to_db_at: datetime