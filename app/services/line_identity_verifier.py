"""LINE ID token verification for MOHANO account sessions."""

from dataclasses import dataclass
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import Settings, get_settings
from app.core.errors import ServiceError


@dataclass(frozen=True)
class VerifiedLineIdentity:
    subject: str
    email: str | None


class LineIdentityVerifier:
    """Asks LINE to validate a client-supplied OpenID Connect ID token.

    Client profile fields are intentionally ignored. The verified LINE response
    is the only source used for the provider subject and optional email.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def verify(self, credential: str, *, nonce: str) -> VerifiedLineIdentity:
        channel_id = self._settings.line_channel_id.strip()
        if not channel_id:
            raise ServiceError(
                "line_sign_in_not_configured",
                "LINE sign-in is not configured on this server.",
                503,
            )

        payload = urlencode(
            {
                "id_token": credential,
                "client_id": channel_id,
                "nonce": nonce,
            }
        ).encode("utf-8")
        request = Request(
            self._settings.line_verify_id_token_url,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:  # noqa: S310 - fixed LINE endpoint/config
                claims = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise ServiceError(
                "invalid_line_id_token",
                "LINE sign-in could not be verified.",
                401,
            ) from error
        except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ServiceError(
                "line_verification_unavailable",
                "LINE sign-in verification is temporarily unavailable.",
                503,
            ) from error

        if not isinstance(claims, dict):
            raise ServiceError("invalid_line_id_token", "LINE sign-in could not be verified.", 401)
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise ServiceError("invalid_line_id_token", "LINE sign-in could not be verified.", 401)
        if (
            claims.get("iss") != "https://access.line.me"
            or claims.get("aud") != channel_id
            or claims.get("nonce") != nonce
        ):
            raise ServiceError("invalid_line_id_token", "LINE sign-in could not be verified.", 401)
        email = claims.get("email")
        return VerifiedLineIdentity(
            subject=subject,
            email=email if isinstance(email, str) else None,
        )
