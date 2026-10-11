"""Tests for Milestone 1: Action layer foundation, ActionResult, and package structure."""

import unittest
from actions.base import ActionResult, ActionConfirmationRequired, ActionError, get_logger
import actions.app_actions
import actions.file_actions
import actions.system_actions
import actions.web_actions
import actions.registry


class TestActionFoundation(unittest.TestCase):
    """Test suite for base action result envelope and exception hierarchy."""

    def test_action_result_ok(self):
        """Test ActionResult.ok constructor and attributes."""
        res = ActionResult.ok(message="Operation successful", data={"status": "ready"})
        self.assertTrue(res.success)
        self.assertEqual(res.message, "Operation successful")
        self.assertEqual(res.data, {"status": "ready"})
        self.assertIsNone(res.error)

    def test_action_result_fail(self):
        """Test ActionResult.fail constructor and attributes."""
        res = ActionResult.fail(message="Operation failed", error="FileNotFoundError")
        self.assertFalse(res.success)
        self.assertEqual(res.message, "Operation failed")
        self.assertEqual(res.error, "FileNotFoundError")
        self.assertIsNone(res.data)

    def test_action_result_dict_access(self):
        """Test that ActionResult supports both dict access and to_dict()."""
        res = ActionResult.ok(message="Done", data=42)
        # Attribute access
        self.assertEqual(res.message, "Done")
        # Dict item access
        self.assertEqual(res["message"], "Done")
        self.assertEqual(res["success"], True)
        self.assertEqual(res["data"], 42)
        self.assertIsNone(res["error"])
        # Conversion to dict
        d = res.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["message"], "Done")
        self.assertEqual(d["success"], True)

    def test_confirmation_exception(self):
        """Test ActionConfirmationRequired exception formatting."""
        exc = ActionConfirmationRequired("shutdown_pc")
        self.assertIn("shutdown_pc", str(exc))
        self.assertIn("confirmed=True", str(exc))
        self.assertIsInstance(exc, ActionError)

    def test_logger_initialization(self):
        """Test get_logger returns a properly configured logger."""
        log = get_logger("test.logger")
        self.assertEqual(log.name, "test.logger")
        self.assertTrue(len(log.handlers) > 0)

    def test_modules_importable(self):
        """Verify all planned action modules are cleanly importable."""
        self.assertTrue(hasattr(actions.app_actions, "open_application"))
        self.assertTrue(hasattr(actions.file_actions, "open_file"))
        self.assertTrue(hasattr(actions.system_actions, "get_system_info"))
        self.assertTrue(hasattr(actions.web_actions, "web_search"))
        self.assertTrue(hasattr(actions.registry, "registry"))

    def test_registry_unregistered_tool(self):
        """Verify registry reports unregistered tools safely."""
        res = actions.registry.registry.execute("unregistered_tool")
        self.assertFalse(res.success)
        self.assertIn("not registered", res.message)


if __name__ == "__main__":
    unittest.main()
