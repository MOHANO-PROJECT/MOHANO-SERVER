import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import delete, select

from app.core.errors import ServiceError
from app.core.security import as_utc, utc_now
from app.db.session import SessionLocal
from app.models.matching import CallRequestRecord, CallSessionRecord, CallSignalRecord


@dataclass(frozen=True)
class StoredCallRequest:
    request_id: str
    requester_id: str
    recipient_id: str
    status: str
    created_at: datetime
    call_session_id: Optional[str]


@dataclass(frozen=True)
class StoredCallSession:
    session_id: str
    requester_id: str
    recipient_id: str
    status: str
    expires_at: datetime
    ended_at: Optional[datetime]


@dataclass(frozen=True)
class StoredCallSignal:
    signal_id: str
    sender_id: str
    signal_type: str
    payload: dict
    created_at: datetime
    expires_at: datetime


class CallRepository:
    """MySQL persistence for call requests, connection sessions, and SDP/ICE signals."""

    # A notification may need a few seconds to reach a backgrounded device and
    # for the recipient to open it. Keep an invitation valid for 14 seconds,
    # matching the app's four-second sending state plus 10-second reply window.
    # The shared deadline prevents a late acceptance from creating a one-sided
    # call session.
    request_timeout = timedelta(seconds=14)
    session_timeout = timedelta(minutes=10)
    signal_timeout = timedelta(minutes=10)

    def create_request(self, requester_id: str, recipient_id: str) -> StoredCallRequest:
        with SessionLocal.begin() as session:
            record = CallRequestRecord(
                requester_id=requester_id,
                recipient_id=recipient_id,
                status="pending",
            )
            session.add(record)
            session.flush()
            return self._request_state(session, record)

    def list_inbox(
        self, user_id: str, cursor: Optional[str], *, limit: int = 20
    ) -> tuple[list[StoredCallRequest], Optional[str]]:
        with SessionLocal.begin() as session:
            records = session.scalars(
                select(CallRequestRecord)
                .where(CallRequestRecord.recipient_id == user_id)
                .order_by(CallRequestRecord.created_at.desc(), CallRequestRecord.id.desc())
            ).all()
            for record in records:
                self._expire_request_if_needed(record)
            states = [self._request_state(session, record) for record in records]
            start = self._cursor_index([state.request_id for state in states], cursor)
            remaining = states[start:]
            page = remaining[:limit]
            return page, page[-1].request_id if len(remaining) > len(page) else None

    def get_request(self, user_id: str, request_id: str) -> StoredCallRequest:
        with SessionLocal.begin() as session:
            record = self._request_for_participant(session, user_id, request_id)
            self._expire_request_if_needed(record)
            session.flush()
            return self._request_state(session, record)

    def accept_request(self, user_id: str, request_id: str) -> StoredCallRequest:
        with SessionLocal.begin() as session:
            record = session.scalar(
                select(CallRequestRecord)
                .where(CallRequestRecord.id == request_id)
                .with_for_update()
            )
            self._assert_request_access(record, user_id)
            if record.recipient_id != user_id:
                raise ServiceError(
                    "call_request_forbidden",
                    "Only the recipient can accept this request",
                    403,
                )
            self._expire_request_if_needed(record)
            if record.status != "pending":
                raise ServiceError(
                    "call_request_not_pending",
                    "Call request is no longer pending",
                    409,
                )
            call_session = CallSessionRecord(
                call_request_id=record.id,
                requester_id=record.requester_id,
                recipient_id=record.recipient_id,
                status="connecting",
                expires_at=utc_now() + self.session_timeout,
            )
            session.add(call_session)
            record.status = "accepted"
            record.updated_at = utc_now()
            session.flush()
            return self._request_state(session, record)

    def reject_request(self, user_id: str, request_id: str) -> StoredCallRequest:
        return self._close_request(user_id, request_id, "rejected", "recipient_id")

    def cancel_request(self, user_id: str, request_id: str) -> StoredCallRequest:
        return self._close_request(user_id, request_id, "cancelled", "requester_id")

    def get_session(self, user_id: str, session_id: str) -> StoredCallSession:
        with SessionLocal.begin() as session:
            record = self._session_for_participant(session, user_id, session_id)
            self._expire_session_if_needed(record)
            session.flush()
            return self._session_state(record)

    def add_signal(
        self, user_id: str, session_id: str, signal_type: str, payload: dict
    ) -> StoredCallSignal:
        with SessionLocal.begin() as session:
            call_session = self._session_for_participant(session, user_id, session_id)
            self._expire_session_if_needed(call_session)
            if call_session.status != "connecting":
                raise ServiceError(
                    "call_session_closed", "Call session is no longer active", 409
                )
            signal = CallSignalRecord(
                session_id=session_id,
                sender_id=user_id,
                signal_type=signal_type,
                payload_json=json.dumps(payload, separators=(",", ":")),
                expires_at=utc_now() + self.signal_timeout,
            )
            session.add(signal)
            session.flush()
            return self._signal_state(signal)

    def list_signals(
        self, user_id: str, session_id: str, after: Optional[str]
    ) -> tuple[list[StoredCallSignal], Optional[str]]:
        with SessionLocal.begin() as session:
            call_session = self._session_for_participant(session, user_id, session_id)
            self._expire_session_if_needed(call_session)
            session.execute(
                delete(CallSignalRecord).where(
                    CallSignalRecord.session_id == session_id,
                    CallSignalRecord.expires_at <= utc_now(),
                )
            )
            records = session.scalars(
                select(CallSignalRecord)
                .where(
                    CallSignalRecord.session_id == session_id,
                    CallSignalRecord.sender_id != user_id,
                )
                .order_by(CallSignalRecord.created_at.asc(), CallSignalRecord.id.asc())
            ).all()
            start = self._after_cursor_index([record.id for record in records], after)
            page = records[start:]
            signals = [self._signal_state(record) for record in page]
            return signals, signals[-1].signal_id if signals else after

    def end_session(self, user_id: str, session_id: str) -> StoredCallSession:
        with SessionLocal.begin() as session:
            record = self._session_for_participant(session, user_id, session_id)
            self._expire_session_if_needed(record)
            if record.status == "connecting":
                record.status = "ended"
                record.ended_at = utc_now()
            session.flush()
            return self._session_state(record)

    def _close_request(
        self, user_id: str, request_id: str, status: str, permitted_field: str
    ) -> StoredCallRequest:
        with SessionLocal.begin() as session:
            record = session.scalar(
                select(CallRequestRecord)
                .where(CallRequestRecord.id == request_id)
                .with_for_update()
            )
            self._assert_request_access(record, user_id)
            if getattr(record, permitted_field) != user_id:
                raise ServiceError(
                    "call_request_forbidden",
                    "You cannot update this call request",
                    403,
                )
            self._expire_request_if_needed(record)
            if record.status != "pending":
                raise ServiceError(
                    "call_request_not_pending",
                    "Call request is no longer pending",
                    409,
                )
            record.status = status
            record.updated_at = utc_now()
            session.flush()
            return self._request_state(session, record)

    @staticmethod
    def _cursor_index(ids: list[str], cursor: Optional[str]) -> int:
        if cursor is None:
            return 0
        try:
            return ids.index(cursor) + 1
        except ValueError:
            return len(ids)

    @staticmethod
    def _after_cursor_index(ids: list[str], cursor: Optional[str]) -> int:
        if cursor is None:
            return 0
        try:
            return ids.index(cursor) + 1
        except ValueError:
            return len(ids)

    @staticmethod
    def _assert_request_access(
        record: Optional[CallRequestRecord], user_id: str
    ) -> None:
        if record is None:
            raise ServiceError("call_request_not_found", "Call request not found", 404)
        if user_id not in (record.requester_id, record.recipient_id):
            raise ServiceError(
                "call_request_forbidden", "You cannot access this call request", 403
            )

    def _request_for_participant(self, session, user_id: str, request_id: str) -> CallRequestRecord:
        record = session.get(CallRequestRecord, request_id)
        self._assert_request_access(record, user_id)
        return record

    @staticmethod
    def _session_for_participant(
        session, user_id: str, session_id: str
    ) -> CallSessionRecord:
        record = session.get(CallSessionRecord, session_id)
        if record is None:
            raise ServiceError("call_session_not_found", "Call session not found", 404)
        if user_id not in (record.requester_id, record.recipient_id):
            raise ServiceError(
                "call_session_forbidden", "You cannot access this call session", 403
            )
        return record

    def _expire_request_if_needed(self, record: CallRequestRecord) -> None:
        if (
            record.status == "pending"
            and as_utc(record.created_at) + self.request_timeout <= utc_now()
        ):
            record.status = "expired"
            record.updated_at = utc_now()

    @staticmethod
    def _expire_session_if_needed(record: CallSessionRecord) -> None:
        if record.status == "connecting" and as_utc(record.expires_at) <= utc_now():
            record.status = "expired"
            record.ended_at = utc_now()

    @staticmethod
    def _request_state(session, record: CallRequestRecord) -> StoredCallRequest:
        session_id = session.scalar(
            select(CallSessionRecord.id).where(
                CallSessionRecord.call_request_id == record.id
            )
        )
        return StoredCallRequest(
            request_id=record.id,
            requester_id=record.requester_id,
            recipient_id=record.recipient_id,
            status=record.status,
            created_at=record.created_at,
            call_session_id=session_id,
        )

    @staticmethod
    def _session_state(record: CallSessionRecord) -> StoredCallSession:
        return StoredCallSession(
            session_id=record.id,
            requester_id=record.requester_id,
            recipient_id=record.recipient_id,
            status=record.status,
            expires_at=record.expires_at,
            ended_at=record.ended_at,
        )

    @staticmethod
    def _signal_state(record: CallSignalRecord) -> StoredCallSignal:
        return StoredCallSignal(
            signal_id=record.id,
            sender_id=record.sender_id,
            signal_type=record.signal_type,
            payload=json.loads(record.payload_json),
            created_at=record.created_at,
            expires_at=record.expires_at,
        )
