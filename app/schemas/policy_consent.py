from typing import Literal

from pydantic import BaseModel


class PolicyConsentRequest(BaseModel):
    """Every required item must be explicitly accepted by the user."""

    terms_accepted: Literal[True]
    privacy_policy_accepted: Literal[True]
    community_guidelines_accepted: Literal[True]
    age_15_or_over_confirmed: Literal[True]
    locale: Literal["en", "ja", "ko"]
