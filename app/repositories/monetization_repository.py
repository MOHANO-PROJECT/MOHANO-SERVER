from datetime import date, datetime

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.monetization import (
    AdGateEvent,
    ChatDailyUsage,
    DiscoveryDailyUsage,
    SubscriptionEntitlement,
)


class MonetizationRepository:
    """Persistent, server-authoritative ad-gate and subscription state."""

    def entitlement_for(self, user_id: str) -> SubscriptionEntitlement | None:
        with SessionLocal() as session:
            return session.scalar(
                select(SubscriptionEntitlement).where(
                    SubscriptionEntitlement.user_id == user_id
                )
            )

    def candidate_status(self, user_id: str, local_date: date) -> DiscoveryDailyUsage | None:
        with SessionLocal() as session:
            return session.scalar(
                select(DiscoveryDailyUsage).where(
                    DiscoveryDailyUsage.user_id == user_id,
                    DiscoveryDailyUsage.local_date == local_date,
                )
            )

    def consume_candidate_batch(self, user_id: str, local_date: date) -> bool:
        """Return false when the next candidate batch has not been ad-unlocked."""
        with SessionLocal.begin() as session:
            usage = self._discovery_usage(session, user_id, local_date, lock=True)
            if usage.batches_served > 0 and usage.unlocked_batches < usage.batches_served:
                return False
            usage.batches_served += 1
            return True

    def complete_candidate_gate(self, user_id: str, local_date: date) -> None:
        with SessionLocal.begin() as session:
            usage = self._discovery_usage(session, user_id, local_date, lock=True)
            if usage.batches_served == 0 or usage.unlocked_batches >= usage.batches_served:
                return
            usage.unlocked_batches += 1
            session.add(
                AdGateEvent(
                    user_id=user_id,
                    gate_type="candidate_batch",
                    subject_id="",
                    local_date=local_date,
                    sequence=usage.unlocked_batches,
                    outcome="completed",
                )
            )
            return

    def chat_usage(
        self, user_id: str, chat_id: str, local_date: date
    ) -> ChatDailyUsage | None:
        with SessionLocal() as session:
            return session.scalar(
                select(ChatDailyUsage).where(
                    ChatDailyUsage.user_id == user_id,
                    ChatDailyUsage.conversation_id == chat_id,
                    ChatDailyUsage.local_date == local_date,
                )
            )

    def complete_chat_gate(
        self, user_id: str, chat_id: str, local_date: date
    ) -> None:
        with SessionLocal.begin() as session:
            usage = self._chat_usage(session, user_id, chat_id, local_date, lock=True)
            if not usage.initial_gate_completed:
                usage.initial_gate_completed = True
                gate_type = "chat_start"
            elif usage.outgoing_messages_since_gate >= 10:
                usage.outgoing_messages_since_gate = 0
                gate_type = "chat_messages"
            else:
                return

            sequence = self._next_event_sequence(
                session, user_id, gate_type, chat_id, local_date
            )
            session.add(
                AdGateEvent(
                    user_id=user_id,
                    gate_type=gate_type,
                    subject_id=chat_id,
                    local_date=local_date,
                    sequence=sequence,
                    outcome="completed",
                )
            )
            return

    def consume_chat_message(
        self, user_id: str, chat_id: str, local_date: date
    ) -> bool:
        """Reserve one outgoing message only when its daily gate is complete."""
        with SessionLocal.begin() as session:
            usage = self._chat_usage(session, user_id, chat_id, local_date, lock=True)
            if not usage.initial_gate_completed or usage.outgoing_messages_since_gate >= 10:
                return False
            usage.outgoing_messages_since_gate += 1
            return True

    @staticmethod
    def is_active(entitlement: SubscriptionEntitlement | None, now: datetime) -> bool:
        return bool(
            entitlement
            and entitlement.status == "active"
            and entitlement.ends_at is not None
            and entitlement.ends_at > now
        )

    @staticmethod
    def _discovery_usage(session, user_id: str, local_date: date, *, lock: bool) -> DiscoveryDailyUsage:
        statement = select(DiscoveryDailyUsage).where(
            DiscoveryDailyUsage.user_id == user_id,
            DiscoveryDailyUsage.local_date == local_date,
        )
        if lock:
            statement = statement.with_for_update()
        usage = session.scalar(statement)
        if usage is None:
            usage = DiscoveryDailyUsage(user_id=user_id, local_date=local_date)
            session.add(usage)
            session.flush()
        return usage

    @staticmethod
    def _chat_usage(session, user_id: str, chat_id: str, local_date: date, *, lock: bool) -> ChatDailyUsage:
        statement = select(ChatDailyUsage).where(
            ChatDailyUsage.user_id == user_id,
            ChatDailyUsage.conversation_id == chat_id,
            ChatDailyUsage.local_date == local_date,
        )
        if lock:
            statement = statement.with_for_update()
        usage = session.scalar(statement)
        if usage is None:
            usage = ChatDailyUsage(
                user_id=user_id,
                conversation_id=chat_id,
                local_date=local_date,
            )
            session.add(usage)
            session.flush()
        return usage

    @staticmethod
    def _next_event_sequence(session, user_id: str, gate_type: str, subject_id: str, local_date: date) -> int:
        events = session.scalars(
            select(AdGateEvent.sequence).where(
                AdGateEvent.user_id == user_id,
                AdGateEvent.gate_type == gate_type,
                AdGateEvent.subject_id == subject_id,
                AdGateEvent.local_date == local_date,
            )
        ).all()
        return (max(events) + 1) if events else 1
