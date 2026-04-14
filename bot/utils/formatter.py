from core import SalesLead


def format_collected_lead(lead: SalesLead) -> str:
    lines = [
        f"Имя: {lead.name or '-'}",
        f"Контакт: {lead.contact or '-'}",
        f"Компания: {lead.company or '-'}",
        f"Интерес: {lead.need_summary or '-'}",
        f"Сроки: {lead.timeline or '-'}",
        f"Температура: {lead.lead_temperature or '-'}",
    ]
    return "\n".join(lines)
