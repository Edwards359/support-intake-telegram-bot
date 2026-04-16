import unittest

from services.lead_contact_tools import extract_contact_from_free_text
from services.workflow import build_crm_idempotency_key


class LeadContactToolsTests(unittest.TestCase):
    def test_extract_phone_ru(self) -> None:
        self.assertEqual(extract_contact_from_free_text("звоните 8 (903) 111-22-33"), "+79031112233")

    def test_extract_email(self) -> None:
        self.assertEqual(
            extract_contact_from_free_text("пишите на A.B@Example.ru спасибо"),
            "a.b@example.ru",
        )

    def test_extract_telegram_handle(self) -> None:
        self.assertEqual(extract_contact_from_free_text("@valid_user_1 привет"), "@valid_user_1")

    def test_no_contact_in_garbage(self) -> None:
        self.assertIsNone(extract_contact_from_free_text("просто позвоните как-нибудь"))


class CrmIdempotencyTests(unittest.TestCase):
    def test_same_lead_same_key(self) -> None:
        from core.schemas import SalesLead

        lead = SalesLead(name="Иван", contact="+79991234567", company="ООО Тест")
        k1 = build_crm_idempotency_key(42, lead)
        k2 = build_crm_idempotency_key(42, lead)
        self.assertEqual(k1, k2)
        self.assertEqual(len(k1), 64)

    def test_different_user_different_key(self) -> None:
        from core.schemas import SalesLead

        lead = SalesLead(name="Иван", contact="+79991234567", company="ООО Тест")
        self.assertNotEqual(build_crm_idempotency_key(1, lead), build_crm_idempotency_key(2, lead))


if __name__ == "__main__":
    unittest.main()
