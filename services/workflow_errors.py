"""Исключения оркестрации лида и CRM-вебхука."""


class WorkflowServiceError(RuntimeError):
    """Базовая ошибка сценария обработки лида."""


class CrmWebhookError(WorkflowServiceError):
    """Сбой вызова CRM_WEBHOOK_URL после успешной отправки в чат менеджеров."""
