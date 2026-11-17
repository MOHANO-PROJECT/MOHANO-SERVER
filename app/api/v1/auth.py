from urllib.parse import parse_qsl, urlencode

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import RedirectResponse

from app.schemas.auth import (
    AppleExchangeRequest,
    GoogleExchangeRequest,
    KakaoExchangeRequest,
    LineExchangeRequest,
    LocalTestLoginRequest,
    RefreshTokenRequest,
    TokenPair,
)
from app.services.auth_service import AuthService
from app.services.container import get_auth_service
from app.core.config import get_settings

router = APIRouter()


@router.post("/anonymous", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def create_anonymous_session(
    service: AuthService = Depends(get_auth_service),
) -> TokenPair:
    return service.create_anonymous_session()


@router.post("/google/exchange", response_model=TokenPair)
def exchange_google_id_token(
    payload: GoogleExchangeRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenPair:
    return service.sign_in_with_google(payload)


@router.post("/apple/exchange", response_model=TokenPair)
def exchange_apple_id_token(
    payload: AppleExchangeRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenPair:
    return service.sign_in_with_apple(payload)


@router.post("/line/exchange", response_model=TokenPair)
def exchange_line_id_token(
    payload: LineExchangeRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenPair:
    return service.sign_in_with_line(payload)


@router.post("/kakao/exchange", response_model=TokenPair)
def exchange_kakao_access_token(
    payload: KakaoExchangeRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenPair:
    return service.sign_in_with_kakao(payload)


@router.post("/apple/callback", include_in_schema=False)
async def forward_apple_android_callback(request: Request) -> RedirectResponse:
    """Return Apple's form POST to Android's Sign in with Apple callback activity.

    Apple only posts this data after the provider flow. The Android app never
    accepts it as a login until `/apple/exchange` verifies the signed ID token.
    """
    raw_body = (await request.body()).decode("utf-8", errors="replace")
    accepted_keys = {"code", "id_token", "state", "user", "error", "error_description"}
    parameters = [
        (key, value)
        for key, value in parse_qsl(raw_body, keep_blank_values=True)
        if key in accepted_keys
    ]
    query = urlencode(parameters)
    package_id = get_settings().apple_android_package_id
    target = (
        f"intent://callback?{query}#Intent;package={package_id};"
        "scheme=signinwithapple;end"
    )
    return RedirectResponse(url=target, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.post("/local-test/login", response_model=TokenPair)
def sign_in_with_local_test_account(
    payload: LocalTestLoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenPair:
    return service.sign_in_with_local_test_account(payload)


@router.post("/refresh", response_model=TokenPair)
def refresh_session(
    payload: RefreshTokenRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenPair:
    return service.refresh_session(payload)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: RefreshTokenRequest,
    service: AuthService = Depends(get_auth_service),
) -> Response:
    service.logout(payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
