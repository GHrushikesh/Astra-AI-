"""Tests for Milestone 2: Application Manager (actions/app_actions.py).

All tests are safe and deterministic. Process launching and termination are
mocked or strictly isolated so real applications are never disrupted.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch
import psutil

from actions.app_actions import (
    PROTECTED_PROCESSES,
    close_application,
    find_application,
    is_application_running,
    open_application,
)
from actions.base import ActionResult


class TestAppActions(unittest.TestCase):
    """Unit tests for Application Manager."""

    # ---------------------------------------------------------
    # find_application tests
    # ---------------------------------------------------------
    def test_find_application_direct_valid_path(self):
        """Locating an existing absolute path succeeds."""
        res = find_application(sys.executable)
        self.assertTrue(res.success)
        self.assertIn("path", res.data)
        self.assertEqual(res.data["path"].lower(), sys.executable.lower())

    def test_find_application_built_in_tool(self):
        """Locating standard Windows tool (cmd / notepad) succeeds."""
        res = find_application("cmd")
        self.assertTrue(res.success)
        self.assertTrue(res.data["path"].lower().endswith("cmd.exe"))

    def test_find_application_alias(self):
        """Locating standard alias (calculator / calc) succeeds."""
        res = find_application("calc")
        self.assertTrue(res.success)
        self.assertTrue(res.data["path"].lower().endswith("calc.exe"))

    def test_find_application_not_found(self):
        """Locating a non-existent application returns failure."""
        res = find_application("astra_completely_nonexistent_tool_12345")
        self.assertFalse(res.success)
        self.assertEqual(res.error, "ApplicationNotFound")

    def test_find_application_invalid_names(self):
        """Empty, whitespace, or invalid types fail gracefully."""
        for invalid in ["", "   ", None, 123]:  # type: ignore
            res = find_application(invalid)  # type: ignore
            self.assertFalse(res.success)
            self.assertEqual(res.error, "InvalidInput")

    # ---------------------------------------------------------
    # open_application tests (MOCKED - No real processes launched)
    # ---------------------------------------------------------
    @patch("actions.app_actions.subprocess.Popen")
    @patch("actions.app_actions.find_application")
    def test_open_application_success(self, mock_find, mock_popen):
        """open_application launches process detached and returns PID."""
        mock_find.return_value = ActionResult.ok(
            message="Found",
            data={"name": "testapp", "path": r"C:\fake\testapp.exe", "executable": "testapp.exe"},
        )
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_popen.return_value = mock_proc

        res = open_application("testapp")
        self.assertTrue(res.success)
        self.assertEqual(res.data["pid"], 9999)
        self.assertEqual(res.data["path"], r"C:\fake\testapp.exe")
        mock_popen.assert_called_once()

    @patch("actions.app_actions.find_application")
    def test_open_application_not_found(self, mock_find):
        """open_application propagates not-found error if app does not exist."""
        mock_find.return_value = ActionResult.fail(
            message="Application 'ghost' could not be found.",
            error="ApplicationNotFound",
        )
        res = open_application("ghost")
        self.assertFalse(res.success)
        self.assertEqual(res.error, "ApplicationNotFound")

    @patch("actions.app_actions.subprocess.Popen")
    @patch("actions.app_actions.find_application")
    def test_open_application_permission_error(self, mock_find, mock_popen):
        """open_application handles PermissionError without crashing."""
        mock_find.return_value = ActionResult.ok(
            message="Found",
            data={"name": "protected", "path": r"C:\fake\protected.exe", "executable": "protected.exe"},
        )
        mock_popen.side_effect = PermissionError("Access is denied")

        res = open_application("protected")
        self.assertFalse(res.success)
        self.assertEqual(res.error, "PermissionDenied")

    # ---------------------------------------------------------
    # is_application_running tests
    # ---------------------------------------------------------
    def test_is_application_running_nonexistent(self):
        """Checking a non-running app returns running=False successfully."""
        res = is_application_running("astra_ghost_process_9999")
        self.assertTrue(res.success)
        self.assertFalse(res.data["running"])
        self.assertEqual(res.data["count"], 0)

    @patch("actions.app_actions.psutil.process_iter")
    def test_is_application_running_detected(self, mock_iter):
        """is_application_running correctly identifies running instances."""
        mock_p1 = MagicMock()
        mock_p1.info = {"pid": 101, "name": "notepad.exe"}
        mock_p2 = MagicMock()
        mock_p2.info = {"pid": 102, "name": "other.exe"}
        mock_iter.return_value = [mock_p1, mock_p2]

        res = is_application_running("notepad")
        self.assertTrue(res.success)
        self.assertTrue(res.data["running"])
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["instances"][0]["pid"], 101)

    def test_is_application_running_invalid_name(self):
        """is_application_running handles empty/invalid input safely."""
        res = is_application_running("   ")
        self.assertFalse(res.success)
        self.assertEqual(res.error, "InvalidInput")

    # ---------------------------------------------------------
    # close_application tests (MOCKED - No real processes terminated)
    # ---------------------------------------------------------
    def test_close_application_protected_processes(self):
        """Protected OS and Astra processes are rejected immediately."""
        for protected in ["explorer", "python", "svchost.exe", "csrss.exe"]:
            res = close_application(protected)
            self.assertFalse(res.success)
            self.assertEqual(res.error, "ProtectedProcessError")

    @patch("actions.app_actions.psutil.process_iter")
    def test_close_application_not_running(self, mock_iter):
        """Attempting to close an app that is not running fails cleanly."""
        mock_iter.return_value = []
        res = close_application("nonexistent_app")
        self.assertFalse(res.success)
        self.assertEqual(res.error, "ProcessNotFound")

    @patch("actions.app_actions.psutil.wait_procs")
    @patch("actions.app_actions.psutil.process_iter")
    def test_close_application_success(self, mock_iter, mock_wait):
        """close_application gracefully terminates matching processes."""
        mock_proc = MagicMock()
        mock_proc.pid = 4321
        mock_proc.info = {"pid": 4321, "name": "dummyapp.exe"}
        mock_proc.is_running.return_value = False

        mock_iter.return_value = [mock_proc]
        mock_wait.return_value = ([mock_proc], [])  # gone, alive

        res = close_application("dummyapp")
        self.assertTrue(res.success)
        self.assertEqual(res.data["terminated_pids"], [4321])
        mock_proc.terminate.assert_called_once()

    @patch("actions.app_actions.psutil.wait_procs")
    @patch("actions.app_actions.psutil.process_iter")
    def test_close_application_access_denied(self, mock_iter, mock_wait):
        """close_application handles permission issues gracefully."""
        mock_proc = MagicMock()
        mock_proc.pid = 5555
        mock_proc.info = {"pid": 5555, "name": "systemservice.exe"}
        mock_proc.terminate.side_effect = psutil.AccessDenied()
        mock_proc.kill.side_effect = psutil.AccessDenied()
        mock_proc.is_running.return_value = True

        mock_iter.return_value = [mock_proc]
        mock_wait.return_value = ([], [mock_proc])

        res = close_application("systemservice")
        self.assertFalse(res.success)
        self.assertEqual(res.error, "AccessDenied")


if __name__ == "__main__":
    unittest.main()
