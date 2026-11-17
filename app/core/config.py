from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MOHANO_", extra="ignore")

    app_name: str = "MOHANO Server"
    environment: str = "local"
    api_v1_prefix: str = "/v1"
    docs_basic_auth_username: str = ""
    docs_basic_auth_password: str = ""
    database_url: str = "mysql+pymysql://mohano:0000@127.0.0.1:3306/mohano?charset=utf8mb4"
    # Cloud Run can scale beyond one container. Keep the default pool deliberately
    # small so the entry-level Cloud SQL instance is not exhausted by idle DB
    # connections. Production values can be adjusted through environment vars.
    database_pool_size: int = 3
    database_max_overflow: int = 1
    database_pool_timeout_seconds: int = 30
    jwt_secret_key: str = "replace-this-before-running"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    google_web_client_id: str = ""
    apple_client_ids_raw: str = ""
    apple_jwks_url: str = "https://appleid.apple.com/auth/keys"
    apple_android_package_id: str = "com.example.mohano"
    line_channel_id: str = ""
    line_verify_id_token_url: str = "https://api.line.me/oauth2/v2.1/verify"
    kakao_app_id: str = ""
    kakao_access_token_info_url: str = "https://kapi.kakao.com/v1/user/access_token_info"
    fcm_enabled: bool = False
    firebase_project_id: str = ""
    firebase_credentials_path: str = ""
    cors_origins_raw: str = ""
    cors_origin_regex: str = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
    object_storage_endpoint: str = "http://127.0.0.1:9000"
    object_storage_public_endpoint: str = ""
    object_storage_access_key: str = "mohano"
    object_storage_secret_key: str = "00000000"
    object_storage_bucket: str = "mohano-profile-images"
    object_storage_region: str = "us-east-1"
    object_storage_upload_url_expire_seconds: int = 600
    object_storage_read_url_expire_seconds: int = 900
    profile_photo_max_bytes: int = 10 * 1024 * 1024

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def apple_client_ids(self) -> list[str]:
        return [client_id.strip() for client_id in self.apple_client_ids_raw.split(",") if client_id.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
