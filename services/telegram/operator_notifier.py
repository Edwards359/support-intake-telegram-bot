import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from core import LeadSession, Settings

from .telegram_errors import TelegramSendError

logger = logging.getLogger(__name__)


class OperatorNotifier:
    def __init__(self, bot: Bot, settings: Settings) -> None:
        self._bot = bot
        self._settings = settings

    async def send_lead(self, session: LeadSession) -> None:
        lead = session.lead
        lines = [
            "=== НОВЫЙ ЛИД (ПРОДАЖИ) ===",
            "",
            "Канал: Telegram-бот",
            f"Откуда узнали: {lead.lead_source or '—'}",
            "",
            f"Имя: {lead.name}",
            f"Контакт: {lead.contact}",
            f"Компания / тип: {lead.company}",
            "",
            "Интерес / задача:",
            f"{lead.need_summary}",
            "",
            f"Сроки решения: {lead.timeline}",
            f"Температура: {lead.lead_temperature}",
            "",
            f"Telegram user id: {session.user_id}",
            f"Telegram username: @{session.telegram_username}" if session.telegram_username else "Telegram username: -",
            "",
            "=== КОНЕЦ ===",
        ]
        text = "\n".join(lines)
        try:
            await self._bot.send_message(self._settings.operator_chat_id, text)
        except TelegramAPIError as exc:
            logger.exception(
                "TelegramSendError: failed to send lead to operator_chat_id=%s user_id=%s (%s)",
                self._settings.operator_chat_id,
                session.user_id,
                type(exc).__name__,
            )
            raise TelegramSendError("Не удалось отправить лид в чат менеджеров.") from exc
