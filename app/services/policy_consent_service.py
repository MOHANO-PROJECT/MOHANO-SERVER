from app.repositories.policy_consent_repository import PolicyConsentRepository
from app.schemas.policy_consent import PolicyConsentRequest


class PolicyConsentService:
    """Applies the onboarding policy-consent contract."""

    def __init__(self, repository: PolicyConsentRepository) -> None:
        self._repository = repository

    def accept_required_policies(
        self, user_id: str, payload: PolicyConsentRequest
    ) -> None:
        # Literal[True] fields in the request ensure all four acknowledgements
        # were affirmative; the server, not the client, assigns policy versions.
        self._repository.accept_required_policies(user_id, locale=payload.locale)
