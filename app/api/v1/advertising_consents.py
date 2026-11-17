from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_current_user_id
from app.schemas.advertising_consent import (
    AdvertisingConsentResponse,
    AdvertisingConsentUpdateRequest,
)
from app.services.advertising_consent_service import AdvertisingConsentService
from app.services.container import get_advertising_consent_service


router = APIRouter(prefix="/me/advertising-consent")


@router.get("", response_model=AdvertisingConsentResponse)
def get_advertising_consent(
    user_id: str = Depends(get_current_user_id),
    service: AdvertisingConsentService = Depends(get_advertising_consent_service),
) -> AdvertisingConsentResponse | Response:
    decision = service.get(user_id)
    if decision is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return decision


@router.put("", response_model=AdvertisingConsentResponse)
def save_advertising_consent(
    payload: AdvertisingConsentUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    service: AdvertisingConsentService = Depends(get_advertising_consent_service),
) -> AdvertisingConsentResponse:
    return service.save(user_id, payload)
