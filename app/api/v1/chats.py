from typing import Optional

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_current_interaction_user_id
from app.schemas.chats import ChatListResponse, ChatMessage, MessageCreateRequest, MessageListResponse
from app.schemas.monetization import ChatMonetizationStatus
from app.services.chat_service import ChatService
from app.services.container import get_chat_service

router = APIRouter(prefix="/chats")


@router.get("", response_model=ChatListResponse)
def list_chats(
    cursor: Optional[str] = None,
    user_id: str = Depends(get_current_interaction_user_id),
    service: ChatService = Depends(get_chat_service),
) -> ChatListResponse:
    return service.list_chats(user_id, cursor)


@router.get("/{chat_id}/messages", response_model=MessageListResponse)
def list_messages(
    chat_id: str,
    before: Optional[str] = None,
    user_id: str = Depends(get_current_interaction_user_id),
    service: ChatService = Depends(get_chat_service),
) -> MessageListResponse:
    return service.list_messages(user_id, chat_id, before)


@router.get("/{chat_id}/monetization", response_model=ChatMonetizationStatus)
def get_chat_monetization_status(
    chat_id: str,
    user_id: str = Depends(get_current_interaction_user_id),
    service: ChatService = Depends(get_chat_service),
) -> ChatMonetizationStatus:
    return service.monetization_status(user_id, chat_id)


@router.post("/{chat_id}/advertising-gate/complete", response_model=ChatMonetizationStatus)
def complete_chat_advertising_gate(
    chat_id: str,
    user_id: str = Depends(get_current_interaction_user_id),
    service: ChatService = Depends(get_chat_service),
) -> ChatMonetizationStatus:
    return service.complete_monetization_gate(user_id, chat_id)


@router.post("/{chat_id}/messages", response_model=ChatMessage)
def create_message(
    chat_id: str,
    payload: MessageCreateRequest,
    user_id: str = Depends(get_current_interaction_user_id),
    service: ChatService = Depends(get_chat_service),
) -> ChatMessage:
    return service.create_message(user_id, chat_id, payload)


@router.post("/{chat_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_chat_read(
    chat_id: str,
    user_id: str = Depends(get_current_interaction_user_id),
    service: ChatService = Depends(get_chat_service),
) -> Response:
    service.mark_read(user_id, chat_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
