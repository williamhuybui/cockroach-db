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
    model_config = ConfigDict(
        extra="forbid",
    )


def validate_phone_number(
    phone_number: str,
) -> str:
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

    if call_id is None:
        return None

    return validate_call_id(
        call_id
    )


def validate_required_text(
    text: str,
) -> str:
    cleaned_text = text.strip()

    if not cleaned_text:
        raise ValueError(
            "Value cannot be blank."
        )

    return cleaned_text


def clean_optional_text(
    text: str | None,
) -> str | None:
    if text is None:
        return None

    cleaned_text = text.strip()

    if not cleaned_text:
        return None

    return cleaned_text



def clean_string_list(
    values: list[str] | None,
) -> list[str] | None:
    if values is None:
        return None

    cleaned = [
        value.strip()
        for value in values
        if value and value.strip()
    ]

    return cleaned or None

class TranscriptCreate(APIModel):
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
        return validate_required_text(
            text
        )


class TranscriptUpdate(APIModel):
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
        return clean_optional_call_id(
            call_id
        )

    @field_validator("caller_number")
    @classmethod
    def check_optional_phone_number(
        cls,
        caller_number,
    ):
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
        if text is None:
            return None

        return validate_required_text(
            text
        )


class TranscriptResponse(APIModel):
    id: UUID
    call_id: str
    timestamp: datetime
    caller_number: str
    speaker: TranscriptSpeaker
    text: str
    saved_to_db_at: datetime


class CustomerCreate(APIModel):
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
        return clean_optional_text(
            text
        )


class CustomerUpdate(APIModel):
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
        return clean_optional_text(
            text
        )


class CustomerResponse(APIModel):
    id: UUID
    phone_number: str
    full_name: str | None = None
    address: str | None = None
    email: EmailStr | None = None
    created_at: datetime
    updated_at: datetime



class TodoItem(APIModel):
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
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=ZoneInfo(COMPANY_TIMEZONE))
        return value


class CallCreate(APIModel):
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
 
        return validate_call_id(
            call_id
        )

    @field_validator("previous_call_id")
    @classmethod
    def check_previous_call_id(
        cls,
        previous_call_id,
    ):
        return clean_optional_call_id(
            previous_call_id
        )

    @field_validator("caller_number")
    @classmethod
    def check_caller_number(
        cls,
        caller_number,
    ):
        return validate_phone_number(
            caller_number
        )

    @field_validator("tags")
    @classmethod
    def check_string_lists(
        cls,
        values,
    ):

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
        return clean_optional_text(
            text
        )

    @model_validator(mode="after")
    def validate_call_relationships(
        self,
    ):
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
        return clean_optional_text(
            text
        )


class CallResponse(APIModel):
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
    status: TaskStatus


class TaskResponse(APIModel):
    id: UUID
    call_id: str
    customer_id: UUID
    description: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    # Set when the task is closed, nulled when reopened.
    completed_at: datetime | None = None
