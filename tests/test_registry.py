"""Tests for Milestone 7: Action & Tool Registry (actions/registry.py).

Verifies discovery, parameter validation, confirmation enforcement, and
execution safety across all 34 Member 1 automation actions.
"""

import unittest
from unittest.mock import MagicMock, patch

from actions.base import ActionResult
from actions.registry import (
    CONFIRMATION_REQUIRED_ACTIONS,
    execute_action,
    get_action,
    get_action_metadata,
    list_actions,
    registry,
)

# Canonical list of 34 Member 1 actions
EXPECTED_ACTIONS = {
    # Applications (4)
    "find_application",
    "open_application",
    "close_application",
    "is_application_running",
    # Files & Folders (7)
    "open_file",
    "open_folder",
    "search_file",
    "create_folder",
    "rename_file",
    "move_file",
    "get_file_info",
    # System Information (8)
    "get_cpu_usage",
    "get_memory_usage",
    "get_disk_usage",
    "get_battery_status",
    "get_network_status",
    "get_os_info",
    "get_running_processes",
    "get_system_info",
    # Windows Controls (10)
    "volume_up",
    "volume_down",
    "mute",
    "unmute",
    "toggle_mute",
    "take_screenshot",
    "lock_pc",
    "sleep_pc",
    "restart_pc",
    "shutdown_pc",
    # Web (5)
    "open_website",
    "web_search",
    "google_search",
    "youtube_search",
    "github_search",
}


class TestActionRegistry(unittest.TestCase):
    """Unit test suite for Action Registry."""

    # 1. Registration completeness
    def test_all_expected_actions_registered(self):
        """All 34 Member 1 actions are registered."""
        registered_names = set(registry._tools.keys())
        self.assertEqual(len(registered_names), 34)
        self.assertEqual(registered_names, EXPECTED_ACTIONS)

    # 2. Scope boundary - no reminder actions
    def test_no_reminder_actions_registered(self):
        """No reminder actions (Member 3 scope) are present in registry."""
        registered_names = set(registry._tools.keys())
        for name in registered_names:
            self.assertNotIn("reminder", name.lower())
            self.assertNotIn("alarm", name.lower())

    # 3. Deterministic list_actions
    def test_list_actions_deterministic(self):
        """list_actions returns sorted, structured list of 34 action schemas."""
        actions_list = list_actions()
        self.assertEqual(len(actions_list), 34)
        # Verify sorted order
        names = [a["name"] for a in actions_list]
        self.assertEqual(names, sorted(names))
        # Verify schema structure
        for schema in actions_list:
            self.assertIn("name", schema)
            self.assertIn("description", schema)
            self.assertIn("category", schema)
            self.assertIn("parameters", schema)
            self.assertIn("requires_confirmation", schema)

    # 4. get_action returns metadata
    def test_get_action_and_metadata(self):
        """get_action and get_action_metadata return accurate definitions."""
        tool = get_action("open_application")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "open_application")
        self.assertEqual(tool.category, "application")
        self.assertFalse(tool.requires_confirmation)

        meta = get_action_metadata("open_application")
        self.assertIsInstance(meta, dict)
        self.assertEqual(meta["name"], "open_application")
        self.assertIn("name", meta["parameters"])

    # 5. Unknown action fails safely
    def test_unknown_action_fails_safely(self):
        """Executing an unregistered action returns structured failure."""
        res = execute_action("nonexistent_unknown_action_xyz")
        self.assertFalse(res.success)
        self.assertEqual(res.error, "ActionNotFound")
        self.assertIn("not registered", res.message)

    # 6. Missing required parameter fails
    def test_missing_required_parameter(self):
        """Executing an action without required parameters fails validation."""
        res = execute_action("open_application", {})
        self.assertFalse(res.success)
        self.assertEqual(res.error, "ValidationError")
        self.assertIn("Missing required parameter 'name'", res.message)

    # 7. Wrong parameter type fails
    def test_wrong_parameter_type(self):
        """Passing incorrect parameter type fails validation."""
        # 'name' expects str, passed int
        res = execute_action("open_application", {"name": 12345})
        self.assertFalse(res.success)
        self.assertEqual(res.error, "ValidationError")
        self.assertIn("expected string", res.message)

        # 'steps' expects int, passed str
        res_vol = execute_action("volume_up", {"steps": "two"})
        self.assertFalse(res_vol.success)
        self.assertEqual(res_vol.error, "ValidationError")
        self.assertIn("expected integer", res_vol.message)

        # 'steps' expects int, passed bool
        res_bool = execute_action("volume_up", {"steps": True})
        self.assertFalse(res_bool.success)
        self.assertEqual(res_bool.error, "ValidationError")

    # 8. Unexpected parameter fails
    def test_unexpected_parameter(self):
        """Passing undeclared extra parameters fails validation."""
        res = execute_action("get_os_info", {"extra_param": "forbidden"})
        self.assertFalse(res.success)
        self.assertEqual(res.error, "ValidationError")
        self.assertIn("Unexpected parameter 'extra_param'", res.message)

    # 9. open_application executes through registry
    def test_open_application_execution(self):
        """open_application executes cleanly through registry."""
        tool = registry.get_tool("open_application")
        self.assertIsNotNone(tool)
        mock_func = MagicMock(return_value=ActionResult.ok("Launched", data={"name": "notepad", "pid": 111}))
        with patch.object(tool, "function", mock_func):
            res = execute_action("open_application", {"name": "notepad"})
            self.assertTrue(res.success)
            self.assertEqual(res.data["pid"], 111)
            mock_func.assert_called_once_with(name="notepad")

    # 10. open_website executes through registry
    def test_open_website_execution(self):
        """open_website executes cleanly through registry."""
        tool = registry.get_tool("open_website")
        self.assertIsNotNone(tool)
        mock_func = MagicMock(return_value=ActionResult.ok("Opened", data={"url": "https://github.com"}))
        with patch.object(tool, "function", mock_func):
            res = execute_action("open_website", {"url": "https://github.com"})
            self.assertTrue(res.success)
            self.assertEqual(res.data["url"], "https://github.com")
            mock_func.assert_called_once_with(url="https://github.com")

    # 11. shutdown_pc unconfirmed does NOT execute
    def test_shutdown_pc_unconfirmed_fails(self):
        """shutdown_pc without confirmation fails with ConfirmationRequired."""
        res = execute_action("shutdown_pc", {"confirmed": False})
        self.assertFalse(res.success)
        self.assertEqual(res.error, "ConfirmationRequired")

        # Also when confirmed parameter is omitted (defaults to False)
        res_default = execute_action("shutdown_pc", {})
        self.assertFalse(res_default.success)
        self.assertEqual(res_default.error, "ConfirmationRequired")

    # 12. shutdown_pc confirmed passes through to action
    @patch("actions.system_actions.subprocess.run")
    def test_shutdown_pc_confirmed_executes(self, mock_subproc):
        """shutdown_pc with confirmed=True passes through to action."""
        res = execute_action("shutdown_pc", {"confirmed": True})
        self.assertTrue(res.success)
        self.assertTrue(res.data["confirmed"])
        mock_subproc.assert_called_once_with(["shutdown", "/s", "/t", "0"], check=True)

    # 13. requires_confirmation metadata mapping
    def test_confirmation_flags_metadata(self):
        """Only sleep_pc, restart_pc, and shutdown_pc require confirmation."""
        for name in EXPECTED_ACTIONS:
            meta = get_action_metadata(name)
            self.assertIsNotNone(meta)
            if name in CONFIRMATION_REQUIRED_ACTIONS:
                self.assertTrue(
                    meta["requires_confirmation"],
                    f"Action '{name}' should require confirmation",
                )
            else:
                self.assertFalse(
                    meta["requires_confirmation"],
                    f"Action '{name}' should NOT require confirmation",
                )

    # 14. Arbitrary function execution blocked
    def test_arbitrary_function_execution_blocked(self):
        """Arbitrary strings or builtins cannot be invoked."""
        for forbidden in ["eval", "exec", "os.system", "__import__", "open"]:
            res = execute_action(forbidden, {})
            self.assertFalse(res.success)
            self.assertEqual(res.error, "ActionNotFound")


if __name__ == "__main__":
    unittest.main()
