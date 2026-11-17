from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import distinct, func, or_, select, update

from app.core.errors import ServiceError
from app.core.security import as_utc, utc_now
from app.db.session import SessionLocal
from app.models.matching import CallRequestRecord, CallSessionRecord
from app.models.safety import SafetyActionRecord, UserReportRecord
from app.models.user import User
from app.schemas.safety import UserReportCreateRequest


@dataclass(frozen=True)
class StoredUserReport:
    report_id: str
    created_at: datetime
    remaining_reports: int


class SafetyRepository:
    """MySQL storage and atomic enforcement for reports and temporary restrictions."""

    report_window = timedelta(hours=24)
    report_limit = 5
    restriction_reporter_threshold = 3
    restriction_duration = timedelta(days=1)

    def submit_report(
        self, reporter_id: str, payload: UserReportCreateRequest
    ) -> StoredUserReport:
        if reporter_id == payload.reported_user_id:
            raise ServiceError("cannot_report_self", "You cannot report yourself", 422)

        now = utc_now()
        window_started_at = now - self.report_window
        with SessionLocal.begin() as session:
            # Lock in a deterministic order so concurrent reports cannot exceed the
            # per-user quota or create multiple restrictions for the same target.
            users = session.scalars(
                select(User)
                .where(User.id.in_((reporter_id, payload.reported_user_id)))
                .order_by(User.id.asc())
                .with_for_update()
            ).all()
            users_by_id = {user.id: user for user in users}
            reporter = users_by_id.get(reporter_id)
            reported = users_by_id.get(payload.reported_user_id)
            if reporter is None or reporter.status not in ("active", "seed"):
                raise ServiceError("user_unavailable", "User unavailable", 401)
            if reported is None or reported.status not in ("active", "seed"):
                raise ServiceError("reported_user_not_found", "User not found", 404)

            report_count = session.scalar(
                select(func.count(UserReportRecord.id)).where(
                    UserReportRecord.reporter_id == reporter_id,
                    UserReportRecord.created_at >= window_started_at,
                )
            ) or 0
            if report_count >= self.report_limit:
                raise ServiceError(
                    "report_rate_limited",
                    "You can submit up to five reports in 24 hours",
                    429,
                )

            duplicate = session.scalar(
                select(UserReportRecord.id).where(
                    UserReportRecord.reporter_id == reporter_id,
                    UserReportRecord.reported_user_id == payload.reported_user_id,
                    UserReportRecord.created_at >= window_started_at,
                )
            )
            if duplicate is not None:
                raise ServiceError(
                    "duplicate_report",
                    "You have already reported this user in the last 24 hours",
                    409,
                )

            report = UserReportRecord(
                reporter_id=reporter_id,
                reported_user_id=payload.reported_user_id,
                reason=payload.reason,
                evidence=payload.evidence,
            )
            session.add(report)
            session.flush()

            last_action_at = session.scalar(
                select(func.max(SafetyActionRecord.triggered_at)).where(
                    SafetyActionRecord.user_id == payload.reported_user_id,
                    SafetyActionRecord.action_type == "auto_restriction",
                )
            )
            threshold_started_at = window_started_at
            if last_action_at is not None:
                threshold_started_at = max(threshold_started_at, as_utc(last_action_at))
            distinct_reporter_count = session.scalar(
                select(func.count(distinct(UserReportRecord.reporter_id))).where(
                    UserReportRecord.reported_user_id == payload.reported_user_id,
                    UserReportRecord.created_at >= threshold_started_at,
                )
            ) or 0

            restriction_is_active = (
                reported.restricted_until is not None
                and as_utc(reported.restricted_until) > now
            )
            if (
                distinct_reporter_count >= self.restriction_reporter_threshold
                and not restriction_is_active
            ):
                restricted_until = now + self.restriction_duration
                reported.restricted_until = restricted_until
                session.add(
                    SafetyActionRecord(
                        user_id=reported.id,
                        action_type="auto_restriction",
                        reason="three_distinct_reports",
                        report_window_started_at=threshold_started_at,
                        reporter_count=distinct_reporter_count,
                        triggered_at=now,
                        restricted_until=restricted_until,
                    )
                )
                # A newly restricted account must not leave a pending or connected
                # counterpart in an active call state.
                session.execute(
                    update(CallRequestRecord)
                    .where(
                        or_(
                            CallRequestRecord.requester_id == reported.id,
                            CallRequestRecord.recipient_id == reported.id,
                        ),
                        CallRequestRecord.status == "pending",
                    )
                    .values(status="cancelled", updated_at=now)
                )
                session.execute(
                    update(CallSessionRecord)
                    .where(
                        or_(
                            CallSessionRecord.requester_id == reported.id,
                            CallSessionRecord.recipient_id == reported.id,
                        ),
                        CallSessionRecord.status == "connecting",
                    )
                    .values(status="ended", ended_at=now)
                )

            return StoredUserReport(
                report_id=report.id,
                created_at=report.created_at,
                remaining_reports=self.report_limit - report_count - 1,
            )

    def restriction_status(self, user_id: str) -> datetime | None:
        with SessionLocal() as session:
            user = session.get(User, user_id)
            if user is None or user.status not in ("active", "seed"):
                raise ServiceError("user_unavailable", "User unavailable", 401)
            if user.restricted_until is None or as_utc(user.restricted_until) <= utc_now():
                return None
            return user.restricted_until
