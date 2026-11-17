from sqlalchemy import delete, select, text

from app.core.errors import ServiceError
from app.core.security import utc_now
from app.db.session import SessionLocal
from app.models.auth import AuthIdentity, RefreshSession
from app.models.advertising_consent import AdvertisingConsentDecision
from app.models.chat import Conversation, ConversationMember
from app.models.profile import Profile
from app.models.policy_consent import PolicyAcceptance
from app.models.user import User


class AccountRepository:
    """Erases account-owned records while retaining only a non-identifying deletion audit row."""

    def delete_account(self, user_id: str) -> None:
        with SessionLocal.begin() as session:
            user = session.get(User, user_id)
            if user is None or user.status not in ("active", "seed"):
                raise ServiceError("user_unavailable", "User unavailable", 401)

            now = utc_now()
            # Removing a member closes every direct chat for both participants.
            # Cascades remove all chat messages and membership/read-state rows.
            conversation_ids = list(
                session.scalars(
                    select(ConversationMember.conversation_id).where(
                        ConversationMember.user_id == user_id
                    )
                )
            )
            if conversation_ids:
                session.execute(
                    delete(Conversation).where(Conversation.id.in_(conversation_ids))
                )
            session.execute(text("DELETE FROM call_signals WHERE sender_id = :user_id"), {"user_id": user_id})
            session.execute(
                text("DELETE FROM call_requests WHERE requester_id = :user_id OR recipient_id = :user_id"),
                {"user_id": user_id},
            )
            session.execute(
                text("DELETE FROM match_exposures WHERE viewer_id = :user_id OR candidate_id = :user_id"),
                {"user_id": user_id},
            )
            session.execute(text("DELETE FROM match_preferences WHERE user_id = :user_id"), {"user_id": user_id})
            # Profile cascades remove its languages, interests, and photo references.
            session.execute(delete(Profile).where(Profile.user_id == user_id))
            # Removing the identity also allows the same Google account to start fresh later.
            session.execute(delete(AuthIdentity).where(AuthIdentity.user_id == user_id))
            session.execute(delete(RefreshSession).where(RefreshSession.user_id == user_id))
            session.execute(delete(PolicyAcceptance).where(PolicyAcceptance.user_id == user_id))
            session.execute(
                delete(AdvertisingConsentDecision).where(
                    AdvertisingConsentDecision.user_id == user_id
                )
            )
            user.status = "deleted"
            user.last_active_at = None
            user.call_notifications_enabled = False
            user.push_token = None
            user.deleted_at = now
