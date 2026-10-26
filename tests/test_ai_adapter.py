"""Unit tests for AI core integration adapter (Phase 8)."""

from __future__ import annotations

import unittest

from actions.base import ActionResult
from ui.ai_adapter import AICoreAdapter, map_action_result_to_response
from ui.assistant_interface import AssistantResponse


class TestAICoreAdapter(unittest.TestCase):
    def test_map_action_result_success(self):
        act_res = ActionResult.ok(
            message="Application 'notepad' opened successfully.",
            data={"pid": 1234},
        )
        resp = map_action_result_to_response(act_res)
        self.assertTrue(resp.success)
        self.assertEqual(resp.text, "Application 'notepad' opened successfully.")
        self.assertIsNone(resp.error)

    def test_map_action_result_failure(self):
        act_res = ActionResult.fail(
            message="Application 'nonexistent' not found.",
            error="ApplicationNotFoundError",
        )
        resp = map_action_result_to_response(act_res)
        self.assertFalse(resp.success)
        self.assertEqual(resp.text, "Application 'nonexistent' not found.")
        self.assertEqual(resp.error, "ApplicationNotFoundError")

    def test_map_invalid_action_result(self):
        resp = map_action_result_to_response("not an action result")  # type: ignore
        self.assertFalse(resp.success)
        self.assertEqual(resp.error, "Invalid ActionResult type")

    def test_adapter_with_custom_callable(self):
        def fake_ai(text: str):
            if "fail" in text:
                raise RuntimeError("AI model offline")
            return f"Processed: {text}"

        adapter = AICoreAdapter(ai_processor=fake_ai)
        r1 = adapter.process("Hello Astra")
        self.assertTrue(r1.success)
        self.assertEqual(r1.text, "Processed: Hello Astra")

        r2 = adapter.process("fail now")
        self.assertFalse(r2.success)
        self.assertEqual(r2.error, "AI model offline")

    def test_adapter_with_action_result_return(self):
        def fake_planner(text: str):
            return ActionResult.ok(
                message="Screenshot saved.",
                data={"path": "C:\\screen.png"},
            )

        adapter = AICoreAdapter(ai_processor=fake_planner)
        resp = adapter.process("take a screenshot")
        self.assertTrue(resp.success)
        self.assertEqual(resp.text, "Screenshot saved.")

    def test_adapter_invalid_response_format(self):
        def bad_core(text: str):
            return 12345  # Not string, dict, ActionResult, or AssistantResponse

        adapter = AICoreAdapter(ai_processor=bad_core)
        resp = adapter.process("test")
        self.assertFalse(resp.success)
        self.assertEqual(resp.error, "Invalid AI core response format")


if __name__ == "__main__":
    unittest.main()
