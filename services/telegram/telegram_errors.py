"""Исключения при отправке сообщений в Telegram (аналогично доменным ошибкам в сервисах PEcb08)."""


class TelegramNotifierError(RuntimeError):
    """Базовая ошибка уведомления операторов."""


class TelegramSendError(TelegramNotifierError):
    """Не удалось отправить сообщение через Bot API."""
