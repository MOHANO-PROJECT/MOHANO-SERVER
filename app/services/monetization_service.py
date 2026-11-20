from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.errors import ServiceError
from app.core.security import utc_now
from app.repositories.monetization_repository import MonetizationRepository
from app.schemas.monetization import (
    CandidateBatchMonetizationStatus,
    ChatMonetizationStatus,
    MonetizationStatus,
)
from app.services.database_profile_service import DatabaseProfileService


class MonetizationService:
    """Applies server-owned free-plan gates without depending on an ad SDK."""

    def __init__(
        self,
        repository: MonetizationRepository,
        profile_service: DatabaseProfileService,
    ) -> None:
        self._repository = repository
        self._profile_service = profile_service

    def status(self, user_id: str) -> MonetizationStatus:
        entitlement = self._repository.entitlement_for(user_id)
        active = self._repository.is_active(entitlement, utc_now())
        return MonetizationStatus(
            plan="plus" if active else "free",
            is_subscriber=active,
            subscription_ends_at=entitlement.ends_at if active and entitlement else None,
        )

    def candidate_status(self, user_id: str) -> CandidateBatchMonetizationStatus:
        status = self.status(user_id)
        local_date = self._local_date(user_id)
        usage = self._repository.candidate_status(user_id, local_date)
        batches_served = usage.batches_served if usage else 0
        requires_ad = (
            not status.is_subscriber
            and usage is not None
            and usage.batches_served > usage.unlocked_batches
        )
        return CandidateBatchMonetizationStatus(
            **status.model_dump(),
            local_date=local_date,
            requires_ad=requires_ad,
            batches_served=batches_served,
        )

    def consume_candidate_batch(self, user_id: str) -> None:
        if self.status(user_id).is_subscriber:
            return
        if not self._repository.consume_candidate_batch(user_id, self._local_date(user_id)):
            raise ServiceError(
                "advertising_gate_required",
                "Complete the candidate-batch advertising gate before continuing",
                409,
            )

    def complete_candidate_gate(self, user_id: str) -> CandidateBatchMonetizationStatus:
        status = self.status(user_id)
        local_date = self._local_date(user_id)
        if not status.is_subscriber:
            self._repository.complete_candidate_gate(user_id, local_date)
        usage = self._repository.candidate_status(user_id, local_date)
        return CandidateBatchMonetizationStatus(
            **status.model_dump(),
            local_date=local_date,
            requires_ad=False,
            batches_served=usage.batches_served if usage else 0,
        )

    def chat_status(self, user_id: str, chat_id: str) -> ChatMonetizationStatus:
        status = self.status(user_id)
        local_date = self._local_date(user_id)
        usage = self._repository.chat_usage(user_id, chat_id, local_date)
        gate_type = None
        if not status.is_subscriber:
            if usage is None or not usage.initial_gate_completed:
                gate_type = "chat_start"
            elif usage.outgoing_messages_since_gate >= 10:
                gate_type = "chat_messages"
        return ChatMonetizationStatus(
            **status.model_dump(),
            local_date=local_date,
            requires_ad=gate_type is not None,
            gate_type=gate_type,
            free_messages_used=usage.outgoing_messages_since_gate if usage else 0,
        )

    def complete_chat_gate(self, user_id: str, chat_id: str) -> ChatMonetizationStatus:
        status = self.status(user_id)
        local_date = self._local_date(user_id)
        if not status.is_subscriber:
            self._repository.complete_chat_gate(user_id, chat_id, local_date)
        return self.chat_status(user_id, chat_id)

    def consume_chat_message(self, user_id: str, chat_id: str) -> None:
        if self.status(user_id).is_subscriber:
            return
        if not self._repository.consume_chat_message(
            user_id, chat_id, self._local_date(user_id)
        ):
            raise ServiceError(
                "advertising_gate_required",
                "Complete the chat advertising gate before sending a message",
                409,
            )

    def _local_date(self, user_id: str) -> date:
        timezone = self._profile_service.get_profile(user_id).timezone
        if timezone:
            try:
                return utc_now().astimezone(ZoneInfo(timezone)).date()
            except ZoneInfoNotFoundError:
                pass
        return utc_now().date()
