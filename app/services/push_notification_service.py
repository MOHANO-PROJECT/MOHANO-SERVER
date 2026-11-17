import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

from app.core.config import Settings
from app.repositories.availability_repository import AvailabilityRepository


logger = logging.getLogger(__name__)


class PushNotificationService:
    """Best-effort Firebase Cloud Messaging delivery.

    A push payload is deliberately limited to an event type and opaque resource
    ID. The Flutter client re-reads the protected call/chat API after a tap or
    foreground event, so a stale or forged payload cannot reveal user data.
    """

    def __init__(
        self, settings: Settings, availability_repository: AvailabilityRepository
    ) -> None:
        self._settings = settings
        self._availability_repository = availability_repository
        self._unavailable_logged = False
        # Push delivery is an external best-effort side effect. A slow Firebase
        # response must never delay the call-request or chat-message API.
        self._delivery_executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="mohano-fcm"
        )

    def send_incoming_call(self, *, recipient_id: str, request_id: str) -> None:
        self._schedule(
            recipient_id=recipient_id,
            event_type="incoming_call",
            resource_key="request_id",
            resource_id=request_id,
        )

    def send_chat_message(self, *, recipient_id: str, chat_id: str) -> None:
        self._schedule(
            recipient_id=recipient_id,
            event_type="chat_message",
            resource_key="chat_id",
            resource_id=chat_id,
        )

    def _schedule(self, **kwargs: str) -> None:
        self._delivery_executor.submit(self._send, **kwargs)

    def _send(
        self,
        *,
        recipient_id: str,
        event_type: str,
        resource_key: str,
        resource_id: str,
    ) -> None:
        target = self._availability_repository.get_push_target(recipient_id)
        if target is None:
            return
        token, locale = target
        messaging = self._messaging_module()
        if messaging is None:
            return
        title, body = self._localized_content(event_type, locale)

        try:
            messaging.send(
                messaging.Message(
                    token=token,
                    data={"type": event_type, resource_key: resource_id},
                    notification=messaging.Notification(title=title, body=body),
                    android=self._android_config(event_type, messaging),
                )
            )
        except messaging.UnregisteredError:
            self._availability_repository.clear_push_token_if_matches(
                recipient_id, token
            )
        except Exception as error:
            # Never log tokens, payloads, message text, or user identifiers.
            logger.warning("FCM delivery failed: %s", type(error).__name__)

    def _messaging_module(self):
        if not self._settings.fcm_enabled:
            return None
        try:
            import firebase_admin
            from firebase_admin import credentials, messaging

            try:
                firebase_admin.get_app()
            except ValueError:
                credentials_path = self._settings.firebase_credentials_path.strip()
                credential = (
                    credentials.Certificate(credentials_path)
                    if credentials_path and Path(credentials_path).is_file()
                    else credentials.ApplicationDefault()
                )
                options = (
                    {"projectId": self._settings.firebase_project_id}
                    if self._settings.firebase_project_id
                    else None
                )
                firebase_admin.initialize_app(credential, options)
            return messaging
        except Exception as error:
            if not self._unavailable_logged:
                logger.warning("FCM initialization failed: %s", type(error).__name__)
                self._unavailable_logged = True
            return None

    @staticmethod
    def _localized_content(event_type: str, locale: str) -> tuple[str, str]:
        """Uses the recipient's app language without exposing either user in a preview."""
        content = {
            "incoming_call": {
                "en": ("MOHANO", "Someone would like to talk with you."),
                "ja": ("MOHANO", "新しい会話のお誘いが届いています。"),
                "ko": ("MOHANO", "새로운 대화 신청이 도착했어요."),
            },
            "chat_message": {
                "en": ("MOHANO", "You have a new message."),
                "ja": ("MOHANO", "新しいメッセージが届いています。"),
                "ko": ("MOHANO", "새로운 메시지가 도착했어요."),
            },
        }
        localized_event = content.get(event_type, content["chat_message"])
        return localized_event.get(locale, localized_event["en"])

    @staticmethod
    def _android_config(event_type: str, messaging):
        is_call_invitation = event_type == "incoming_call"
        return messaging.AndroidConfig(
            priority="high",
            # A call invitation is actionable for only 14 seconds. Do not let
            # Android surface it after the server has expired the request.
            ttl=timedelta(seconds=14) if is_call_invitation else timedelta(hours=1),
            notification=messaging.AndroidNotification(
                channel_id=(
                    "mohano_call_requests"
                    if is_call_invitation
                    else "mohano_messages"
                ),
                sound="default",
            ),
        )
