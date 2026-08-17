"""
Pydantic models and shared validation for the FastAPI application.

This file defines the data accepted by the API:

1. TranscriptCreate validates each live transcript turn.
2. TranscriptUpdate validates partial transcript changes.
3. CustomerCreate validates manually created customers.
4. CustomerUpdate validates customer profile changes.
5. CallCreate validates the completed call summary.
6. CallUpdate validates partial changes to completed calls.

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
from zoneinfo import ZoneInfo

from config import COMPANY_TIMEZONE

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


PHONE_PATTERN = re.compile(
    r"^\+[1-9]\d{7,14}$"
)


CALL_ID_PATTERN = re.compile(
    r"^C\d{3,}$"
)


TranscriptSpeaker = Literal[
    "assistant",
    "caller",
]


CallUrgency = Literal[
    "Low",
    "Medium",
    "High",
    "Emergency",
]


CallStatus = Literal[
    "active",
    "completed",
    "failed",
    "disconnected",
]

TaskStatus = Literal[
    "open",
    "done",
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

    cleaned_phone_number = phone_number.strip()

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

    cleaned_call_id = call_id.strip().upper()

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



def clean_string_list(
    values: list[str] | None,
) -> list[str] | None:
    """
    Clean an optional list of short text values (tags or to-do items).

    Blank entries are dropped. An empty result becomes None.
    """

    if values is None:
        return None

    cleaned = [
        value.strip()
        for value in values
        if value and value.strip()
    ]

    return cleaned or None
# -------------------------------------------------------------------
# Transcript models
# -------------------------------------------------------------------

class TranscriptCreate(APIModel):
    """
    Request body for saving one live transcript turn.

    The first transcript turn may omit call_id. The transcript service
    then gets a unique sequence number from CockroachDB and returns a
    call ID such as C001.

    Every later turn in the same call must reuse that call ID.

    CockroachDB generates:
    - transcript UUID
    - saved_to_db_at
    """

    call_id: str | None = None
    timestamp: datetime
    caller_number: str
    speaker: TranscriptSpeaker

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
    """

    id: UUID
    call_id: str
    timestamp: datetime
    caller_number: str
    speaker: TranscriptSpeaker
    text: str
    saved_to_db_at: datetime


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

class TodoItem(APIModel):
    """
    One follow-up action item, as judged directly by the post-call
    extraction LLM (see post_call_extraction.py) — not derived after the
    fact by keyword/regex matching on the description text.

    is_appointment and suggested_datetime are the model's own read of
    whether this item is about scheduling/confirming an in-person visit and,
    if the caller and agent settled on a specific date/time, what that is
    (resolved against the call's real date the same way `availability` is).
    The dashboard's Schedule sheet uses suggested_datetime only to pre-fill
    itself — a human still has to click Save to actually book it.
    """

    description: str
    is_appointment: bool = False
    suggested_datetime: datetime | None = None

    @field_validator("description")
    @classmethod
    def check_description(cls, description):
        description = (description or "").strip()
        if not description:
            raise ValueError("todo_items description cannot be blank")
        return description

    @field_validator("suggested_datetime")
    @classmethod
    def localize_suggested_datetime(cls, value):
        """
        The extraction prompt asks for a plain "YYYY-MM-DDTHH:MM" (no
        timezone) meant as company-local time — same convention as
        dashboard.py's scheduled_at. Attach the zone explicitly rather than
        letting it fall through as naive, which the database would
        otherwise store as UTC and silently shift by several hours.
        """
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=ZoneInfo(COMPANY_TIMEZONE))
        return value


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

    call_id: str
    caller_number: str

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
    previous_call_id: str | None = None
    calling_on_behalf_of: str | None = None
    summary: str | None = None
    ended_at: datetime | None = None

    status: CallStatus = "completed"

    tags: list[str] | None = None
    todo_items: list[TodoItem] | None = None

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

    @field_validator("tags")
    @classmethod
    def check_string_lists(
        cls,
        values,
    ):
        """
        Clean tags: strip each entry, drop blanks.
        """

        return clean_string_list(
            values
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
    tags: list[str] | None = None

    previous_call_id: str | None = None
    calling_on_behalf_of: str | None = None
    summary: str | None = None
    ended_at: datetime | None = None
    saved_to_db_at: datetime

class TaskUpdate(APIModel):
    """
    Request body for changing a task's status from the dashboard.
    """

    status: TaskStatus


class TaskResponse(APIModel):
    """
    One follow-up task returned by the API.
    """

    id: UUID
    call_id: str
    customer_id: UUID
    description: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    # Set when the task is closed, nulled when reopened.
    completed_at: datetime | None = None