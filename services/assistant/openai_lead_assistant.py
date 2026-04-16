import asyncio
import json
import logging
import re

import httpx
from pydantic import ValidationError

from core import AssistantTurn, REQUIRED_FIELDS_FOR_COMPLETION, SalesLead, Settings
from core.schemas import DialogueMessage, LeadTemperature, LeadTimeline
from services.assistant.prompts import LEAD_RESPONSE_SCHEMA, lead_system_prompt
from services.lead_contact_tools import extract_contact_from_free_text

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


class OpenAILeadAssistant:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.openai_base_url,
            timeout=httpx.Timeout(45.0, connect=12.0),
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
        )

    async def generate_turn(
        self,
        current_lead: SalesLead,
        user_message: str,
        is_new_session: bool,
        conversation_history: list[DialogueMessage],
        last_assistant_message: str | None,
        telegram_first_name: str | None,
    ) -> AssistantTurn:
        payload = {
            "model": self._settings.openai_model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": lead_system_prompt(self._settings.prompt_variant)},
                {
                    "role": "user",
                    "content": self._build_user_prompt(
                        current_lead=current_lead,
                        user_message=user_message,
                        is_new_session=is_new_session,
                        conversation_history=conversation_history,
                        last_assistant_message=last_assistant_message,
                        telegram_first_name=telegram_first_name,
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": LEAD_RESPONSE_SCHEMA,
            },
        }

        def fallback_turn() -> AssistantTurn:
            return self._build_fallback_turn(
                current_lead=current_lead,
                user_message=user_message,
                is_new_session=is_new_session,
                conversation_history=conversation_history,
                last_assistant_message=last_assistant_message,
                telegram_first_name=telegram_first_name,
            )

        try:
            response = await self._post_with_retries(payload)
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return AssistantTurn.model_validate(json.loads(content))
        except json.JSONDecodeError:
            logger.exception("AssistantResponseParseError: invalid JSON in API response or model content")
            return fallback_turn()
        except ValidationError:
            logger.exception("AssistantResponseParseError: AssistantTurn validation failed for model output")
            return fallback_turn()
        except (KeyError, IndexError, TypeError) as exc:
            logger.exception(
                "AssistantServiceError: unexpected chat/completions payload shape (%s)",
                type(exc).__name__,
            )
            return fallback_turn()
        except httpx.HTTPError:
            logger.exception("AssistantHTTPError: chat completions failed")
            return fallback_turn()
        except Exception as exc:
            logger.exception(
                "AssistantServiceError: unexpected error during generate_turn (%s)",
                type(exc).__name__,
            )
            return fallback_turn()

    async def close(self) -> None:
        try:
            await self._client.aclose()
        except Exception as exc:
            logger.exception(
                "AssistantServiceError: failed to close httpx client (%s)",
                type(exc).__name__,
            )

    async def _post_with_retries(self, payload: dict) -> httpx.Response:
        last_error: Exception | None = None

        for attempt in range(1, 4):
            try:
                response = await self._client.post("/chat/completions", json=payload)
                if response.status_code in RETRYABLE_STATUS_CODES:
                    response.raise_for_status()
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status_code = exc.response.status_code
                logger.warning(
                    "OpenAILeadAssistant HTTPStatusError attempt=%s status=%s",
                    attempt,
                    status_code,
                )
                if status_code not in RETRYABLE_STATUS_CODES or attempt == 3:
                    raise
            except httpx.RequestError as exc:
                last_error = exc
                logger.warning(
                    "OpenAILeadAssistant RequestError attempt=%s type=%s",
                    attempt,
                    type(exc).__name__,
                )
                if attempt == 3:
                    break

            await asyncio.sleep(0.75 * attempt)

        assert last_error is not None
        logger.error(
            "AssistantHTTPError: exhausted retries (%s)",
            type(last_error).__name__,
            exc_info=last_error,
        )
        raise last_error

    @staticmethod
    def _build_user_prompt(
        current_lead: SalesLead,
        user_message: str,
        is_new_session: bool,
        conversation_history: list[DialogueMessage],
        last_assistant_message: str | None,
        telegram_first_name: str | None,
    ) -> str:
        lead_json = json.dumps(current_lead.model_dump(), ensure_ascii=False, indent=2)
        history_json = json.dumps(
            [message.model_dump() for message in conversation_history],
            ensure_ascii=False,
            indent=2,
        )
        missing = list(current_lead.missing_required_fields())
        missing_json = json.dumps(missing, ensure_ascii=False)
        required_json = json.dumps(list(REQUIRED_FIELDS_FOR_COMPLETION), ensure_ascii=False)
        first_name = telegram_first_name or "null"
        last_bot_message = last_assistant_message or "null"

        return (
            f"is_new_session: {str(is_new_session).lower()}\n"
            f"telegram_first_name: {first_name}\n"
            f"required_fields_for_completion: {required_json}\n"
            f"missing_required_fields_for_completion: {missing_json}\n"
            f"current_lead:\n{lead_json}\n\n"
            f"conversation_history:\n{history_json}\n\n"
            f"last_assistant_message:\n{last_bot_message}\n\n"
            f"latest_user_message:\n{user_message}"
        )

    def _build_fallback_turn(
        self,
        current_lead: SalesLead,
        user_message: str,
        is_new_session: bool,
        conversation_history: list[DialogueMessage],
        last_assistant_message: str | None,
        telegram_first_name: str | None,
    ) -> AssistantTurn:
        message = self._normalize_text(user_message)
        message_lower = message.lower()
        extracted = SalesLead()
        requested_field = self._detect_requested_field(last_assistant_message)

        if self._is_repeat_question_request(message_lower):
            repeated_question = last_assistant_message or "Пока мы не дошли до следующего вопроса."
            return AssistantTurn(
                reply=f"Последний мой вопрос был таким: {repeated_question}",
                extracted_lead=extracted,
                ready_to_submit=current_lead.is_complete(),
            )

        if not current_lead.name and self._looks_like_name(message):
            extracted.name = message

        if not current_lead.contact:
            contact = self._extract_contact(message)
            if contact:
                extracted.contact = contact

        if requested_field == "name" and not extracted.name and self._looks_like_name(message):
            extracted.name = message
        elif requested_field == "contact" and not extracted.contact:
            extracted.contact = self._extract_contact(message)
        elif requested_field == "company" and not extracted.company:
            extracted.company = self._extract_company(message)
        elif requested_field == "need":
            ns = self._extract_need_summary(message, current_lead)
            if ns:
                extracted.need_summary = ns
        elif requested_field == "timeline":
            extracted.timeline = self._extract_timeline(message_lower)
        elif requested_field == "temperature":
            extracted.lead_temperature = self._extract_temperature(message_lower)

        if not extracted.need_summary and not current_lead.need_summary and not self._looks_like_name(message):
            ns = self._extract_need_summary(message, current_lead)
            if ns:
                extracted.need_summary = ns

        if not extracted.company and not current_lead.company and requested_field == "company":
            extracted.company = self._extract_company(message)

        if not extracted.company and not current_lead.company and len(message.split()) <= 6:
            if any(x in message_lower for x in ["ооо", "ип ", "ип,", "компани", "организац", "физлиц", "частн"]):
                extracted.company = message

        if not extracted.timeline and not current_lead.timeline:
            extracted.timeline = self._extract_timeline(message_lower)

        if not extracted.lead_temperature and not current_lead.lead_temperature:
            extracted.lead_temperature = self._extract_temperature(message_lower)

        merged_lead = current_lead.model_copy(deep=True)
        merged_lead.merge(extracted)

        reply = self._build_fallback_reply(
            merged_lead=merged_lead,
            extracted=extracted,
            is_new_session=is_new_session,
            conversation_history=conversation_history,
            telegram_first_name=telegram_first_name,
        )

        return AssistantTurn(
            reply=reply,
            extracted_lead=extracted,
            ready_to_submit=merged_lead.is_complete(),
        )

    def _build_fallback_reply(
        self,
        merged_lead: SalesLead,
        extracted: SalesLead,
        is_new_session: bool,
        conversation_history: list[DialogueMessage],
        telegram_first_name: str | None,
    ) -> str:
        if not conversation_history and is_new_session and not extracted.name and not merged_lead.name:
            return (
                "Здравствуйте! Я помогу оставить заявку для отдела продаж. "
                "Как к вам обращаться?"
            )

        if not merged_lead.name:
            return "Подскажите, как к вам обращаться?"

        if not merged_lead.contact:
            return "Оставьте контакт для связи: телефон, email или Telegram."

        if not merged_lead.company:
            return "Вы представляете компанию или оформляете запрос как частное лицо / ИП? Напишите название или «частное лицо»."

        if not merged_lead.need_summary:
            name = merged_lead.name or telegram_first_name
            prefix = f"{name}, " if name else ""
            return f"{prefix}кратко опишите, что вас интересует: продукт, услуга или задача."

        if not merged_lead.timeline:
            return (
                "Когда планируете принять решение? Выберите ближайший вариант: "
                "до 2 недель, до 1 месяца, 1-3 месяца, позже / не определились."
            )

        if not merged_lead.lead_temperature:
            return "Как бы вы оценили готовность: горячий (срочно нужно), тёплый или холодный (пока изучаю)?"

        return "Спасибо! Проверяю, всё ли собрано по заявке."

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join(value.split()).strip()

    @staticmethod
    def _is_repeat_question_request(message_lower: str) -> bool:
        triggers = [
            "какой был прошлый вопрос",
            "какой был предыдущий вопрос",
            "повтори вопрос",
            "повтори последний вопрос",
            "что ты спрашивал",
            "что вы спрашивали",
        ]
        return any(trigger in message_lower for trigger in triggers)

    @staticmethod
    def _detect_requested_field(last_assistant_message: str | None) -> str | None:
        if not last_assistant_message:
            return None

        message = last_assistant_message.lower()
        if any(phrase in message for phrase in ["как к вам обращаться", "как вас зовут"]):
            return "name"
        if any(phrase in message for phrase in ["контакт", "телефон", "email", "telegram"]):
            return "contact"
        if any(phrase in message for phrase in ["компани", "ип", "частное лицо", "представляете"]):
            return "company"
        if any(phrase in message for phrase in ["интерес", "задач", "что вас интересует", "опишите"]):
            return "need"
        if any(phrase in message for phrase in ["когда планируете", "сроки", "до 2 недель"]):
            return "timeline"
        if any(phrase in message for phrase in ["готовность", "горячий", "тёплый", "холодный", "температур"]):
            return "temperature"
        return None

    @staticmethod
    def _looks_like_name(message: str) -> bool:
        lowered = message.lower()
        blockers = [
            "ооо ",
            "ооо«",
            "ип ",
            "компани",
            "срочно",
            "горяч",
            "холодн",
            "недел",
            "месяц",
            "email",
            "@",
        ]
        if any(blocker in lowered for blocker in blockers):
            return False
        if any(char.isdigit() for char in message):
            return False
        words = [word for word in re.split(r"\s+", message) if word]
        return 1 <= len(words) <= 3

    @staticmethod
    def _extract_contact(message: str) -> str | None:
        return extract_contact_from_free_text(message)

    @staticmethod
    def _extract_company(message: str) -> str | None:
        cleaned = " ".join(message.split()).strip()
        if not cleaned or len(cleaned) > 120:
            return None
        return cleaned

    def _extract_need_summary(self, message: str, current_lead: SalesLead) -> str | None:
        cleaned = self._normalize_text(message)
        if not cleaned:
            return None
        if self._looks_like_name(cleaned) and not any(
            token in cleaned.lower() for token in ["лиценз", "подписк", "crm", "интеграц", "закуп", "заказ"]
        ):
            return None
        existing = current_lead.need_summary
        if existing and cleaned.lower() in existing.lower():
            return None
        if existing and len(cleaned.split()) <= 6:
            return f"{existing.rstrip('.')} {cleaned}".strip()
        return cleaned

    @staticmethod
    def _extract_timeline(message_lower: str) -> LeadTimeline | None:
        if any(t in message_lower for t in ["2 недел", "две недел", "неделю", "срочно на этой неделе"]):
            return "до 2 недель"
        if "3 месяц" in message_lower or "квартал" in message_lower or "полгода" in message_lower:
            return "1-3 месяца"
        if "месяц" in message_lower or "30 дней" in message_lower:
            return "до 1 месяца"
        if any(
            t in message_lower
            for t in ["не знаю", "не определ", "позже", "пока смотр", "изучаем", "год", "долго"]
        ):
            return "позже / не определились"
        return None

    @staticmethod
    def _extract_temperature(message_lower: str) -> LeadTemperature | None:
        if any(t in message_lower for t in ["горяч", "срочно", "критично", "как можно скорее", "сегодня"]):
            return "горячий"
        if any(t in message_lower for t in ["холодн", "пока смотр", "информац", "просто интересно", "не планиру"]):
            return "холодный"
        if any(t in message_lower for t in ["тёпл", "тепл", "думаем", "обсуждаем", "скорее да"]):
            return "тёплый"
        return None
