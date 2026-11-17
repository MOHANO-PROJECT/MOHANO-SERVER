from sqlalchemy import select

from app.core.errors import ServiceError
from app.db.session import SessionLocal
from app.models.advertising_consent import AdvertisingConsentDecision
from app.models.user import User
from app.schemas.advertising_consent import (
    AdvertisingConsentResponse,
    AdvertisingConsentUpdateRequest,
)


CURRENT_ADVERTISING_CONSENT_VERSION = "2026-10-26"


class AdvertisingConsentRepository:
    """Stores the current advertising preference as an append-only decision history."""

    def get(self, user_id: str) -> AdvertisingConsentResponse | None:
        with SessionLocal() as session:
            self._active_user(session, user_id)
            decision = session.scalar(
                select(AdvertisingConsentDecision)
                .where(AdvertisingConsentDecision.user_id == user_id)
                .order_by(
                    AdvertisingConsentDecision.decided_at.desc(),
                    AdvertisingConsentDecision.id.desc(),
                )
            )
            return self._response(decision) if decision is not None else None

    def save(
        self, user_id: str, payload: AdvertisingConsentUpdateRequest
    ) -> AdvertisingConsentResponse:
        with SessionLocal.begin() as session:
            self._active_user(session, user_id)
            latest = session.scalar(
                select(AdvertisingConsentDecision)
                .where(AdvertisingConsentDecision.user_id == user_id)
                .order_by(
                    AdvertisingConsentDecision.decided_at.desc(),
                    AdvertisingConsentDecision.id.desc(),
                )
            )
            if (
                latest is not None
                and latest.consent_version == CURRENT_ADVERTISING_CONSENT_VERSION
                and latest.personalized_ads_allowed
                == payload.personalized_ads_allowed
                and latest.locale == payload.locale
            ):
                return self._response(latest)
            decision = AdvertisingConsentDecision(
                user_id=user_id,
                consent_version=CURRENT_ADVERTISING_CONSENT_VERSION,
                personalized_ads_allowed=payload.personalized_ads_allowed,
                locale=payload.locale,
            )
            session.add(decision)
            session.flush()
            return self._response(decision)

    @staticmethod
    def _response(decision: AdvertisingConsentDecision) -> AdvertisingConsentResponse:
        return AdvertisingConsentResponse(
            personalized_ads_allowed=decision.personalized_ads_allowed,
            consent_version=decision.consent_version,
            locale=decision.locale,
            decided_at=decision.decided_at,
        )

    @staticmethod
    def _active_user(session, user_id: str) -> User:
        user = session.get(User, user_id)
        if user is None or user.status not in ("active", "seed"):
            raise ServiceError("user_unavailable", "User unavailable", 401)
        return user
