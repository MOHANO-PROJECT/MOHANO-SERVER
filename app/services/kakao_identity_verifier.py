"""Kakao access-token verification for MOHANO account sessions."""

from dataclasses import dataclass
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import Settings, get_settings
from app.core.errors import ServiceError


@dataclass(frozen=True)
class VerifiedKakaoIdentity:
    subject: str


class KakaoIdentityVerifier:
    """Validates a native Kakao access token directly with Kakao.

    Kakao's token-info response contains both the service user ID and the app
    ID for which the token was issued. Both values must be checked server-side;
    no client-provided profile or email field participates in identity lookup.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def verify(self, access_token: str) -> VerifiedKakaoIdentity:
        expected_app_id = self._settings.kakao_app_id.strip()
        if not expected_app_id or expected_app_id.startswith("replace-with-"):
            raise ServiceError(
                "kakao_sign_in_not_configured",
                "Kakao sign-in is not configured on this server.",
                503,
            )
        if not access_token or access_token != access_token.strip() or "\r" in access_token or "\n" in access_token:
            raise ServiceError("invalid_kakao_access_token", "Kakao sign-in could not be verified.", 401)

        request = Request(
            self._settings.kakao_access_token_info_url,
            headers={"Authorization": f"Bearer {access_token}"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=10) as response:  # noqa: S310 - fixed Kakao endpoint/config
                token_info = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise ServiceError(
                "invalid_kakao_access_token",
                "Kakao sign-in could not be verified.",
                401,
            ) from error
        except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ServiceError(
                "kakao_verification_unavailable",
                "Kakao sign-in verification is temporarily unavailable.",
                503,
            ) from error

        if not isinstance(token_info, dict):
            raise ServiceError("invalid_kakao_access_token", "Kakao sign-in could not be verified.", 401)
        subject = token_info.get("id")
        app_id = token_info.get("app_id")
        if isinstance(subject, bool) or isinstance(app_id, bool) or subject is None or app_id is None:
            raise ServiceError("invalid_kakao_access_token", "Kakao sign-in could not be verified.", 401)
        if str(app_id) != expected_app_id:
            raise ServiceError("invalid_kakao_access_token", "Kakao sign-in could not be verified.", 401)
        return VerifiedKakaoIdentity(subject=str(subject))
