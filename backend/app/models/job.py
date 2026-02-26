from enum import Enum

from pydantic import BaseModel


class JobStatus(str, Enum):
    NEW = "New"
    IN_PROGRESS = "In Progress"
    APPLIED = "Applied"
    WAITING = "Waiting"
    RESPONSE = "Response"
    INTERVIEW = "Interview"
    NO_RESPONSE = "No Response"
    CLOSED = "Closed"


# Only these flags are valid — see CLAUDE.md Scoring Module
VALID_STOP_FLAGS = {"visa_required", "citizenship"}
VALID_WARNING_FLAGS = {"exp_gap", "junior_role"}
VALID_REVIEW_FLAGS = {"strong_mismatch"}
ALL_VALID_FLAGS = VALID_STOP_FLAGS | VALID_WARNING_FLAGS | VALID_REVIEW_FLAGS


def sanitize_flags(raw: str) -> str:
    """Keep only valid flags, strip geo/contractor/other garbage."""
    if not raw or raw.strip().upper() == "NONE":
        return ""
    parts = [f.strip() for f in raw.split(",")]
    clean = [f for f in parts if f in ALL_VALID_FLAGS]
    return ", ".join(clean)


class Job(BaseModel):
    """Maps 1:1 to the Google Sheets 'Pipeline' columns."""
    row_num: int = 0

    company: str = ""
    role: str = ""
    region: str = ""
    seniority: str = ""
    operator_vs_contractor: str = ""
    status: str = "New"
    submission_count: str = ""
    reapply_reason: str = ""
    applied_date: str = ""
    followup_1: str = ""
    followup_2: str = ""
    response_date: str = ""
    days_to_response: str = ""
    source: str = ""
    channel: str = ""
    role_fit: str = ""
    stop_flags: str = ""
    contact: str = ""
    cv: str = ""
    cl: str = ""
    comment: str = ""

    # Computed fields (not in sheet)
    possible_duplicate: bool = False
    duplicate_of: str = ""  # e.g. "Row 15: Shell — PM"
    needs_followup: bool = False


class JobCreate(BaseModel):
    """Create a job — fields match the bot's evaluate() output dict."""
    company: str = ""
    role: str = ""
    region: str = ""
    seniority: str = ""
    operator_vs_contractor: str = ""
    source: str = ""
    channel: str = ""
    role_fit: str = ""
    stop_flags: str = ""
    comment: str = ""


class JobUpdate(BaseModel):
    """Partial update of a sheet row."""
    status: str | None = None
    role_fit: str | None = None
    stop_flags: str | None = None
    applied_date: str | None = None
    followup_1: str | None = None
    followup_2: str | None = None
    response_date: str | None = None
    contact: str | None = None
    cv: str | None = None
    cl: str | None = None
    comment: str | None = None
    submission_count: str | None = None
    reapply_reason: str | None = None


class Event(BaseModel):
    """Event log entry."""
    job_id: int
    timestamp: str = ""
    event_type: str = ""
    data: str = ""  # JSON string
