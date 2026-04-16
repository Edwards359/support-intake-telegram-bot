"""Исключения сервиса LLM-ассистента (аналогично AIServiceError в data_assistant)."""


class AssistantServiceError(RuntimeError):
    """Базовая ошибка сервиса ассистента."""


class AssistantHTTPError(AssistantServiceError):
    """Сбой HTTP при вызове Chat Completions (после ретраев или немедленный 4xx)."""


class AssistantResponseParseError(AssistantServiceError):
    """Ответ API не удалось разобрать как JSON или не прошла валидация AssistantTurn."""
