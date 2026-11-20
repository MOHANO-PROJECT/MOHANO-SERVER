from fastapi import APIRouter, Depends

from app.api.deps import get_current_interaction_user_id
from app.schemas.monetization import MonetizationStatus
from app.services.container import get_monetization_service
from app.services.monetization_service import MonetizationService


router = APIRouter()


@router.get("/me/monetization", response_model=MonetizationStatus)
def get_monetization_status(
    user_id: str = Depends(get_current_interaction_user_id),
    service: MonetizationService = Depends(get_monetization_service),
) -> MonetizationStatus:
    return service.status(user_id)
