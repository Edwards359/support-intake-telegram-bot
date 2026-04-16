"""
Детерминированное извлечение контакта (телефон / email / @username) без вызова LLM.

Используется в fallback-ассистенте и может вызываться из других слоёв как «инструмент»
нормализации — единая логика с проверкой plausibility в SalesLead.
"""

from __future__ import annotations

import re

from core.schemas import SalesLead

_EMAIL_INLINE = re.compile(
    r"[a-zA-Z0-9](?:[a-zA-Z0-9._%+-]*[a-zA-Z0-9])?@[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?\.[a-zA-Z]{2,}",
)


def extract_contact_from_free_text(message: str) -> str | None:
    """Возвращает нормализованный контакт или None, если в тексте нет допустимого контакта."""
    raw = message.strip()
    if not raw:
        return None

    if raw.startswith("@"):
        handle = raw.split()[0]
        if SalesLead.contact_is_plausible(handle):
            return SalesLead.normalize_contact_value(handle)
        return None

    email_match = _EMAIL_INLINE.search(message)
    if email_match:
        candidate = email_match.group(0)
        if SalesLead.contact_is_plausible(candidate):
            return SalesLead.normalize_contact_value(candidate)

    digits = re.sub(r"\D", "", message)
    if len(digits) >= 10 and SalesLead.contact_is_plausible(message):
        return SalesLead.normalize_contact_value(message)
    return None
