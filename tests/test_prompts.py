import unittest

from services.assistant.prompts import LEAD_ASSISTANT_PROMPT, LEAD_ASSISTANT_PROMPT_ALT, lead_system_prompt


class LeadSystemPromptTests(unittest.TestCase):
    def test_default_variant(self) -> None:
        self.assertEqual(lead_system_prompt("default"), LEAD_ASSISTANT_PROMPT)
        self.assertEqual(lead_system_prompt("DEFAULT"), LEAD_ASSISTANT_PROMPT)
        self.assertEqual(lead_system_prompt("unknown"), LEAD_ASSISTANT_PROMPT)

    def test_alt_variant(self) -> None:
        self.assertEqual(lead_system_prompt("alt"), LEAD_ASSISTANT_PROMPT_ALT)
        self.assertEqual(lead_system_prompt(" ALT "), LEAD_ASSISTANT_PROMPT_ALT)


if __name__ == "__main__":
    unittest.main()
