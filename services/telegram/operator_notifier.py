from aiogram import Bot

from core import LeadSession, Settings


class OperatorNotifier:
    def __init__(self, bot: Bot, settings: Settings) -> None:
        self._bot = bot
        self._settings = settings

    async def send_lead(self, session: LeadSession) -> None:
        lead = session.lead
        lines = [
            "=== НОВЫЙ ЛИД (ПРОДАЖИ) ===",
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
        await self._bot.send_message(self._settings.operator_chat_id, "\n".join(lines))
