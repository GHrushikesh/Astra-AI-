"""File and folder management actions for Astra.

Functions:
- open_file(path)
- open_folder(path)
- search_file(name, location=None)
- create_folder(path)
- rename_file(old_path, new_path)
- move_file(source, destination)
- get_file_info(path)

To be implemented in Milestone 3.
"""

from typing import Optional
from actions.base import ActionResult

__all__ = [
    "open_file",
    "open_folder",
    "search_file",
    "create_folder",
    "rename_file",
    "move_file",
    "get_file_info",
]


def open_file(path: str) -> ActionResult:
    """Open a file with its default Windows application."""
    raise NotImplementedError("Scheduled for Milestone 3")


def open_folder(path: str) -> ActionResult:
    """Open a folder in Windows File Explorer."""
    raise NotImplementedError("Scheduled for Milestone 3")


def search_file(name: str, location: Optional[str] = None) -> ActionResult:
    """Search for files matching name within location."""
    raise NotImplementedError("Scheduled for Milestone 3")


def create_folder(path: str) -> ActionResult:
    """Safely create a directory path."""
    raise NotImplementedError("Scheduled for Milestone 3")


def rename_file(old_path: str, new_path: str) -> ActionResult:
    """Rename a file or folder safely."""
    raise NotImplementedError("Scheduled for Milestone 3")


def move_file(source: str, destination: str) -> ActionResult:
    """Move a file to a new destination."""
    raise NotImplementedError("Scheduled for Milestone 3")


def get_file_info(path: str) -> ActionResult:
    """Retrieve metadata (size, created, modified) for a path."""
    raise NotImplementedError("Scheduled for Milestone 3")
