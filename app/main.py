import base64
import binascii
import logging
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import ServiceError


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    api_prefix = settings.api_v1_prefix.rstrip("/") or "/v1"
    docs_enabled = settings.environment != "prod"
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url=f"{api_prefix}/docs" if docs_enabled else None,
        redoc_url=f"{api_prefix}/redoc" if docs_enabled else None,
        openapi_url=f"{api_prefix}/openapi.json" if docs_enabled else None,
    )

    # Protect non-production API documentation with the browser's native
    # HTTP Basic Authentication prompt. Production documentation is disabled
    # above, so these paths are not registered there at all.
    docs_paths = {
        f"{api_prefix}/docs",
        f"{api_prefix}/redoc",
        f"{api_prefix}/openapi.json",
    }
    docs_auth_required = settings.environment in {"dev", "staging"}

    def valid_docs_credentials(request: Request) -> bool:
        authorization = request.headers.get("Authorization", "")
        scheme, _, encoded = authorization.partition(" ")
        if scheme.lower() != "basic" or not encoded:
            return False

        try:
            decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
            username, password = decoded.split(":", 1)
        except (binascii.Error, ValueError, UnicodeDecodeError):
            return False

        return secrets.compare_digest(username, settings.docs_basic_auth_username) and secrets.compare_digest(
            password,
            settings.docs_basic_auth_password,
        )

    @app.middleware("http")
    async def protect_api_docs(request: Request, call_next):
        path = request.url.path.rstrip("/") or "/"
        if docs_auth_required and path in docs_paths:
            if not settings.docs_basic_auth_username or not settings.docs_basic_auth_password:
                return JSONResponse(
                    status_code=503,
                    content={
                        "code": "docs_auth_not_configured",
                        "message": "API documentation authentication is not configured.",
                    },
                )
            if not valid_docs_credentials(request):
                return Response(
                    status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="MOHANO API docs"'},
                )
        return await call_next(request)

    @app.exception_handler(ServiceError)
    async def handle_service_error(_: Request, error: ServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"code": error.code, "message": error.message},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, error: Exception) -> JSONResponse:
        # 개인정보·credential을 남기지 않도록 예외 본문이나 요청값은 로그에 쓰지 않는다.
        logger.error("Unhandled server error: %s", type(error).__name__)
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_server_error",
                "message": "The server could not complete this request.",
            },
        )

    if settings.cors_origins or settings.cors_origin_regex:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_origin_regex=settings.cors_origin_regex or None,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
