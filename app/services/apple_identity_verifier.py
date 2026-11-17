"""Apple ID token verification for MOHANO account sessions."""

from dataclasses import dataclass

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError, PyJWTError

from app.core.config import Settings, get_settings
from app.core.errors import ServiceError


@dataclass(frozen=True)
class VerifiedAppleIdentity:
    subject: str
    email: str | None


class AppleIdentityVerifier:
    """Verifies Apple-signed ID tokens with Apple's current public signing keys."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._jwks_client = PyJWKClient(self._settings.apple_jwks_url)

    def verify(self, credential: str, *, nonce: str) -> VerifiedAppleIdentity:
        audiences = self._settings.apple_client_ids
        if not audiences:
            raise ServiceError(
                "apple_sign_in_not_configured",
                "Apple sign-in is not configured on this server.",
                503,
            )

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(credential)
            claims = jwt.decode(
                credential,
                signing_key.key,
                algorithms=["RS256"],
                audience=audiences,
                issuer="https://appleid.apple.com",
                options={"require": ["aud", "exp", "iat", "iss", "sub", "nonce"]},
            )
        except (PyJWKClientError, PyJWTError, ValueError) as error:
            raise ServiceError(
                "invalid_apple_id_token",
                "Apple sign-in could not be verified.",
                401,
            ) from error

        if claims.get("nonce") != nonce:
            raise ServiceError(
                "invalid_apple_id_token",
                "Apple sign-in could not be verified.",
                401,
            )
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise ServiceError(
                "invalid_apple_id_token",
                "Apple sign-in could not be verified.",
                401,
            )
        email = claims.get("email")
        return VerifiedAppleIdentity(
            subject=subject,
            email=email if isinstance(email, str) else None,
        )
