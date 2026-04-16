import unittest

from core.schemas import REQUIRED_FIELDS_FOR_COMPLETION, SalesLead


class SalesLeadTests(unittest.TestCase):
    def test_required_fields_constant_matches_is_complete(self) -> None:
        self.assertEqual(
            REQUIRED_FIELDS_FOR_COMPLETION,
            (
                "name",
                "contact",
                "company",
                "need_summary",
                "timeline",
                "lead_temperature",
            ),
        )

    def test_is_complete_requires_plausible_contact(self) -> None:
        lead = SalesLead(
            name="Иван",
            contact="позвоните мне как-нибудь",
            company="ООО Ромашка",
            need_summary="Закупка CRM",
            timeline="до 1 месяца",
            lead_temperature="тёплый",
        )
        self.assertFalse(lead.is_complete())
        self.assertIn("contact", lead.missing_required_fields())

    def test_contact_email_normalized(self) -> None:
        lead = SalesLead(contact="  User@Example.COM ")
        self.assertEqual(lead.contact, "user@example.com")
        self.assertTrue(lead.contact_is_plausible(lead.contact or ""))

    def test_contact_ru_phone_normalized(self) -> None:
        lead = SalesLead(contact="8 (999) 123-45-67")
        self.assertEqual(lead.contact, "+79991234567")

    def test_lead_source_optional_for_completion(self) -> None:
        lead = SalesLead(
            name="Иван",
            contact="+79991234567",
            company="ИП Иванов",
            need_summary="Демо",
            timeline="до 2 недель",
            lead_temperature="горячий",
            lead_source=None,
        )
        self.assertTrue(lead.is_complete())
        self.assertEqual(lead.missing_required_fields(), ())


if __name__ == "__main__":
    unittest.main()
