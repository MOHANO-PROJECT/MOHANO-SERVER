from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class MonetizationStatus(BaseModel):
    plan: Literal["free", "plus"] = "free"
    is_subscriber: bool = False
    subscription_ends_at: datetime | None = None


class ChatMonetizationStatus(MonetizationStatus):
    local_date: date
    requires_ad: bool
    gate_type: Literal["chat_start", "chat_messages"] | None = None
    free_messages_used: int = 0
    free_messages_limit: int = 10


class CandidateBatchMonetizationStatus(MonetizationStatus):
    local_date: date
    requires_ad: bool
    batches_served: int = 0
