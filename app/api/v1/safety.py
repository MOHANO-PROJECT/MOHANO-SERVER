from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id
from app.schemas.safety import (
    SafetyStatusResponse,
    UserReportCreateRequest,
    UserReportResponse,
)
from app.services.container import get_safety_service
from app.services.safety_service import SafetyService


router = APIRouter()


@router.post("/reports", response_model=UserReportResponse)
def create_user_report(
    payload: UserReportCreateRequest,
    user_id: str = Depends(get_current_user_id),
    service: SafetyService = Depends(get_safety_service),
) -> UserReportResponse:
    return service.submit_report(user_id, payload)


@router.get("/me/safety-status", response_model=SafetyStatusResponse)
def get_safety_status(
    user_id: str = Depends(get_current_user_id),
    service: SafetyService = Depends(get_safety_service),
) -> SafetyStatusResponse:
    return service.status(user_id)
