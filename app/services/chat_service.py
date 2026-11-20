from typing import Optional

from app.core.errors import ServiceError
from app.repositories.chat_repository import ChatRepository, ChatSummary, StoredMessage
from app.schemas.chats import (
    ChatListItem,
    ChatListResponse,
    ChatMessage,
    MessageCreateRequest,
    MessageListResponse,
)
from app.services.database_profile_service import DatabaseProfileService
from app.services.push_notification_service import PushNotificationService
from app.services.monetization_service import MonetizationService
from app.schemas.monetization import ChatMonetizationStatus


class ChatService:
    """REST chat service backed by MySQL; delivery remains refresh-based for MVP."""

    def __init__(
        self,
        repository: ChatRepository,
        profile_service: DatabaseProfileService,
        push_notifications: PushNotificationService,
        monetization_service: MonetizationService,
    ) -> None:
        self._repository = repository
        self._profile_service = profile_service
        self._push_notifications = push_notifications
        self._monetization_service = monetization_service

    def list_chats(self, user_id: str, cursor: Optional[str]) -> ChatListResponse:
        self._ensure_demo_chat(user_id)
        records, next_cursor = self._repository.list_chats(user_id, cursor)
        items: list[ChatListItem] = []
        for record in records:
            try:
                items.append(self._chat_list_item(record))
            except ServiceError:
                # A counterpart that has been deleted cannot be exposed again.
                continue
        return ChatListResponse(items=items, next_cursor=next_cursor)

    def list_messages(
        self, user_id: str, chat_id: str, before: Optional[str]
    ) -> MessageListResponse:
        messages, next_cursor = self._repository.list_messages(user_id, chat_id, before)
        return MessageListResponse(
            items=[self._message_response(user_id, message) for message in messages],
            next_cursor=next_cursor,
        )

    def create_message(
        self, user_id: str, chat_id: str, payload: MessageCreateRequest
    ) -> ChatMessage:
        text = payload.text.strip()
        if not text:
            raise ServiceError("message_empty", "Message cannot be empty", 422)
        self._repository.counterpart_id(user_id, chat_id)
        self._monetization_service.consume_chat_message(user_id, chat_id)
        message = self._repository.create_message(user_id, chat_id, text)
        self._push_notifications.send_chat_message(
            recipient_id=self._repository.counterpart_id(user_id, chat_id),
            chat_id=chat_id,
        )
        return self._message_response(user_id, message)

    def monetization_status(self, user_id: str, chat_id: str) -> ChatMonetizationStatus:
        self._repository.counterpart_id(user_id, chat_id)
        return self._monetization_service.chat_status(user_id, chat_id)

    def complete_monetization_gate(
        self, user_id: str, chat_id: str
    ) -> ChatMonetizationStatus:
        self._repository.counterpart_id(user_id, chat_id)
        return self._monetization_service.complete_chat_gate(user_id, chat_id)

    def mark_read(self, user_id: str, chat_id: str) -> None:
        self._repository.mark_read(user_id, chat_id)

    def record_call_connected(self, requester_id: str, recipient_id: str) -> str:
        """Create/reuse a direct chat and persist its call-history system event."""
        return self._repository.record_call_connected(requester_id, recipient_id)

    def _ensure_demo_chat(self, user_id: str) -> None:
        if user_id == "mock-yuki":
            return
        try:
            self._profile_service.get_public_profile("mock-yuki")
        except ServiceError:
            # Demo data is present only in local development.
            return
        self._repository.ensure_demo_chat(user_id, "mock-yuki")

    def _chat_list_item(self, record: ChatSummary) -> ChatListItem:
        counterpart = self._profile_service.get_public_profile(record.counterpart_id)
        last_message = record.last_message
        return ChatListItem(
            chat_id=record.chat_id,
            counterpart_id=record.counterpart_id,
            counterpart=counterpart,
            last_message=last_message.text if last_message else None,
            last_message_at=last_message.created_at if last_message else None,
            unread_count=record.unread_count,
            last_message_type=(
                last_message.message_type if last_message else "message"
            ),
        )

    @staticmethod
    def _message_response(user_id: str, message: StoredMessage) -> ChatMessage:
        return ChatMessage(
            message_id=message.message_id,
            sender_id=message.sender_id or "system",
            text=message.text,
            created_at=message.created_at,
            is_mine=message.sender_id == user_id,
            message_type=message.message_type,
        )
