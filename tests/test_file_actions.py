"""Tests for Milestone 3: File & Folder Manager (actions/file_actions.py).

All filesystem operations are performed inside isolated tempfile.TemporaryDirectory
sandboxes. Windows-specific shell openers (os.startfile) are strictly mocked.
"""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from actions.file_actions import (
    create_folder,
    get_file_info,
    move_file,
    open_file,
    open_folder,
    rename_file,
    search_file,
)


class TestFileActions(unittest.TestCase):
    """Unit test suite for File and Folder Manager."""

    def setUp(self):
        """Create a temporary sandbox directory for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.sandbox = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up the sandbox directory."""
        self.temp_dir.cleanup()

    # ---------------------------------------------------------
    # open_file tests
    # ---------------------------------------------------------
    @patch("actions.file_actions.os.startfile")
    def test_open_file_success(self, mock_startfile):
        """Existing file calls os.startfile and returns success."""
        test_file = self.sandbox / "sample.txt"
        test_file.write_text("Hello Astra", encoding="utf-8")

        res = open_file(str(test_file))
        self.assertTrue(res.success)
        self.assertEqual(res.data["name"], "sample.txt")
        mock_startfile.assert_called_once_with(str(test_file.resolve()))

    def test_open_file_not_found(self):
        """Opening a non-existent file returns FileNotFoundError."""
        res = open_file(str(self.sandbox / "ghost_file.txt"))
        self.assertFalse(res.success)
        self.assertEqual(res.error, "FileNotFoundError")

    def test_open_file_directory_rejected(self):
        """Passing a folder path to open_file returns IsADirectoryError."""
        res = open_file(str(self.sandbox))
        self.assertFalse(res.success)
        self.assertEqual(res.error, "IsADirectoryError")

    def test_open_file_invalid_input(self):
        """Empty or invalid inputs fail gracefully."""
        res = open_file("   ")
        self.assertFalse(res.success)
        self.assertEqual(res.error, "InvalidInput")

    # ---------------------------------------------------------
    # open_folder tests
    # ---------------------------------------------------------
    @patch("actions.file_actions.os.startfile")
    def test_open_folder_success(self, mock_startfile):
        """Existing directory calls os.startfile and returns success."""
        sub_folder = self.sandbox / "docs"
        sub_folder.mkdir()

        res = open_folder(str(sub_folder))
        self.assertTrue(res.success)
        self.assertEqual(res.data["name"], "docs")
        mock_startfile.assert_called_once_with(str(sub_folder.resolve()))

    def test_open_folder_not_found(self):
        """Opening a non-existent folder returns FileNotFoundError."""
        res = open_folder(str(self.sandbox / "missing_dir"))
        self.assertFalse(res.success)
        self.assertEqual(res.error, "FileNotFoundError")

    def test_open_folder_file_rejected(self):
        """Passing a file path to open_folder returns NotADirectoryError."""
        test_file = self.sandbox / "sample.txt"
        test_file.write_text("Hello Astra", encoding="utf-8")

        res = open_folder(str(test_file))
        self.assertFalse(res.success)
        self.assertEqual(res.error, "NotADirectoryError")

    # ---------------------------------------------------------
    # create_folder tests
    # ---------------------------------------------------------
    def test_create_folder_new(self):
        """Creating a new folder succeeds with created=True."""
        target = self.sandbox / "new_project" / "src"
        res = create_folder(str(target))
        self.assertTrue(res.success)
        self.assertTrue(res.data["created"])
        self.assertTrue(target.is_dir())

    def test_create_folder_already_exists(self):
        """Creating an already existing folder succeeds with created=False."""
        existing = self.sandbox / "existing_dir"
        existing.mkdir()

        res = create_folder(str(existing))
        self.assertTrue(res.success)
        self.assertFalse(res.data["created"])

    def test_create_folder_file_conflict(self):
        """Attempting to create folder where a file exists fails."""
        conflict_file = self.sandbox / "conflict.txt"
        conflict_file.write_text("content", encoding="utf-8")

        res = create_folder(str(conflict_file))
        self.assertFalse(res.success)
        self.assertEqual(res.error, "FileExistsError")

    # ---------------------------------------------------------
    # rename_file tests
    # ---------------------------------------------------------
    def test_rename_file_success(self):
        """Renaming a file safely updates name and path."""
        src = self.sandbox / "old_name.txt"
        dst = self.sandbox / "new_name.txt"
        src.write_text("Rename me", encoding="utf-8")

        res = rename_file(str(src), str(dst))
        self.assertTrue(res.success)
        self.assertEqual(res.data["name"], "new_name.txt")
        self.assertFalse(src.exists())
        self.assertTrue(dst.exists())

    def test_rename_file_source_missing(self):
        """Renaming non-existent source fails with FileNotFoundError."""
        res = rename_file(str(self.sandbox / "ghost.txt"), str(self.sandbox / "dest.txt"))
        self.assertFalse(res.success)
        self.assertEqual(res.error, "FileNotFoundError")

    def test_rename_file_overwrite_protection(self):
        """Renaming fails if destination already exists to avoid overwrite."""
        src = self.sandbox / "file1.txt"
        dst = self.sandbox / "file2.txt"
        src.write_text("One", encoding="utf-8")
        dst.write_text("Two", encoding="utf-8")

        res = rename_file(str(src), str(dst))
        self.assertFalse(res.success)
        self.assertEqual(res.error, "FileExistsError")
        self.assertEqual(src.read_text(encoding="utf-8"), "One")
        self.assertEqual(dst.read_text(encoding="utf-8"), "Two")

    # ---------------------------------------------------------
    # move_file tests
    # ---------------------------------------------------------
    def test_move_file_into_folder(self):
        """Moving file into an existing folder succeeds."""
        src = self.sandbox / "move_me.txt"
        src.write_text("Move data", encoding="utf-8")
        target_dir = self.sandbox / "target_folder"
        target_dir.mkdir()

        res = move_file(str(src), str(target_dir))
        self.assertTrue(res.success)
        self.assertFalse(src.exists())
        self.assertTrue((target_dir / "move_me.txt").exists())

    def test_move_file_overwrite_protection(self):
        """Moving file aborts if target filename already exists in destination."""
        src = self.sandbox / "data.txt"
        src.write_text("Source data", encoding="utf-8")
        target_dir = self.sandbox / "archive"
        target_dir.mkdir()
        (target_dir / "data.txt").write_text("Existing data", encoding="utf-8")

        res = move_file(str(src), str(target_dir))
        self.assertFalse(res.success)
        self.assertEqual(res.error, "FileExistsError")
        self.assertTrue(src.exists())
        self.assertEqual((target_dir / "data.txt").read_text(encoding="utf-8"), "Existing data")

    def test_move_directory_into_self_rejected(self):
        """Moving a directory into itself or subdirectory is rejected."""
        parent_dir = self.sandbox / "parent"
        parent_dir.mkdir()
        child_dir = parent_dir / "child"
        child_dir.mkdir()

        res = move_file(str(parent_dir), str(child_dir))
        self.assertFalse(res.success)
        self.assertEqual(res.error, "InvalidMoveError")

    # ---------------------------------------------------------
    # get_file_info tests
    # ---------------------------------------------------------
    def test_get_file_info_file(self):
        """Retrieving file metadata returns complete structured data."""
        test_file = self.sandbox / "info_test.py"
        test_file.write_text("print('hello')", encoding="utf-8")

        res = get_file_info(str(test_file))
        self.assertTrue(res.success)
        data = res.data
        self.assertEqual(data["name"], "info_test.py")
        self.assertEqual(data["extension"], ".py")
        self.assertTrue(data["is_file"])
        self.assertFalse(data["is_dir"])
        self.assertGreater(data["size"], 0)
        self.assertIn("created_time", data)
        self.assertIn("modified_time", data)

    def test_get_file_info_directory(self):
        """Retrieving folder metadata returns directory indicators."""
        sub_folder = self.sandbox / "test_folder"
        sub_folder.mkdir()

        res = get_file_info(str(sub_folder))
        self.assertTrue(res.success)
        data = res.data
        self.assertEqual(data["name"], "test_folder")
        self.assertFalse(data["is_file"])
        self.assertTrue(data["is_dir"])
        self.assertIsNone(data["size"])

    def test_get_file_info_missing(self):
        """Querying missing path fails with FileNotFoundError."""
        res = get_file_info(str(self.sandbox / "not_there.txt"))
        self.assertFalse(res.success)
        self.assertEqual(res.error, "FileNotFoundError")

    # ---------------------------------------------------------
    # search_file tests
    # ---------------------------------------------------------
    def test_search_file_matches(self):
        """search_file finds matching files within the bounded directory."""
        (self.sandbox / "notes.txt").write_text("1", encoding="utf-8")
        (self.sandbox / "budget.csv").write_text("2", encoding="utf-8")
        sub = self.sandbox / "sub"
        sub.mkdir()
        (sub / "report.txt").write_text("3", encoding="utf-8")

        res = search_file("*.txt", location=str(self.sandbox))
        self.assertTrue(res.success)
        self.assertEqual(res.data["count"], 2)
        names = [f["name"] for f in res.data["files"]]
        self.assertIn("notes.txt", names)
        self.assertIn("report.txt", names)

    def test_search_file_no_matches(self):
        """search_file succeeds with count=0 when no files match."""
        res = search_file("nonexistent_pattern_*.log", location=str(self.sandbox))
        self.assertTrue(res.success)
        self.assertEqual(res.data["count"], 0)
        self.assertEqual(res.data["files"], [])

    def test_search_file_invalid_location(self):
        """Searching in a missing directory fails with FileNotFoundError."""
        res = search_file("*.txt", location=str(self.sandbox / "missing_folder"))
        self.assertFalse(res.success)
        self.assertEqual(res.error, "FileNotFoundError")


if __name__ == "__main__":
    unittest.main()
