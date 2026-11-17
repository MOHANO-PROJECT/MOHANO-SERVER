from app.core.errors import ServiceError
from app.repositories.safety_repository import SafetyRepository
from app.schemas.safety import (
    SafetyStatusResponse,
    UserReportCreateRequest,
    UserReportResponse,
)


class SafetyService:
    """Applies user-reporting limits and interaction restrictions."""

    def __init__(self, repository: SafetyRepository) -> None:
        self._repository = repository

    def submit_report(
        self, reporter_id: str, payload: UserReportCreateRequest
    ) -> UserReportResponse:
        report = self._repository.submit_report(reporter_id, payload)
        return UserReportResponse(
            report_id=report.report_id,
            created_at=report.created_at,
            remaining_reports=report.remaining_reports,
        )

    def status(self, user_id: str) -> SafetyStatusResponse:
        restricted_until = self._repository.restriction_status(user_id)
        return SafetyStatusResponse(
            restricted=restricted_until is not None,
            restricted_until=restricted_until,
        )

    def assert_interactions_allowed(self, user_id: str) -> None:
        if self._repository.restriction_status(user_id) is not None:
            raise ServiceError(
                "account_restricted",
                "Your account is temporarily restricted from matching, chatting, and calls",
                403,
            )
