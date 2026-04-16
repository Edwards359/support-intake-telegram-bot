import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


LeadTimeline = Literal["до 2 недель", "до 1 месяца", "1-3 месяца", "позже / не определились"]
LeadTemperature = Literal["горячий", "тёплый", "холодный"]
MessageRole = Literal["user", "assistant"]

# Поля, без которых `SalesLead.is_complete()` ложно (синхронизировать с промптом и JSON Schema).
REQUIRED_FIELDS_FOR_COMPLETION: tuple[str, ...] = (
    "name",
    "contact",
    "company",
    "need_summary",
    "timeline",
    "lead_temperature",
)

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9](?:[a-zA-Z0-9._%+-]*[a-zA-Z0-9])?@[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?\.[a-zA-Z]{2,}"
)
_TG_RE = re.compile(r"^@[A-Za-z][A-Za-z0-9_]{3,31}$")


class SalesLead(BaseModel):
    name: str | None = None
    contact: str | None = None
    company: str | None = None
    need_summary: str | None = None
    timeline: LeadTimeline | None = None
    lead_temperature: LeadTemperature | None = None
    lead_source: str | None = Field(
        default=None,
        max_length=200,
        description="Откуда клиент узнал о вас (рекомендация, поиск, реклама и т.п.). Не обязательно для завершения.",
    )

    @field_validator("name", "contact", "company", "need_summary", "lead_source")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split()).strip()
        return cleaned or None

    @field_validator("contact")
    @classmethod
    def normalize_contact(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = " ".join(value.split()).strip()
        if not trimmed:
            return None
        if cls.contact_is_plausible(trimmed):
            return cls.normalize_contact_value(trimmed)
        return trimmed

    def merge(self, other: "SalesLead") -> None:
        for field_name, value in other.model_dump().items():
            if value not in (None, ""):
                setattr(self, field_name, value)

    @staticmethod
    def contact_is_plausible(value: str | None) -> bool:
        if value is None:
            return False
        candidate = value.strip()
        if not candidate:
            return False
        if SalesLead._looks_email(candidate):
            return True
        if SalesLead._looks_telegram_username(candidate):
            return True
        if SalesLead._looks_phone(candidate):
            return True
        return False

    @staticmethod
    def _looks_email(value: str) -> bool:
        match = _EMAIL_RE.fullmatch(value.strip())
        return bool(match)

    @staticmethod
    def _looks_telegram_username(value: str) -> bool:
        return bool(_TG_RE.match(value.strip()))

    @staticmethod
    def _looks_phone(value: str) -> bool:
        digits = re.sub(r"\D", "", value)
        if len(digits) < 10 or len(digits) > 15:
            return False
        if len(set(digits)) < 2:
            return False
        return True

    @staticmethod
    def normalize_contact_value(value: str) -> str:
        raw = value.strip()
        if SalesLead._looks_email(raw):
            return raw.lower()
        if SalesLead._looks_telegram_username(raw):
            return raw if raw.startswith("@") else f"@{raw}"
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 11 and digits.startswith("8"):
            digits = "7" + digits[1:]
        elif len(digits) == 10 and digits.startswith("9"):
            digits = "7" + digits
        if len(digits) == 11 and digits.startswith("7"):
            return "+" + digits
        if 10 <= len(digits) <= 15:
            return "+" + digits
        return raw

    def missing_required_fields(self) -> tuple[str, ...]:
        missing: list[str] = []
        for field in REQUIRED_FIELDS_FOR_COMPLETION:
            val = getattr(self, field)
            if field in ("timeline", "lead_temperature"):
                if val is None:
                    missing.append(field)
                continue
            if val is None or (isinstance(val, str) and not val.strip()):
                missing.append(field)
                continue
            if field == "contact" and isinstance(val, str) and not self.contact_is_plausible(val):
                missing.append(field)
        return tuple(missing)

    def is_complete(self) -> bool:
        """Лид готов к передаче менеджеру: все поля из REQUIRED_FIELDS_FOR_COMPLETION и контакт проходит проверку."""
        return len(self.missing_required_fields()) == 0


class DialogueMessage(BaseModel):
    role: MessageRole
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = " ".join(value.split()).strip()
        if not cleaned:
            raise ValueError("Dialogue message cannot be empty")
        return cleaned


class AssistantTurn(BaseModel):
    reply: str = Field(min_length=1)
    extracted_lead: SalesLead = Field(default_factory=SalesLead)
    ready_to_submit: bool = False


class LeadSession(BaseModel):
    user_id: int
    chat_id: int
    telegram_username: str | None = None
    telegram_first_name: str | None = None
    started: bool = False
    submitted: bool = False
    lead: SalesLead = Field(default_factory=SalesLead)
    history: list[DialogueMessage] = Field(default_factory=list)

    def add_user_message(self, text: str) -> None:
        self._append_history("user", text)

    def add_assistant_message(self, text: str) -> None:
        self._append_history("assistant", text)

    def recent_history(self, limit: int = 8) -> list[DialogueMessage]:
        return list(self.history[-limit:])

    @property
    def last_assistant_message(self) -> str | None:
        for message in reversed(self.history):
            if message.role == "assistant":
                return message.text
        return None

    def reset(self) -> None:
        self.started = False
        self.submitted = False
        self.lead = SalesLead()
        self.history = []

    def _append_history(self, role: MessageRole, text: str) -> None:
        self.history.append(DialogueMessage(role=role, text=text))
        if len(self.history) > 20:
            self.history = self.history[-20:]
