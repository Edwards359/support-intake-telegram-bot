import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from core import LeadSession
from services import LeadWorkflowService
from services.storage import InMemorySessionRepository

logger = logging.getLogger(__name__)
router = Router()

START_MESSAGE = (
    "Здравствуйте! Я помогу оставить заявку для отдела продаж. Как к вам обращаться?"
)
RESET_MESSAGE = "Диалог сброшен. Начнём заново. Как к вам обращаться?"
GENERIC_ERROR_MESSAGE = "Сейчас не удалось обработать сообщение. Попробуйте ещё раз через пару минут."
UNSUPPORTED_MESSAGE = "Пожалуйста, опишите запрос текстом — я передам его менеджеру по продажам."


@router.message(Command("start"))
async def handle_start(
    message: Message,
    session_repository: InMemorySessionRepository,
) -> None:
    user = message.from_user
    if user is None:
        await message.answer("Не удалось определить пользователя. Попробуйте ещё раз.")
        return

    session = session_repository.get_or_create(
        user_id=user.id,
        chat_id=message.chat.id,
        telegram_username=user.username,
        telegram_first_name=user.first_name,
    )
    session.reset()
    session.started = True

    if user.username:
        session.lead.contact = f"@{user.username}"

    session.add_assistant_message(START_MESSAGE)
    await message.answer(START_MESSAGE)


@router.message(Command("reset"))
async def handle_reset(
    message: Message,
    session_repository: InMemorySessionRepository,
) -> None:
    user = message.from_user
    if user is None:
        await message.answer("Не удалось сбросить диалог. Попробуйте ещё раз.")
        return

    session_repository.reset(user.id)
    session = session_repository.get_or_create(
        user_id=user.id,
        chat_id=message.chat.id,
        telegram_username=user.username,
        telegram_first_name=user.first_name,
    )
    session.started = True
    if user.username:
        session.lead.contact = f"@{user.username}"

    session.add_assistant_message(RESET_MESSAGE)
    await message.answer(RESET_MESSAGE)


@router.message(F.text)
async def handle_text_message(
    message: Message,
    session_repository: InMemorySessionRepository,
    workflow: LeadWorkflowService,
) -> None:
    user = message.from_user
    if user is None or not message.text:
        await message.answer("Не удалось обработать сообщение. Попробуйте ещё раз.")
        return

    session: LeadSession = session_repository.get_or_create(
        user_id=user.id,
        chat_id=message.chat.id,
        telegram_username=user.username,
        telegram_first_name=user.first_name,
    )

    try:
        reply = await workflow.process_message(session, message.text)
        await message.answer(reply)
    except Exception:
        logger.exception("Failed to process incoming lead message")
        await message.answer(GENERIC_ERROR_MESSAGE)


@router.message()
async def handle_unsupported_message(message: Message) -> None:
    await message.answer(UNSUPPORTED_MESSAGE)
