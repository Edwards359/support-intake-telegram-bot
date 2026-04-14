from typing import Literal

from pydantic import BaseModel, Field, field_validator


LeadTimeline = Literal["до 2 недель", "до 1 месяца", "1-3 месяца", "позже / не определились"]
LeadTemperature = Literal["горячий", "тёплый", "холодный"]
MessageRole = Literal["user", "assistant"]


class SalesLead(BaseModel):
    name: str | None = None
    contact: str | None = None
    company: str | None = None
    need_summary: str | None = None
    timeline: LeadTimeline | None = None
    lead_temperature: LeadTemperature | None = None

    @field_validator("name", "contact", "company", "need_summary")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split()).strip()
        return cleaned or None

    def merge(self, other: "SalesLead") -> None:
        for field_name, value in other.model_dump().items():
            if value not in (None, ""):
                setattr(self, field_name, value)

    def is_complete(self) -> bool:
        return all(
            [
                self.name,
                self.contact,
                self.company,
                self.need_summary,
                self.timeline,
                self.lead_temperature,
            ]
        )


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
