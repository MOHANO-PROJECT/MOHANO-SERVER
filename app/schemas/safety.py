from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


ReportReason = Literal[
    "harassment",
    "impersonation",
    "sexual_content",
    "hate_or_discrimination",
    "scam_or_spam",
    "other",
]


class UserReportCreateRequest(BaseModel):
    reported_user_id: str = Field(min_length=1, max_length=36)
    reason: ReportReason
    evidence: str | None = Field(default=None, max_length=1000)

    @field_validator("evidence")
    @classmethod
    def normalize_evidence(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class UserReportResponse(BaseModel):
    report_id: str
    created_at: datetime
    remaining_reports: int


class SafetyStatusResponse(BaseModel):
    restricted: bool
    restricted_until: datetime | None = None
