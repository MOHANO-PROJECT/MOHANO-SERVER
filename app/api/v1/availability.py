from fastapi import APIRouter, Depends

from app.api.deps import get_current_interaction_user_id
from app.schemas.availability import (
    AvailabilityPresenceUpdateRequest,
    AvailabilityResponse,
    AvailabilityUpdateRequest,
)
from app.services.container import get_availability_repository
from app.repositories.availability_repository import AvailabilityRepository


router = APIRouter(prefix="/me/availability")


@router.put("/presence", response_model=AvailabilityResponse)
def update_presence(
    payload: AvailabilityPresenceUpdateRequest,
    user_id: str = Depends(get_current_interaction_user_id),
    repository: AvailabilityRepository = Depends(get_availability_repository),
) -> AvailabilityResponse:
    return repository.update_presence(user_id, payload.is_foreground)


@router.put("", response_model=AvailabilityResponse)
def update_availability(
    payload: AvailabilityUpdateRequest,
    user_id: str = Depends(get_current_interaction_user_id),
    repository: AvailabilityRepository = Depends(get_availability_repository),
) -> AvailabilityResponse:
    return repository.update(user_id, payload)
