import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import Message

from core import LeadSession
from services import LeadWorkflowService, TelegramSendError
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

    try:
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
    except TelegramAPIError:
        logger.exception("Bot handler: TelegramAPIError on /start user_id=%s", user.id)
    except Exception:
        logger.exception("Bot handler: unexpected error on /start user_id=%s", user.id)


@router.message(Command("reset"))
async def handle_reset(
    message: Message,
    session_repository: InMemorySessionRepository,
) -> None:
    user = message.from_user
    if user is None:
        await message.answer("Не удалось сбросить диалог. Попробуйте ещё раз.")
        return

    try:
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
    except TelegramAPIError:
        logger.exception("Bot handler: TelegramAPIError on /reset user_id=%s", user.id)
    except Exception:
        logger.exception("Bot handler: unexpected error on /reset user_id=%s", user.id)


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
    except TelegramSendError:
        logger.exception(
            "Workflow: TelegramSendError (operator notification) user_id=%s chat_id=%s",
            user.id,
            message.chat.id,
        )
        try:
            await message.answer(GENERIC_ERROR_MESSAGE)
        except TelegramAPIError:
            logger.exception(
                "Bot handler: TelegramAPIError after TelegramSendError user_id=%s",
                user.id,
            )
        return
    except Exception:
        logger.exception(
            "Workflow: unexpected error in process_message user_id=%s chat_id=%s",
            user.id,
            message.chat.id,
        )
        try:
            await message.answer(GENERIC_ERROR_MESSAGE)
        except TelegramAPIError:
            logger.exception(
                "Bot handler: TelegramAPIError after workflow error user_id=%s",
                user.id,
            )
        return

    try:
        await message.answer(reply)
    except TelegramAPIError:
        logger.exception(
            "Bot handler: TelegramAPIError sending reply to user user_id=%s chat_id=%s",
            user.id,
            message.chat.id,
        )


@router.message()
async def handle_unsupported_message(message: Message) -> None:
    try:
        await message.answer(UNSUPPORTED_MESSAGE)
    except TelegramAPIError:
        logger.exception("Bot handler: TelegramAPIError on unsupported message type")
    except Exception:
        logger.exception("Bot handler: unexpected error on unsupported message type")
