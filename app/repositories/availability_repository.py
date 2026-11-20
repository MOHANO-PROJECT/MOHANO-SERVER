from sqlalchemy import or_, select

from app.core.errors import ServiceError
from app.core.security import utc_now
from app.db.session import SessionLocal
from app.models.profile import Profile
from app.models.user import User
from app.schemas.availability import AvailabilityResponse, AvailabilityUpdateRequest


class AvailabilityRepository:
    """Stores device delivery settings and one-shot app lifecycle presence."""

    def update_presence(self, user_id: str, is_foreground: bool) -> AvailabilityResponse:
        with SessionLocal.begin() as session:
            user = self._active_user(session, user_id)
            user.last_active_at = utc_now() if is_foreground else None
            session.flush()
            return self._response(user)

    def update(self, user_id: str, payload: AvailabilityUpdateRequest) -> AvailabilityResponse:
        with SessionLocal.begin() as session:
            user = self._active_user(session, user_id)
            user.call_notifications_enabled = payload.call_notifications_enabled
            if "push_token" in payload.model_fields_set:
                user.push_token = payload.push_token.strip() if payload.push_token else None
            user.notification_locale = payload.notification_locale
            session.flush()
            return self._response(user)

    def is_eligible_for_call(self, user_id: str) -> bool:
        with SessionLocal() as session:
            return session.scalar(
                select(User.id)
                .join(Profile, Profile.user_id == User.id)
                .where(
                    User.id == user_id,
                    User.status.in_(("active", "seed")),
                    or_(User.restricted_until.is_(None), User.restricted_until <= utc_now()),
                    Profile.onboarding_completed.is_(True),
                )
            ) is not None

    def get_push_target(self, user_id: str) -> tuple[str, str] | None:
        """Returns a token and the recipient's selected notification locale."""
        with SessionLocal() as session:
            user = session.get(User, user_id)
            if (
                user is None
                or user.status != "active"
                or not user.call_notifications_enabled
                or not user.push_token
            ):
                return None
            return user.push_token, user.notification_locale

    def clear_push_token_if_matches(self, user_id: str, token: str) -> None:
        """Drops only the rejected device token, never a newly rotated one."""
        with SessionLocal.begin() as session:
            user = session.get(User, user_id)
            if user is not None and user.push_token == token:
                user.push_token = None
                user.call_notifications_enabled = False

    @classmethod
    def _response(cls, user: User) -> AvailabilityResponse:
        return AvailabilityResponse(
            is_foreground=user.last_active_at is not None,
            call_notifications_enabled=user.call_notifications_enabled,
            has_push_token=bool(user.push_token),
        )

    @staticmethod
    def _active_user(session, user_id: str) -> User:
        user = session.get(User, user_id)
        if user is None or user.status != "active":
            raise ServiceError("user_unavailable", "User unavailable", 401)
        return user
