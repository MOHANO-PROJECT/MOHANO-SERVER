from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_token
from app.core.errors import ServiceError
from app.repositories.auth_repository import AuthRepository
from app.services.container import get_safety_service
from app.services.safety_service import SafetyService

bearer_scheme = HTTPBearer(auto_error=True)


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """access JWT에서 현재 사용자 ID만 꺼낸다.

    사용자 존재 여부와 도메인 권한 검사는 각 서비스가 담당한다.
    """

    payload = decode_token(credentials.credentials, expected_type="access")
    user_id = str(payload["sub"])
    if not AuthRepository().user_exists(user_id):
        raise ServiceError("user_unavailable", "User unavailable", 401)
    return user_id


def get_current_interaction_user_id(
    user_id: str = Depends(get_current_user_id),
    safety_service: SafetyService = Depends(get_safety_service),
) -> str:
    """Ensures a logged-in user is not temporarily restricted from interactions."""

    safety_service.assert_interactions_allowed(user_id)
    return user_id
