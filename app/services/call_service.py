from typing import Optional

from app.core.errors import ServiceError
from app.repositories.availability_repository import AvailabilityRepository
from app.repositories.call_repository import (
    CallRepository,
    StoredCallRequest,
    StoredCallSession,
    StoredCallSignal,
)
from app.schemas.calls import (
    CallRequestCreateRequest,
    CallRequestListResponse,
    CallRequestResponse,
    CallSessionResponse,
    CallSignal,
    SignalCreateRequest,
    SignalListResponse,
)
from app.services.chat_service import ChatService
from app.services.database_profile_service import DatabaseProfileService
from app.services.push_notification_service import PushNotificationService


class CallService:
    """Coordinates call state and WebRTC signaling; audio never passes through this server."""

    def __init__(
        self,
        repository: CallRepository,
        profile_service: DatabaseProfileService,
        chat_service: ChatService,
        availability_repository: AvailabilityRepository,
        push_notifications: PushNotificationService,
    ) -> None:
        self._repository = repository
        self._profile_service = profile_service
        self._chat_service = chat_service
        self._availability_repository = availability_repository
        self._push_notifications = push_notifications

    def create_request(
        self, user_id: str, payload: CallRequestCreateRequest
    ) -> CallRequestResponse:
        if payload.candidate_id == user_id:
            raise ServiceError("candidate_not_found", "Candidate not found", 404)
        try:
            self._profile_service.get_public_profile(payload.candidate_id)
        except ServiceError as error:
            raise ServiceError(
                "candidate_not_found", "Candidate not found", 404
            ) from error
        if not self._availability_repository.is_contactable(payload.candidate_id):
            raise ServiceError(
                "candidate_unavailable", "This person is not available right now.", 409
            )
        request = self._repository.create_request(user_id, payload.candidate_id)
        self._push_notifications.send_incoming_call(
            recipient_id=request.recipient_id,
            request_id=request.request_id,
        )
        return self._request_response(user_id, request)

    def list_inbox(
        self, user_id: str, cursor: Optional[str]
    ) -> CallRequestListResponse:
        records, next_cursor = self._repository.list_inbox(user_id, cursor)
        return CallRequestListResponse(
            items=[self._request_response(user_id, record) for record in records],
            next_cursor=next_cursor,
        )

    def get_request(self, user_id: str, request_id: str) -> CallRequestResponse:
        return self._request_response(
            user_id, self._repository.get_request(user_id, request_id)
        )

    def accept_request(self, user_id: str, request_id: str) -> CallRequestResponse:
        request = self._repository.accept_request(user_id, request_id)
        self._chat_service.record_call_connected(
            request.requester_id, request.recipient_id
        )
        return self._request_response(user_id, request)

    def reject_request(self, user_id: str, request_id: str) -> CallRequestResponse:
        return self._request_response(
            user_id, self._repository.reject_request(user_id, request_id)
        )

    def cancel_request(self, user_id: str, request_id: str) -> CallRequestResponse:
        return self._request_response(
            user_id, self._repository.cancel_request(user_id, request_id)
        )

    def get_session(self, user_id: str, session_id: str) -> CallSessionResponse:
        return self._session_response(
            user_id, self._repository.get_session(user_id, session_id)
        )

    def add_signal(
        self, user_id: str, session_id: str, payload: SignalCreateRequest
    ) -> CallSignal:
        return self._signal_response(
            self._repository.add_signal(
                user_id, session_id, payload.signal_type, payload.payload
            )
        )

    def list_signals(
        self, user_id: str, session_id: str, after: Optional[str]
    ) -> SignalListResponse:
        signals, next_cursor = self._repository.list_signals(
            user_id, session_id, after
        )
        return SignalListResponse(
            items=[self._signal_response(signal) for signal in signals],
            next_cursor=next_cursor,
        )

    def end_session(self, user_id: str, session_id: str) -> CallSessionResponse:
        return self._session_response(
            user_id, self._repository.end_session(user_id, session_id)
        )

    def _request_response(
        self, user_id: str, request: StoredCallRequest
    ) -> CallRequestResponse:
        counterpart_id = (
            request.recipient_id
            if request.requester_id == user_id
            else request.requester_id
        )
        return CallRequestResponse(
            request_id=request.request_id,
            direction="outgoing" if request.requester_id == user_id else "incoming",
            status=request.status,
            counterpart_id=counterpart_id,
            counterpart=self._profile_service.get_public_profile(counterpart_id),
            created_at=request.created_at,
            call_session_id=request.call_session_id,
        )

    def _session_response(
        self, user_id: str, call_session: StoredCallSession
    ) -> CallSessionResponse:
        peer_id = (
            call_session.recipient_id
            if call_session.requester_id == user_id
            else call_session.requester_id
        )
        return CallSessionResponse(
            session_id=call_session.session_id,
            status=call_session.status,
            peer_id=peer_id,
            peer=self._profile_service.get_public_profile(peer_id),
            expires_at=call_session.expires_at,
            ended_at=call_session.ended_at,
        )

    @staticmethod
    def _signal_response(signal: StoredCallSignal) -> CallSignal:
        return CallSignal(
            signal_id=signal.signal_id,
            sender_id=signal.sender_id,
            signal_type=signal.signal_type,
            payload=signal.payload,
            created_at=signal.created_at,
            expires_at=signal.expires_at,
        )
