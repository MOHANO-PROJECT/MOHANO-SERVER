from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class AdvertisingConsentUpdateRequest(BaseModel):
    personalized_ads_allowed: bool
    locale: Literal["en", "ja", "ko"]


class AdvertisingConsentResponse(BaseModel):
    personalized_ads_allowed: bool
    consent_version: str
    locale: Literal["en", "ja", "ko"]
    decided_at: datetime
