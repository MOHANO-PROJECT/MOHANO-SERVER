from typing import Optional

from pydantic import BaseModel, Field

from app.core.age_policy import MAXIMUM_MATCHING_AGE, MINIMUM_SERVICE_AGE

from app.schemas.profile import PublicProfile


class MatchPreferences(BaseModel):
    country_code: Optional[str] = Field(default=None, min_length=2, max_length=2)
    gender: Optional[str] = None
    age_min: Optional[int] = Field(
        default=None, ge=MINIMUM_SERVICE_AGE, le=MAXIMUM_MATCHING_AGE
    )
    age_max: Optional[int] = Field(
        default=None, ge=MINIMUM_SERVICE_AGE, le=MAXIMUM_MATCHING_AGE
    )


class MatchPreferencesUpdateRequest(MatchPreferences):
    pass


class MatchCandidate(PublicProfile):
    candidate_id: str


class CandidateListResponse(BaseModel):
    items: list[MatchCandidate]
    next_cursor: Optional[str] = None
