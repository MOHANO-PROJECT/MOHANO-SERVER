from app.repositories.advertising_consent_repository import AdvertisingConsentRepository
from app.schemas.advertising_consent import (
    AdvertisingConsentResponse,
    AdvertisingConsentUpdateRequest,
)


class AdvertisingConsentService:
    """Applies and retrieves the user's optional advertising preference."""

    def __init__(self, repository: AdvertisingConsentRepository) -> None:
        self._repository = repository

    def get(self, user_id: str) -> AdvertisingConsentResponse | None:
        return self._repository.get(user_id)

    def save(
        self, user_id: str, payload: AdvertisingConsentUpdateRequest
    ) -> AdvertisingConsentResponse:
        return self._repository.save(user_id, payload)
