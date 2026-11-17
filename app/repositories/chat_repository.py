from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select

from app.core.errors import ServiceError
from app.core.security import utc_now
from app.db.session import SessionLocal
from app.models.chat import Conversation, ConversationMember, MessageRecord


@dataclass(frozen=True)
class StoredMessage:
    message_id: str
    sender_id: Optional[str]
    text: str
    message_type: str
    created_at: datetime


@dataclass(frozen=True)
class ChatSummary:
    chat_id: str
    counterpart_id: str
    last_message: Optional[StoredMessage]
    unread_count: int
    activity_at: datetime


class ChatRepository:
    """MySQL persistence for direct conversations, messages, and read state."""

    def list_chats(
        self, user_id: str, cursor: Optional[str], *, limit: int = 20
    ) -> tuple[list[ChatSummary], Optional[str]]:
        with SessionLocal.begin() as session:
            memberships = session.scalars(
                select(ConversationMember).where(ConversationMember.user_id == user_id)
            ).all()
            summaries: list[ChatSummary] = []
            for membership in memberships:
                member_ids = session.scalars(
                    select(ConversationMember.user_id).where(
                        ConversationMember.conversation_id == membership.conversation_id
                    )
                ).all()
                # Direct chats only. A deleted user is removed from membership,
                # so the remaining participant no longer sees the conversation.
                if len(member_ids) != 2 or user_id not in member_ids:
                    continue
                counterpart_id = next(member_id for member_id in member_ids if member_id != user_id)
                conversation = session.get(Conversation, membership.conversation_id)
                if conversation is None:
                    continue
                last = session.scalar(
                    select(MessageRecord)
                    .where(MessageRecord.conversation_id == conversation.id)
                    .order_by(MessageRecord.created_at.desc(), MessageRecord.id.desc())
                    .limit(1)
                )
                unread_query = select(func.count()).select_from(MessageRecord).where(
                    MessageRecord.conversation_id == conversation.id,
                    MessageRecord.sender_id.is_not(None),
                    MessageRecord.sender_id != user_id,
                )
                if membership.last_read_at is not None:
                    unread_query = unread_query.where(
                        MessageRecord.created_at > membership.last_read_at
                    )
                unread_count = int(session.scalar(unread_query) or 0)
                summaries.append(
                    ChatSummary(
                        chat_id=conversation.id,
                        counterpart_id=counterpart_id,
                        last_message=self._stored_message(last) if last is not None else None,
                        unread_count=unread_count,
                        activity_at=last.created_at if last is not None else conversation.created_at,
                    )
                )

            summaries.sort(key=lambda item: (item.activity_at, item.chat_id), reverse=True)
            start = self._cursor_index([item.chat_id for item in summaries], cursor)
            remaining = summaries[start:]
            page = remaining[:limit]
            next_cursor = page[-1].chat_id if len(remaining) > len(page) else None
            return page, next_cursor

    def list_messages(
        self, user_id: str, chat_id: str, before: Optional[str], *, limit: int = 50
    ) -> tuple[list[StoredMessage], Optional[str]]:
        with SessionLocal.begin() as session:
            self._conversation_for_member(session, user_id, chat_id)
            messages = session.scalars(
                select(MessageRecord)
                .where(MessageRecord.conversation_id == chat_id)
                .order_by(MessageRecord.created_at.asc(), MessageRecord.id.asc())
            ).all()
            if before is not None:
                try:
                    messages = messages[:next(index for index, item in enumerate(messages) if item.id == before)]
                except StopIteration:
                    messages = []
            page = messages[-limit:]
            next_cursor = page[0].id if len(messages) > len(page) else None
            return [self._stored_message(item) for item in page], next_cursor

    def create_message(self, user_id: str, chat_id: str, text: str) -> StoredMessage:
        with SessionLocal.begin() as session:
            self._conversation_for_member(session, user_id, chat_id)
            message = MessageRecord(
                conversation_id=chat_id,
                sender_id=user_id,
                text=text,
                message_type="message",
            )
            session.add(message)
            session.flush()
            return self._stored_message(message)

    def counterpart_id(self, user_id: str, chat_id: str) -> str:
        with SessionLocal() as session:
            self._conversation_for_member(session, user_id, chat_id)
            member_ids = session.scalars(
                select(ConversationMember.user_id).where(
                    ConversationMember.conversation_id == chat_id
                )
            ).all()
            try:
                return next(member_id for member_id in member_ids if member_id != user_id)
            except StopIteration as error:
                raise ServiceError("chat_not_found", "Chat not found", 404) from error

    def mark_read(self, user_id: str, chat_id: str) -> None:
        with SessionLocal.begin() as session:
            membership = self._conversation_for_member(session, user_id, chat_id)
            membership.last_read_at = utc_now()

    def record_call_connected(self, requester_id: str, recipient_id: str) -> str:
        with SessionLocal.begin() as session:
            conversation, _ = self._get_or_create_pair_chat(
                session, requester_id, recipient_id
            )
            session.add(
                MessageRecord(
                    conversation_id=conversation.id,
                    sender_id=None,
                    text="call_connected",
                    message_type="call_connected",
                )
            )
            session.flush()
            return conversation.id

    def ensure_demo_chat(self, user_id: str, counterpart_id: str) -> None:
        with SessionLocal.begin() as session:
            conversation, created = self._get_or_create_pair_chat(
                session, user_id, counterpart_id
            )
            if not created:
                return
            session.add_all(
                [
                    MessageRecord(
                        conversation_id=conversation.id,
                        sender_id=counterpart_id,
                        text="Hi! How is your day going?",
                        message_type="message",
                    ),
                    MessageRecord(
                        conversation_id=conversation.id,
                        sender_id=None,
                        text="call_connected",
                        message_type="call_connected",
                    ),
                ]
            )

    @staticmethod
    def _cursor_index(ids: list[str], cursor: Optional[str]) -> int:
        if cursor is None:
            return 0
        try:
            return ids.index(cursor) + 1
        except ValueError:
            return len(ids)

    def _get_or_create_pair_chat(self, session, first_user_id: str, second_user_id: str) -> tuple[Conversation, bool]:
        candidate_ids = session.scalars(
            select(ConversationMember.conversation_id).where(
                ConversationMember.user_id == first_user_id
            )
        ).all()
        for conversation_id in candidate_ids:
            member_ids = session.scalars(
                select(ConversationMember.user_id).where(
                    ConversationMember.conversation_id == conversation_id
                )
            ).all()
            if set(member_ids) == {first_user_id, second_user_id} and len(member_ids) == 2:
                conversation = session.get(Conversation, conversation_id)
                if conversation is not None:
                    return conversation, False

        conversation = Conversation()
        session.add(conversation)
        session.flush()
        session.add_all(
            [
                ConversationMember(conversation_id=conversation.id, user_id=first_user_id),
                ConversationMember(conversation_id=conversation.id, user_id=second_user_id),
            ]
        )
        return conversation, True

    @staticmethod
    def _conversation_for_member(session, user_id: str, chat_id: str) -> ConversationMember:
        conversation = session.get(Conversation, chat_id)
        if conversation is None:
            raise ServiceError("chat_not_found", "Chat not found", 404)
        membership = session.get(ConversationMember, (chat_id, user_id))
        if membership is None:
            raise ServiceError("chat_forbidden", "You cannot access this chat", 403)
        return membership

    @staticmethod
    def _stored_message(message: MessageRecord) -> StoredMessage:
        return StoredMessage(
            message_id=message.id,
            sender_id=message.sender_id,
            text=message.text,
            message_type=message.message_type,
            created_at=message.created_at,
        )
