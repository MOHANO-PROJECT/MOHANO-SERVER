"""프로세스 수명 동안 공유되는 개발용 서비스 조립 지점."""

from app.repositories.auth_repository import AuthRepository
from app.repositories.advertising_consent_repository import AdvertisingConsentRepository
from app.repositories.account_repository import AccountRepository
from app.repositories.availability_repository import AvailabilityRepository
from app.repositories.chat_repository import ChatRepository
from app.repositories.call_repository import CallRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.policy_consent_repository import PolicyConsentRepository
from app.repositories.matching_repository import MatchingRepository
from app.repositories.safety_repository import SafetyRepository
from app.core.config import get_settings
from app.services.auth_service import AuthService
from app.services.advertising_consent_service import AdvertisingConsentService
from app.services.account_service import AccountService
from app.services.call_service import CallService
from app.services.chat_service import ChatService
from app.services.database_profile_service import DatabaseProfileService
from app.services.google_identity_verifier import GoogleIdentityVerifier
from app.services.apple_identity_verifier import AppleIdentityVerifier
from app.services.line_identity_verifier import LineIdentityVerifier
from app.services.kakao_identity_verifier import KakaoIdentityVerifier
from app.services.matching_service import MatchingService
from app.services.object_storage_service import ObjectStorageService
from app.services.policy_consent_service import PolicyConsentService
from app.services.push_notification_service import PushNotificationService
from app.services.safety_service import SafetyService

profile_service = DatabaseProfileService(
    ProfileRepository(),
    ObjectStorageService(get_settings()),
    seed_candidates=get_settings().environment == "local",
)
auth_repository = AuthRepository()
if get_settings().environment == "local":
    auth_repository.seed_local_test_identities()
auth_service = AuthService(
    auth_repository,
    GoogleIdentityVerifier(),
    AppleIdentityVerifier(),
    LineIdentityVerifier(),
    KakaoIdentityVerifier(),
)
policy_consent_service = PolicyConsentService(PolicyConsentRepository())
advertising_consent_service = AdvertisingConsentService(AdvertisingConsentRepository())
account_service = AccountService(AccountRepository(), ObjectStorageService(get_settings()))
availability_repository = AvailabilityRepository()
push_notification_service = PushNotificationService(
    get_settings(), availability_repository
)
matching_service = MatchingService(
    MatchingRepository(),
    profile_service,
    get_settings().jwt_secret_key,
)
chat_service = ChatService(ChatRepository(), profile_service, push_notification_service)
call_service = CallService(
    CallRepository(),
    profile_service,
    chat_service,
    availability_repository,
    push_notification_service,
)
safety_service = SafetyService(SafetyRepository())


def get_auth_service() -> AuthService:
    return auth_service


def get_account_service() -> AccountService:
    return account_service


def get_availability_repository() -> AvailabilityRepository:
    return availability_repository


def get_profile_service() -> DatabaseProfileService:
    return profile_service


def get_policy_consent_service() -> PolicyConsentService:
    return policy_consent_service


def get_advertising_consent_service() -> AdvertisingConsentService:
    return advertising_consent_service


def get_matching_service() -> MatchingService:
    return matching_service


def get_call_service() -> CallService:
    return call_service


def get_chat_service() -> ChatService:
    return chat_service


def get_safety_service() -> SafetyService:
    return safety_service
