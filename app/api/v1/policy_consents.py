from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id
from app.schemas.policy_consent import PolicyConsentRequest
from app.schemas.profile import ProfileResponse
from app.services.container import get_policy_consent_service, get_profile_service
from app.services.database_profile_service import DatabaseProfileService
from app.services.policy_consent_service import PolicyConsentService

router = APIRouter(prefix="/me/policy-consents")


@router.post("", response_model=ProfileResponse)
def accept_required_policies(
    payload: PolicyConsentRequest,
    user_id: str = Depends(get_current_user_id),
    consent_service: PolicyConsentService = Depends(get_policy_consent_service),
    profile_service: DatabaseProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    consent_service.accept_required_policies(user_id, payload)
    return profile_service.get_profile(user_id)
