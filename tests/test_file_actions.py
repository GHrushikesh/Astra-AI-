"""Tests for Milestone 3: File & Folder Manager (actions/file_actions.py).

All filesystem operations are performed inside isolated tempfile.TemporaryDirectory
sandboxes. Windows-specific shell openers (os.startfile) are strictly mocked.
"""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from actions.file_actions import (
    _resolve_safe_path,
    create_folder,
    delete_file,
    delete_folder,
    find_file_path,
    find_folder_path,
    get_file_info,
    list_folder,
    move_file,
    open_file,
    open_folder,
    read_file,
    rename_file,
    run_file,
    search_file,
    smart_create_folder,
    write_file,
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

    # ---------------------------------------------------------
    # Subfolder creation, drive expressions, and quoted paths
    # ---------------------------------------------------------
    def test_create_nested_subfolders(self):
        """Creating multi-level deep subfolders succeeds."""
        nested = self.sandbox / "parent" / "child" / "grandchild"
        res = create_folder(str(nested))
        self.assertTrue(res.success)
        self.assertTrue(nested.is_dir())
        self.assertTrue(res.data["created"])

    def test_create_folder_with_double_quotes(self):
        """Path enclosed in double quotes is handled safely."""
        target = self.sandbox / "quoted_folder" / "sub"
        quoted = f'"{target}"'
        res = create_folder(quoted)
        self.assertTrue(res.success)
        self.assertTrue(target.is_dir())

    def test_create_folder_with_single_quotes(self):
        """Path enclosed in single quotes is handled safely."""
        target = self.sandbox / "single_quoted" / "sub"
        quoted = f"'{target}'"
        res = create_folder(quoted)
        self.assertTrue(res.success)
        self.assertTrue(target.is_dir())

    def test_create_folder_with_forward_slashes(self):
        """Path using forward slashes works properly."""
        target = self.sandbox / "slash_dir" / "sub_dir"
        forward_path = str(target).replace("\\", "/")
        res = create_folder(forward_path)
        self.assertTrue(res.success)
        self.assertTrue(target.is_dir())

    def test_resolve_safe_path_quotes_and_natural_language(self):
        """_resolve_safe_path normalizes quotes, slashes, and natural phrases."""
        # Surrounding quotes
        p1 = _resolve_safe_path(f'"{self.sandbox}"')
        self.assertEqual(p1, self.sandbox.resolve())

        # Natural drive prefix
        p2 = _resolve_safe_path("under e drive under some folder")
        self.assertIsNotNone(p2)
        self.assertIn("some folder", str(p2))

    # ---------------------------------------------------------
    # list_folder tests
    # ---------------------------------------------------------
    def test_list_folder_success(self):
        """list_folder returns subfolders and files with metadata."""
        sub = self.sandbox / "sub_dir"
        sub.mkdir()
        f1 = self.sandbox / "file1.txt"
        f1.write_text("hello", encoding="utf-8")
        f2 = self.sandbox / "file2.py"
        f2.write_text("print()", encoding="utf-8")

        res = list_folder(str(self.sandbox))
        self.assertTrue(res.success)
        self.assertEqual(res.data["folder_count"], 1)
        self.assertEqual(res.data["file_count"], 2)
        self.assertEqual(res.data["folders"][0]["name"], "sub_dir")
        file_names = [f["name"] for f in res.data["files"]]
        self.assertIn("file1.txt", file_names)
        self.assertIn("file2.py", file_names)

    def test_list_folder_not_found(self):
        """list_folder on missing directory returns FileNotFoundError."""
        res = list_folder(str(self.sandbox / "does_not_exist"))
        self.assertFalse(res.success)
        self.assertEqual(res.error, "FileNotFoundError")

    def test_list_folder_on_file_rejected(self):
        """list_folder on a regular file returns NotADirectoryError."""
        f = self.sandbox / "a.txt"
        f.write_text("test", encoding="utf-8")
        res = list_folder(str(f))
        self.assertFalse(res.success)
        self.assertEqual(res.error, "NotADirectoryError")

    # ---------------------------------------------------------
    # write_file and read_file tests
    # ---------------------------------------------------------
    def test_write_and_read_file_in_subfolder(self):
        """write_file creates parent folders and writes content; read_file reads it."""
        sub_file = self.sandbox / "nested" / "deep" / "test.txt"
        res_write = write_file(str(sub_file), "Initial content", mode="write")
        self.assertTrue(res_write.success)
        self.assertTrue(sub_file.exists())

        res_read = read_file(str(sub_file))
        self.assertTrue(res_read.success)
        self.assertEqual(res_read.data["content"], "Initial content")

    def test_write_file_append_and_overwrite(self):
        """write_file supports append and overwrite modes."""
        sub_file = self.sandbox / "doc.txt"
        write_file(str(sub_file), "Part1", mode="write")

        # Append
        res_app = write_file(str(sub_file), " Part2", mode="append")
        self.assertTrue(res_app.success)
        self.assertEqual(sub_file.read_text(encoding="utf-8"), "Part1 Part2")

        # Overwrite
        res_over = write_file(str(sub_file), "Fresh", mode="overwrite")
        self.assertTrue(res_over.success)
        self.assertEqual(sub_file.read_text(encoding="utf-8"), "Fresh")

    def test_write_file_existing_write_mode_conflict(self):
        """write_file with mode='write' aborts if file exists."""
        sub_file = self.sandbox / "existing.txt"
        sub_file.write_text("orig", encoding="utf-8")
        res = write_file(str(sub_file), "new", mode="write")
        self.assertFalse(res.success)
        self.assertEqual(res.error, "FileExistsError")

    # ---------------------------------------------------------
    # delete_file and delete_folder tests
    # ---------------------------------------------------------
    def test_delete_file_success(self):
        """delete_file deletes regular files."""
        f = self.sandbox / "delete_me.txt"
        f.write_text("bye", encoding="utf-8")
        res = delete_file(str(f))
        self.assertTrue(res.success)
        self.assertFalse(f.exists())

    def test_delete_folder_recursive(self):
        """delete_folder removes directory and all nested contents."""
        sub = self.sandbox / "to_delete" / "sub"
        sub.mkdir(parents=True)
        (sub / "nested.txt").write_text("data", encoding="utf-8")

        res = delete_folder(str(self.sandbox / "to_delete"), recursive=True)
        self.assertTrue(res.success)
        self.assertFalse((self.sandbox / "to_delete").exists())

    # ---------------------------------------------------------
    # Pathless search and execution tests
    # ---------------------------------------------------------
    def test_find_folder_path_nested(self):
        """find_folder_path locates a folder by name inside nested subfolders."""
        deep_folder = self.sandbox / "projects" / "ai" / "astra_core"
        deep_folder.mkdir(parents=True)

        found = find_folder_path("astra_core", root_location=str(self.sandbox))
        self.assertEqual(found, deep_folder.resolve())

    def test_find_file_path_nested(self):
        """find_file_path locates a file anywhere within subfolders."""
        deep_file = self.sandbox / "src" / "modules" / "helper.py"
        deep_file.parent.mkdir(parents=True)
        deep_file.write_text("print('hello')", encoding="utf-8")

        found = find_file_path("helper.py", root_location=str(self.sandbox))
        self.assertEqual(found, deep_file.resolve())

    def test_smart_create_folder_under_nested_parent(self):
        """smart_create_folder locates parent without full path and creates new folder."""
        parent = self.sandbox / "deep" / "nested" / "target_parent"
        parent.mkdir(parents=True)

        res = smart_create_folder(
            parent_folder="target_parent",
            new_folder_name="auto_created",
            drive=str(self.sandbox),
        )
        self.assertTrue(res.success)
        self.assertTrue((parent / "auto_created").is_dir())

    @patch("actions.file_actions.subprocess.Popen")
    def test_run_file_python(self, mock_popen):
        """run_file locates Python file in subfolder and spawns Python process."""
        script = self.sandbox / "scripts" / "run_me.py"
        script.parent.mkdir(parents=True)
        script.write_text("print(1)", encoding="utf-8")

        mock_proc = mock_popen.return_value
        mock_proc.pid = 9999

        res = run_file("run_me.py", location=str(self.sandbox))
        self.assertTrue(res.success)
        self.assertIn("Launched Python file", res.message)
        mock_popen.assert_called_once()

    @patch("actions.file_actions.os.startfile")
    def test_run_file_document(self, mock_startfile):
        """run_file opens document file via os.startfile."""
        doc = self.sandbox / "docs" / "manual.pdf"
        doc.parent.mkdir(parents=True)
        doc.write_text("%PDF-1.4", encoding="utf-8")

        res = run_file("manual.pdf", location=str(self.sandbox))
        self.assertTrue(res.success)
        self.assertIn("Opened file", res.message)
        mock_startfile.assert_called_once_with(str(doc.resolve()))


if __name__ == "__main__":
    unittest.main()
