import hashlib
import json
import logging
from typing import Any

import httpx

from core import LeadSession, SalesLead, Settings
from services.assistant import OpenAILeadAssistant
from services.telegram import OperatorNotifier
from services.workflow_errors import CrmWebhookError

logger = logging.getLogger(__name__)

FINAL_CLIENT_MESSAGE = (
    "Спасибо! Я передал вашу заявку менеджеру по продажам. "
    "С вами свяжутся в ближайшее время."
)

_MISSING_FIELD_HINTS_RU: dict[str, str] = {
    "name": "имя",
    "contact": "телефон, email или @username в Telegram",
    "company": "компания или тип клиента (например, частное лицо)",
    "need_summary": "краткое описание запроса",
    "timeline": "сроки решения из предложенных вариантов",
    "lead_temperature": "температура лида (горячий / тёплый / холодный)",
}


def build_crm_idempotency_key(user_id: int, lead: SalesLead) -> str:
    """Стабильный ключ для повторной отправки того же лида (ретраи CRM без дублей)."""
    payload = {"user_id": user_id, "lead": lead.model_dump(mode="json", exclude_none=True)}
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class LeadWorkflowService:
    def __init__(
        self,
        assistant: OpenAILeadAssistant,
        notifier: OperatorNotifier,
        settings: Settings,
    ) -> None:
        self._assistant = assistant
        self._notifier = notifier
        self._settings = settings
        self._metric_turns = 0
        self._metric_premature_ready = 0
        self._metric_submits = 0

    async def process_message(self, session: LeadSession, message_text: str) -> str:
        if session.submitted:
            session.reset()

        self._prefill_contact_from_telegram(session)
        history_before_turn = session.recent_history()
        is_new_session = not history_before_turn and not session.started

        turn = await self._assistant.generate_turn(
            current_lead=session.lead,
            user_message=message_text,
            is_new_session=is_new_session,
            conversation_history=history_before_turn,
            last_assistant_message=session.last_assistant_message,
            telegram_first_name=session.telegram_first_name,
        )

        session.add_user_message(message_text)
        session.lead.merge(turn.extracted_lead)
        session.started = True

        self._metric_turns += 1
        missing_after = session.lead.missing_required_fields()
        logger.debug(
            "lead_quality_turn user_id=%s missing=%s model_ready=%s is_complete=%s turns=%s",
            session.user_id,
            missing_after,
            turn.ready_to_submit,
            session.lead.is_complete(),
            self._metric_turns,
        )

        if session.lead.is_complete() and turn.ready_to_submit:
            await self._notifier.send_lead(session)
            try:
                await self._maybe_push_crm_webhook(session)
            except CrmWebhookError:
                pass
            session.submitted = True
            session.add_assistant_message(FINAL_CLIENT_MESSAGE)
            self._metric_submits += 1
            logger.info(
                "Lead submitted for user_id=%s | lead_quality submits=%s turns=%s premature_ready=%s rate=%.5f",
                session.user_id,
                self._metric_submits,
                self._metric_turns,
                self._metric_premature_ready,
                self._metric_premature_ready / self._metric_turns if self._metric_turns else 0.0,
            )
            return FINAL_CLIENT_MESSAGE

        reply = turn.reply
        if turn.ready_to_submit and not session.lead.is_complete():
            self._metric_premature_ready += 1
            reply = self._reply_for_incomplete_lead(session.lead)
            logger.info(
                "lead_quality_premature_ready user_id=%s missing=%s turns=%s premature=%s cumulative_rate=%.5f",
                session.user_id,
                session.lead.missing_required_fields(),
                self._metric_turns,
                self._metric_premature_ready,
                self._metric_premature_ready / self._metric_turns,
            )

        session.add_assistant_message(reply)
        return reply

    @staticmethod
    def _reply_for_incomplete_lead(lead: SalesLead) -> str:
        missing = lead.missing_required_fields()
        if not missing:
            return "Почти готово — проверьте, пожалуйста, формат контакта (телефон, email или @username)."
        labels = [_MISSING_FIELD_HINTS_RU.get(field, field) for field in missing]
        tail = ", ".join(labels[:4])
        if len(labels) > 4:
            tail += " и др."
        return f"Чтобы передать заявку менеджеру, не хватает: {tail}. Уточните, пожалуйста."

    async def _maybe_push_crm_webhook(self, session: LeadSession) -> None:
        url = (self._settings.crm_webhook_url or "").strip()
        if not url:
            return

        payload: dict[str, Any] = {
            "event": "lead_submitted",
            "ingestion_channel": "telegram_bot",
            "telegram": {
                "user_id": session.user_id,
                "chat_id": session.chat_id,
                "username": session.telegram_username,
                "first_name": session.telegram_first_name,
            },
            "lead": session.lead.model_dump(mode="json"),
        }
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Idempotency-Key": build_crm_idempotency_key(session.user_id, session.lead),
        }
        secret = (self._settings.crm_webhook_secret or "").strip()
        if secret:
            headers["Authorization"] = f"Bearer {secret}"

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=8.0)) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.exception(
                "CrmWebhookError: HTTP failure user_id=%s url=%s (%s)",
                session.user_id,
                url,
                type(exc).__name__,
            )
            raise CrmWebhookError("Сбой HTTP при отправке лида в CRM.") from exc
        except Exception as exc:
            logger.exception(
                "CrmWebhookError: unexpected error user_id=%s (%s)",
                session.user_id,
                type(exc).__name__,
            )
            raise CrmWebhookError("Неожиданная ошибка при отправке лида в CRM.") from exc

    @staticmethod
    def _prefill_contact_from_telegram(session: LeadSession) -> None:
        if session.lead.contact:
            return
        if session.telegram_username:
            session.lead.contact = f"@{session.telegram_username}"

    async def close(self) -> None:
        await self._assistant.close()
