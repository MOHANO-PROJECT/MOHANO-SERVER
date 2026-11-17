from sqlalchemy import select

from app.core.errors import ServiceError
from app.db.session import SessionLocal
from app.models.policy_consent import PolicyAcceptance
from app.models.profile import Profile
from app.models.user import User


CURRENT_POLICY_VERSIONS = {
    "terms": "2026-10-26",
    "privacy": "2026-10-26",
    "community_guidelines": "2026-10-26",
    "age_15_or_over": "2026-10-26",
}


class PolicyConsentRepository:
    """Persists affirmative onboarding policy acceptances and completes onboarding."""

    def accept_required_policies(self, user_id: str, *, locale: str) -> None:
        with SessionLocal.begin() as db:
            user = db.get(User, user_id)
            if user is None or user.status not in ("active", "seed"):
                raise ServiceError("user_unavailable", "User unavailable", 401)

            profile = db.get(Profile, user_id)
            if profile is None or not (
                profile.nationality and profile.gender and profile.birth_date
            ):
                raise ServiceError(
                    "profile_incomplete",
                    "Complete the required profile details before accepting policies.",
                    400,
                )

            existing = {
                (record.policy_type, record.policy_version)
                for record in db.scalars(
                    select(PolicyAcceptance).where(
                        PolicyAcceptance.user_id == user_id
                    )
                )
            }
            for policy_type, policy_version in CURRENT_POLICY_VERSIONS.items():
                if (policy_type, policy_version) not in existing:
                    db.add(
                        PolicyAcceptance(
                            user_id=user_id,
                            policy_type=policy_type,
                            policy_version=policy_version,
                            locale=locale,
                        )
                    )

            profile.onboarding_completed = True
