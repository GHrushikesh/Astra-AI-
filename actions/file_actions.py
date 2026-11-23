"""File and folder management actions for Astra.

Provides deterministic tools for file inspection, folder creation,
safe renaming, non-destructive moving, folder listing, content reading/writing,
and Windows shell file opening across any drive and nested subfolders.

Functions:
- open_file(path: str) -> ActionResult
- open_folder(path: str) -> ActionResult
- search_file(name: str, location: Optional[str] = None) -> ActionResult
- create_folder(path: str) -> ActionResult
- rename_file(old_path: str, new_path: str) -> ActionResult
- move_file(source: str, destination: str) -> ActionResult
- get_file_info(path: str) -> ActionResult
- list_folder(path: str, max_items: int = 100) -> ActionResult
- read_file(path: str, max_bytes: int = 50000) -> ActionResult
- write_file(path: str, content: str = "", mode: str = "write") -> ActionResult
- delete_file(path: str) -> ActionResult
- delete_folder(path: str, recursive: bool = False) -> ActionResult
"""

from __future__ import annotations

from datetime import datetime, timezone
import fnmatch
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Optional

from actions.base import ActionResult, get_logger

logger = get_logger("astra.actions.file")

# Directories skipped during broad searches to maintain performance and avoid permission issues
IGNORED_SEARCH_DIRS = {
    "$recycle.bin",
    "system volume information",
    "windows",
    "node_modules",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    ".idea",
    ".vscode",
    "appdata",
}


def _resolve_safe_path(raw_path: Any) -> Optional[Path]:
    """Validate, expand, and resolve a file/folder path.

    Handles:
    - Standard absolute and relative paths across any Windows drive (C:, E:, etc.)
    - Paths enclosed in single or double quotes
    - Forward slashes and backslashes
    - Natural language drive expressions (e.g., 'e drive/folder' or 'under e drive under folder')
    - Windows environment variables (%USERPROFILE%) and user home (~)
    """
    if not isinstance(raw_path, (str, Path)):
        return None
    raw_str = str(raw_path).strip()
    if not raw_str:
        return None
    try:
        # 1. Strip surrounding quotes (double or single)
        raw_str = raw_str.strip("\"'")
        if not raw_str:
            return None

        # 2. Strip leading conversational prepositions (e.g., "under ...", "in ...")
        for prefix in ("under ", "in ", "at "):
            if raw_str.lower().startswith(prefix):
                raw_str = raw_str[len(prefix):].strip()
                break

        # 3. Replace natural language "under" or "inside" between path segments with slash
        # e.g., "e drive under some folder under child" -> "e drive\some folder\child"
        raw_str = re.sub(r"(?i)\s+(?:under|inside)\s+", r"\\", raw_str)

        # 4. Handle natural drive expressions like "e drive", "E drive", "e:"
        raw_str = re.sub(
            r"(?i)^([a-zA-Z])\s+drive(?:\s*[:\\/]+|\b|$)",
            r"\1:\\",
            raw_str,
        )

        # 5. Fix "e:subfolder" without slash -> "e:\subfolder"
        if re.match(r"^[a-zA-Z]:[^\\]", raw_str) and not re.match(r"^[a-zA-Z]:/", raw_str):
            raw_str = raw_str[0:2] + "\\" + raw_str[2:]

        # 6. Expand environment variables and user home (~)
        expanded = os.path.expandvars(raw_str)
        path = Path(expanded).expanduser()
        return path.resolve()
    except Exception:
        return None


def open_file(path: str) -> ActionResult:
    """Open an existing file using its associated Windows application.

    Args:
        path: File path to open.

    Returns:
        ActionResult indicating success or error details.
    """
    resolved = _resolve_safe_path(path)
    if not resolved:
        return ActionResult.fail(
            message="Invalid or empty file path provided.",
            error="InvalidInput",
        )

    if not resolved.exists():
        return ActionResult.fail(
            message=f"File not found: '{resolved}'.",
            error="FileNotFoundError",
        )

    if resolved.is_dir():
        return ActionResult.fail(
            message=f"Path is a directory, not a file: '{resolved}'. Use open_folder() instead.",
            error="IsADirectoryError",
        )

    try:
        # os.startfile opens the file with Windows associated application without blocking
        os.startfile(str(resolved))
        logger.info("Opened file '%s'", resolved)
        return ActionResult.ok(
            message=f"Opened file '{resolved.name}'.",
            data={
                "name": resolved.name,
                "path": str(resolved),
            },
        )
    except PermissionError as exc:
        logger.error("Permission denied opening file '%s': %s", resolved, exc)
        return ActionResult.fail(
            message=f"Permission denied when opening file '{resolved.name}'.",
            error="PermissionDenied",
        )
    except OSError as exc:
        logger.error("OS error opening file '%s': %s", resolved, exc)
        return ActionResult.fail(
            message=f"Could not open file '{resolved.name}': {exc}",
            error=str(exc),
        )


def open_folder(path: str) -> ActionResult:
    """Open an existing folder in Windows File Explorer.

    Args:
        path: Directory path to open.

    Returns:
        ActionResult indicating success or error details.
    """
    resolved = _resolve_safe_path(path)
    if not resolved:
        return ActionResult.fail(
            message="Invalid or empty directory path provided.",
            error="InvalidInput",
        )

    if not resolved.exists():
        return ActionResult.fail(
            message=f"Folder not found: '{resolved}'.",
            error="FileNotFoundError",
        )

    if not resolved.is_dir():
        return ActionResult.fail(
            message=f"Path is a file, not a directory: '{resolved}'. Use open_file() instead.",
            error="NotADirectoryError",
        )

    try:
        os.startfile(str(resolved))
        logger.info("Opened directory '%s' in Explorer", resolved)
        return ActionResult.ok(
            message=f"Opened folder '{resolved.name}'.",
            data={
                "name": resolved.name,
                "path": str(resolved),
            },
        )
    except PermissionError as exc:
        logger.error("Permission denied opening folder '%s': %s", resolved, exc)
        return ActionResult.fail(
            message=f"Permission denied when opening folder '{resolved.name}'.",
            error="PermissionDenied",
        )
    except OSError as exc:
        logger.error("OS error opening folder '%s': %s", resolved, exc)
        return ActionResult.fail(
            message=f"Could not open folder '{resolved.name}': {exc}",
            error=str(exc),
        )


def search_file(
    name: str,
    location: Optional[str] = None,
    max_results: int = 50,
    max_depth: int = 5,
) -> ActionResult:
    """Search deterministically for files matching a name or pattern.

    To avoid system freezing, broad whole-disk scans are avoided by default.
    If no location is given, it defaults to the current working directory.

    Args:
        name: Filename or wildcard pattern (e.g. 'report.pdf' or '*.txt').
        location: Root directory to search within (defaults to current working directory).
        max_results: Maximum number of matched files to return (default: 50).
        max_depth: Maximum directory recursion depth (default: 5).

    Returns:
        ActionResult with matched files and metadata.
    """
    if not isinstance(name, str) or not name.strip():
        return ActionResult.fail(
            message="Search name/pattern must be a non-empty string.",
            error="InvalidInput",
        )

    search_pattern = name.strip()
    # Normalize pattern for wildcard matching if exact name was passed
    pattern_lower = search_pattern.lower()

    if location:
        root_dir = _resolve_safe_path(location)
        if not root_dir or not root_dir.exists():
            return ActionResult.fail(
                message=f"Search location does not exist: '{location}'.",
                error="FileNotFoundError",
            )
        if not root_dir.is_dir():
            return ActionResult.fail(
                message=f"Search location is not a directory: '{location}'.",
                error="NotADirectoryError",
            )
    else:
        root_dir = Path.cwd()

    matched_files: list[dict[str, Any]] = []
    root_str = str(root_dir)

    try:
        for current_root, dirs, files in os.walk(root_str):
            # Compute current depth relative to root
            rel_path = os.path.relpath(current_root, root_str)
            depth = 0 if rel_path == "." else len(Path(rel_path).parts)

            if depth >= max_depth:
                dirs.clear()
                continue

            # Skip ignored/system folders
            dirs[:] = [
                d
                for d in dirs
                if d.lower() not in IGNORED_SEARCH_DIRS
                and not d.startswith(".")
            ]

            for file in files:
                file_lower = file.lower()
                is_match = (
                    fnmatch.fnmatch(file_lower, pattern_lower)
                    or pattern_lower in file_lower
                )
                if is_match:
                    full_path = Path(current_root) / file
                    try:
                        stat = full_path.stat()
                        matched_files.append(
                            {
                                "name": file,
                                "path": str(full_path),
                                "size": stat.st_size,
                                "modified": datetime.fromtimestamp(
                                    stat.st_mtime, tz=timezone.utc
                                ).isoformat(),
                            }
                        )
                    except (OSError, PermissionError):
                        matched_files.append(
                            {
                                "name": file,
                                "path": str(full_path),
                                "size": None,
                                "modified": None,
                            }
                        )

                    if len(matched_files) >= max_results:
                        break

            if len(matched_files) >= max_results:
                break

    except PermissionError as exc:
        logger.warning("Permission denied scanning directory '%s': %s", root_dir, exc)
    except Exception as exc:
        logger.error("Error during search in '%s': %s", root_dir, exc)
        return ActionResult.fail(
            message=f"Error occurred while searching for '{search_pattern}': {exc}",
            error=str(exc),
        )

    return ActionResult.ok(
        message=f"Found {len(matched_files)} file(s) matching '{search_pattern}'.",
        data={
            "query": search_pattern,
            "location": str(root_dir),
            "count": len(matched_files),
            "files": matched_files,
        },
    )


def create_folder(path: str) -> ActionResult:
    """Safely create a folder, including parent directories if needed.

    Args:
        path: Path of the folder to create.

    Returns:
        ActionResult indicating whether folder was created or already existed.
    """
    resolved = _resolve_safe_path(path)
    if not resolved:
        return ActionResult.fail(
            message="Invalid or empty directory path provided.",
            error="InvalidInput",
        )

    if resolved.exists():
        if resolved.is_dir():
            return ActionResult.ok(
                message=f"Folder already exists: '{resolved}'.",
                data={
                    "path": str(resolved),
                    "created": False,
                },
            )
        return ActionResult.fail(
            message=f"Cannot create folder; a file already exists at '{resolved}'.",
            error="FileExistsError",
        )

    try:
        resolved.mkdir(parents=True, exist_ok=True)
        logger.info("Created folder '%s'", resolved)
        return ActionResult.ok(
            message=f"Folder created successfully: '{resolved}'.",
            data={
                "path": str(resolved),
                "created": True,
            },
        )
    except PermissionError as exc:
        logger.error("Permission denied creating folder '%s': %s", resolved, exc)
        return ActionResult.fail(
            message=f"Permission denied creating folder '{resolved}'.",
            error="PermissionDenied",
        )
    except OSError as exc:
        logger.error("OS error creating folder '%s': %s", resolved, exc)
        return ActionResult.fail(
            message=f"Could not create folder '{resolved}': {exc}",
            error=str(exc),
        )


def rename_file(old_path: str, new_path: str) -> ActionResult:
    """Safely rename a file or folder, strictly preventing accidental overwrites.

    Args:
        old_path: Current path of the file or folder.
        new_path: New name or destination path.

    Returns:
        ActionResult indicating the renamed status.
    """
    src = _resolve_safe_path(old_path)
    if not src or not src.exists():
        return ActionResult.fail(
            message=f"Source file or folder not found: '{old_path}'.",
            error="FileNotFoundError",
        )

    dst = _resolve_safe_path(new_path)
    if not dst:
        return ActionResult.fail(
            message="Invalid destination path provided.",
            error="InvalidInput",
        )

    # Prevent accidental overwrites
    if dst.exists():
        return ActionResult.fail(
            message=f"Destination '{dst}' already exists. Rename aborted to prevent overwrite.",
            error="FileExistsError",
        )

    # Validate parent directory exists
    if not dst.parent.exists():
        return ActionResult.fail(
            message=f"Destination parent directory does not exist: '{dst.parent}'.",
            error="FileNotFoundError",
        )

    try:
        src.rename(dst)
        logger.info("Renamed '%s' -> '%s'", src, dst)
        return ActionResult.ok(
            message=f"Successfully renamed '{src.name}' to '{dst.name}'.",
            data={
                "old_path": str(src),
                "new_path": str(dst),
                "name": dst.name,
            },
        )
    except PermissionError as exc:
        logger.error("Permission denied renaming '%s' to '%s': %s", src, dst, exc)
        return ActionResult.fail(
            message=f"Permission denied renaming '{src.name}'.",
            error="PermissionDenied",
        )
    except OSError as exc:
        logger.error("OS error renaming '%s' to '%s': %s", src, dst, exc)
        return ActionResult.fail(
            message=f"Could not rename '{src.name}': {exc}",
            error=str(exc),
        )


def move_file(source: str, destination: str) -> ActionResult:
    """Safely move a file or folder without overwriting existing files.

    If destination is an existing folder, the file is placed inside it.
    If a file of the same name already exists in the destination,
    the move is safely aborted to avoid data loss.

    Args:
        source: Path of the file or folder to move.
        destination: Target folder or new file path.

    Returns:
        ActionResult indicating move status and target path.
    """
    src = _resolve_safe_path(source)
    if not src or not src.exists():
        return ActionResult.fail(
            message=f"Source path not found: '{source}'.",
            error="FileNotFoundError",
        )

    dst = _resolve_safe_path(destination)
    if not dst:
        return ActionResult.fail(
            message="Invalid destination path provided.",
            error="InvalidInput",
        )

    # Prevent moving a folder into itself
    if src.is_dir() and (dst == src or src in dst.parents):
        return ActionResult.fail(
            message="Cannot move a directory into itself or a subdirectory of itself.",
            error="InvalidMoveError",
        )

    # Determine final target path
    if dst.exists() and dst.is_dir():
        final_target = dst / src.name
    else:
        final_target = dst

    # Overwrite guard: abort if final target already exists
    if final_target.exists():
        return ActionResult.fail(
            message=f"Target path already exists: '{final_target}'. Move aborted to prevent overwrite.",
            error="FileExistsError",
        )

    # Ensure target parent folder exists
    if not final_target.parent.exists():
        return ActionResult.fail(
            message=f"Destination parent directory does not exist: '{final_target.parent}'.",
            error="FileNotFoundError",
        )

    try:
        shutil.move(str(src), str(final_target))
        logger.info("Moved '%s' -> '%s'", src, final_target)
        return ActionResult.ok(
            message=f"Successfully moved '{src.name}' to '{final_target}'.",
            data={
                "source": str(src),
                "destination": str(final_target),
            },
        )
    except PermissionError as exc:
        logger.error("Permission denied moving '%s' to '%s': %s", src, final_target, exc)
        return ActionResult.fail(
            message=f"Permission denied moving '{src.name}'.",
            error="PermissionDenied",
        )
    except OSError as exc:
        logger.error("OS error moving '%s' to '%s': %s", src, final_target, exc)
        return ActionResult.fail(
            message=f"Could not move '{src.name}': {exc}",
            error=str(exc),
        )


def get_file_info(path: str) -> ActionResult:
    """Retrieve structured metadata for a file or folder.

    Args:
        path: Path to inspect.

    Returns:
        ActionResult containing structured filesystem metadata:
        name, path, extension, size, created_time, modified_time,
        is_file, is_dir.
    """
    resolved = _resolve_safe_path(path)
    if not resolved:
        return ActionResult.fail(
            message="Invalid or empty path provided.",
            error="InvalidInput",
        )

    if not resolved.exists():
        return ActionResult.fail(
            message=f"Path does not exist: '{resolved}'.",
            error="FileNotFoundError",
        )

    try:
        stat = resolved.stat()
        created_dt = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat()
        modified_dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

        metadata: dict[str, Any] = {
            "name": resolved.name,
            "path": str(resolved),
            "extension": resolved.suffix.lower() if resolved.is_file() else "",
            "size": stat.st_size if resolved.is_file() else None,
            "created_time": created_dt,
            "modified_time": modified_dt,
            "is_file": resolved.is_file(),
            "is_dir": resolved.is_dir(),
        }

        return ActionResult.ok(
            message=f"Retrieved information for '{resolved.name}'.",
            data=metadata,
        )
    except PermissionError as exc:
        logger.error("Permission denied inspecting '%s': %s", resolved, exc)
        return ActionResult.fail(
            message=f"Permission denied accessing metadata for '{resolved.name}'.",
            error="PermissionDenied",
        )
    except OSError as exc:
        logger.error("OS error inspecting '%s': %s", resolved, exc)
        return ActionResult.fail(
            message=f"Could not retrieve metadata for '{resolved.name}': {exc}",
            error=str(exc),
        )


def list_folder(path: str, max_items: int = 100) -> ActionResult:
    """List subfolders and files in a directory with metadata.

    Args:
        path: Directory path to list.
        max_items: Maximum items to return.

    Returns:
        ActionResult containing folder count, file count, and item lists.
    """
    resolved = _resolve_safe_path(path)
    if not resolved:
        return ActionResult.fail(
            message="Invalid or empty directory path provided.",
            error="InvalidInput",
        )
    if not resolved.exists():
        return ActionResult.fail(
            message=f"Directory not found: '{resolved}'.",
            error="FileNotFoundError",
        )
    if not resolved.is_dir():
        return ActionResult.fail(
            message=f"Path is not a directory: '{resolved}'.",
            error="NotADirectoryError",
        )

    try:
        folders: list[dict[str, Any]] = []
        files: list[dict[str, Any]] = []
        for entry in sorted(resolved.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if len(folders) + len(files) >= max_items:
                break
            try:
                stat = entry.stat()
                mod_time = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                if entry.is_dir():
                    folders.append({
                        "name": entry.name,
                        "path": str(entry),
                        "modified": mod_time,
                    })
                else:
                    files.append({
                        "name": entry.name,
                        "path": str(entry),
                        "size": stat.st_size,
                        "modified": mod_time,
                    })
            except (OSError, PermissionError):
                continue

        items_summary = []
        if folders:
            items_summary.append("Folders: " + ", ".join(f["name"] for f in folders[:10]))
        if files:
            items_summary.append("Files: " + ", ".join(f["name"] for f in files[:10]))
        detail = (" (" + "; ".join(items_summary) + ")") if items_summary else ""

        return ActionResult.ok(
            message=f"Found {len(folders)} folder(s) and {len(files)} file(s) in '{resolved}'{detail}.",
            data={
                "path": str(resolved),
                "folder_count": len(folders),
                "file_count": len(files),
                "folders": folders,
                "files": files,
            },
        )
    except PermissionError as exc:
        logger.error("Permission denied listing folder '%s': %s", resolved, exc)
        return ActionResult.fail(
            message=f"Permission denied listing folder '{resolved}'.",
            error="PermissionDenied",
        )
    except OSError as exc:
        logger.error("OS error listing folder '%s': %s", resolved, exc)
        return ActionResult.fail(
            message=f"Could not list folder '{resolved}': {exc}",
            error=str(exc),
        )


def read_file(path: str, max_bytes: int = 50000) -> ActionResult:
    """Read the textual content of a file up to max_bytes.

    Args:
        path: Path of file to read.
        max_bytes: Maximum characters to read.

    Returns:
        ActionResult containing file content and size.
    """
    resolved = _resolve_safe_path(path)
    if not resolved:
        return ActionResult.fail(
            message="Invalid or empty file path provided.",
            error="InvalidInput",
        )
    if not resolved.exists():
        return ActionResult.fail(
            message=f"File not found: '{resolved}'.",
            error="FileNotFoundError",
        )
    if resolved.is_dir():
        return ActionResult.fail(
            message=f"Path is a directory, not a file: '{resolved}'. Use list_folder() instead.",
            error="IsADirectoryError",
        )

    try:
        with resolved.open("r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_bytes)

        return ActionResult.ok(
            message=f"Read {len(content)} characters from '{resolved.name}'.",
            data={
                "name": resolved.name,
                "path": str(resolved),
                "content": content,
                "size": resolved.stat().st_size,
            },
        )
    except PermissionError as exc:
        logger.error("Permission denied reading file '%s': %s", resolved, exc)
        return ActionResult.fail(
            message=f"Permission denied reading file '{resolved.name}'.",
            error="PermissionDenied",
        )
    except OSError as exc:
        logger.error("OS error reading file '%s': %s", resolved, exc)
        return ActionResult.fail(
            message=f"Could not read file '{resolved.name}': {exc}",
            error=str(exc),
        )


def write_file(path: str, content: str = "", mode: str = "write") -> ActionResult:
    """Create or modify a text file under any folder or subfolder.

    Args:
        path: Target file path.
        content: Text content to write.
        mode: 'write' (fail if file exists), 'overwrite' (replace), or 'append'.

    Returns:
        ActionResult indicating success and written byte size.
    """
    resolved = _resolve_safe_path(path)
    if not resolved:
        return ActionResult.fail(
            message="Invalid or empty file path provided.",
            error="InvalidInput",
        )
    if resolved.is_dir():
        return ActionResult.fail(
            message=f"Path is a directory, not a file: '{resolved}'.",
            error="IsADirectoryError",
        )

    norm_mode = (mode or "write").lower().strip()
    if norm_mode not in {"write", "overwrite", "append"}:
        return ActionResult.fail(
            message=f"Invalid write mode '{mode}'. Choose 'write', 'overwrite', or 'append'.",
            error="InvalidInput",
        )

    if norm_mode == "write" and resolved.exists():
        return ActionResult.fail(
            message=f"File already exists at '{resolved}'. Use mode='overwrite' or mode='append'.",
            error="FileExistsError",
        )

    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        file_mode = "a" if norm_mode == "append" else "w"
        with resolved.open(file_mode, encoding="utf-8") as f:
            f.write(content)

        logger.info("Wrote %d bytes to '%s' (mode=%s)", len(content), resolved, norm_mode)
        return ActionResult.ok(
            message=f"Successfully wrote {len(content)} characters to '{resolved.name}'.",
            data={
                "name": resolved.name,
                "path": str(resolved),
                "mode": norm_mode,
                "size": resolved.stat().st_size,
            },
        )
    except PermissionError as exc:
        logger.error("Permission denied writing file '%s': %s", resolved, exc)
        return ActionResult.fail(
            message=f"Permission denied writing file '{resolved.name}'.",
            error="PermissionDenied",
        )
    except OSError as exc:
        logger.error("OS error writing file '%s': %s", resolved, exc)
        return ActionResult.fail(
            message=f"Could not write file '{resolved.name}': {exc}",
            error=str(exc),
        )


def delete_file(path: str) -> ActionResult:
    """Safely delete a regular file.

    Args:
        path: Path of file to delete.

    Returns:
        ActionResult indicating success.
    """
    resolved = _resolve_safe_path(path)
    if not resolved:
        return ActionResult.fail(
            message="Invalid or empty file path provided.",
            error="InvalidInput",
        )
    if not resolved.exists():
        return ActionResult.fail(
            message=f"File not found: '{resolved}'.",
            error="FileNotFoundError",
        )
    if resolved.is_dir():
        return ActionResult.fail(
            message=f"Path is a directory, not a file: '{resolved}'. Use delete_folder() instead.",
            error="IsADirectoryError",
        )

    try:
        resolved.unlink()
        logger.info("Deleted file '%s'", resolved)
        return ActionResult.ok(
            message=f"Deleted file '{resolved.name}'.",
            data={"name": resolved.name, "path": str(resolved)},
        )
    except PermissionError as exc:
        logger.error("Permission denied deleting file '%s': %s", resolved, exc)
        return ActionResult.fail(
            message=f"Permission denied deleting file '{resolved.name}'.",
            error="PermissionDenied",
        )
    except OSError as exc:
        logger.error("OS error deleting file '%s': %s", resolved, exc)
        return ActionResult.fail(
            message=f"Could not delete file '{resolved.name}': {exc}",
            error=str(exc),
        )


def delete_folder(path: str, recursive: bool = False) -> ActionResult:
    """Safely delete a directory.

    Args:
        path: Path of folder to delete.
        recursive: If True, delete non-empty directory tree; if False, only empty directory.

    Returns:
        ActionResult indicating success.
    """
    resolved = _resolve_safe_path(path)
    if not resolved:
        return ActionResult.fail(
            message="Invalid or empty directory path provided.",
            error="InvalidInput",
        )
    if not resolved.exists():
        return ActionResult.fail(
            message=f"Folder not found: '{resolved}'.",
            error="FileNotFoundError",
        )
    if not resolved.is_dir():
        return ActionResult.fail(
            message=f"Path is a file, not a directory: '{resolved}'. Use delete_file() instead.",
            error="NotADirectoryError",
        )

    try:
        if recursive:
            shutil.rmtree(str(resolved))
        else:
            resolved.rmdir()
        logger.info("Deleted folder '%s' (recursive=%s)", resolved, recursive)
        return ActionResult.ok(
            message=f"Deleted folder '{resolved.name}'.",
            data={"name": resolved.name, "path": str(resolved)},
        )
    except OSError as exc:
        logger.error("Error deleting folder '%s': %s", resolved, exc)
        return ActionResult.fail(
            message=f"Could not delete folder '{resolved.name}': {exc}",
            error=str(exc),
        )


def find_folder_path(
    folder_name: str,
    root_location: Optional[str] = None,
    max_depth: int = 5,
) -> Optional[Path]:
    """Locate a folder by name across subfolders within a root location or available drives.

    Args:
        folder_name: The folder name to locate (e.g. 'CineCritic', 'Prac1', 'Study').
        root_location: Root search directory or drive (e.g. 'D:\\', 'E:\\', or None).
        max_depth: Maximum directory traversal depth (default 5).

    Returns:
        Resolved Path of the matching directory, or None if not found.
    """
    clean_name = folder_name.strip().strip("\"'").lower()
    if not clean_name:
        return None

    roots_to_try: list[Path] = []
    if root_location:
        resolved_root = _resolve_safe_path(root_location)
        if resolved_root and resolved_root.is_dir():
            roots_to_try.append(resolved_root)
    else:
        roots_to_try.append(Path.cwd())
        for drive_letter in ("D:\\", "E:\\", "C:\\"):
            p = Path(drive_letter)
            if p.exists() and p not in roots_to_try:
                roots_to_try.append(p)

    for root_dir in roots_to_try:
        # 1. Direct check
        direct = root_dir / folder_name.strip().strip("\"'")
        if direct.is_dir():
            return direct.resolve()

        # 2. Bounded directory traversal
        root_str = str(root_dir)
        try:
            for current_root, dirs, _ in os.walk(root_str):
                rel_path = os.path.relpath(current_root, root_str)
                depth = 0 if rel_path == "." else len(Path(rel_path).parts)
                if depth >= max_depth:
                    dirs.clear()
                    continue

                dirs[:] = [
                    d for d in dirs
                    if d.lower() not in IGNORED_SEARCH_DIRS
                ]

                for d in dirs:
                    if d.lower() == clean_name:
                        return (Path(current_root) / d).resolve()
        except (OSError, PermissionError):
            continue

    return None


def find_file_path(
    filename: str,
    root_location: Optional[str] = None,
    max_depth: int = 5,
) -> Optional[Path]:
    """Locate a file across subfolders by name or wildcard pattern.

    Args:
        filename: Filename or wildcard pattern (e.g. 'app.py', 'test_tts.py', '*.pdf').
        root_location: Starting directory (defaults to current working directory).
        max_depth: Maximum directory depth to search.

    Returns:
        Resolved Path if found, else None.
    """
    clean_name = filename.strip().strip("\"'")
    if not clean_name:
        return None

    # Check direct relative / absolute path first
    direct = _resolve_safe_path(clean_name)
    if direct and direct.is_file():
        return direct

    roots_to_try: list[Path] = []
    if root_location:
        res_loc = _resolve_safe_path(root_location)
        if res_loc and res_loc.is_dir():
            roots_to_try.append(res_loc)
    else:
        roots_to_try.append(Path.cwd())
        home = Path.home()
        for candidate in (home / "Documents", home / "Desktop", home / "Downloads"):
            if candidate.exists() and candidate not in roots_to_try:
                roots_to_try.append(candidate)

    pattern_lower = clean_name.lower()
    for root_dir in roots_to_try:
        root_str = str(root_dir)
        try:
            for current_root, dirs, files in os.walk(root_str):
                rel_path = os.path.relpath(current_root, root_str)
                depth = 0 if rel_path == "." else len(Path(rel_path).parts)
                if depth >= max_depth:
                    dirs.clear()
                    continue

                dirs[:] = [
                    d for d in dirs
                    if d.lower() not in IGNORED_SEARCH_DIRS
                ]

                for f in files:
                    f_lower = f.lower()
                    if f_lower == pattern_lower or fnmatch.fnmatch(f_lower, pattern_lower):
                        return (Path(current_root) / f).resolve()
        except (OSError, PermissionError):
            continue

    return None


def smart_create_folder(
    parent_folder: str,
    new_folder_name: Optional[str] = None,
    drive: Optional[str] = None,
) -> ActionResult:
    """Find a parent folder across subfolders or drives and create a new folder inside it.

    Allows commands like 'create a folder under d drive under CineCritic' or
    'create folder test under Prac1' without requiring full paths.

    Args:
        parent_folder: Name of the existing parent folder to find.
        new_folder_name: Name of the new folder to create (defaults to 'new_folder').
        drive: Target drive letter or root (e.g., 'D', 'D:\\', or None).

    Returns:
        ActionResult indicating success and created directory path.
    """
    clean_parent = parent_folder.strip().strip("\"'")
    clean_new = (new_folder_name or "new_folder").strip().strip("\"'")

    # Normalize drive or root location
    root_loc: Optional[str] = None
    if drive:
        d_str = str(drive).strip().strip("\"'")
        match_letter = re.match(r"^([a-zA-Z])(?:\s*:\s*|\s+drive)?$", d_str, re.IGNORECASE)
        if match_letter:
            root_loc = f"{match_letter.group(1).upper()}:\\"
        else:
            root_loc = d_str

    # Locate the parent directory
    parent_path = find_folder_path(clean_parent, root_location=root_loc)

    if not parent_path:
        base_dir = Path(root_loc) if root_loc and Path(root_loc).exists() else Path.cwd()
        target = base_dir / clean_parent / clean_new
        return create_folder(str(target))

    target = parent_path / clean_new
    res = create_folder(str(target))
    if res.success:
        return ActionResult.ok(
            message=f"Found parent folder '{clean_parent}' at '{parent_path}'. Folder '{clean_new}' created successfully at '{target}'.",
            data={
                "parent_path": str(parent_path),
                "created_path": str(target),
                "name": clean_new,
                "created": res.data.get("created", True) if res.data else True,
            },
        )
    return res


def run_file(path: str, location: Optional[str] = None) -> ActionResult:
    """Find and run a file from any subfolder or specified location.

    Supports running Python scripts (.py), Windows executables (.exe, .bat, .cmd),
    and opening document/media files with their default associated Windows application.

    Args:
        path: Filename, pattern, or path of the file to run.
        location: Optional root directory/drive to search within.

    Returns:
        ActionResult indicating execution status and resolved path.
    """
    resolved = find_file_path(path, root_location=location)
    if not resolved or not resolved.exists():
        return ActionResult.fail(
            message=f"Could not find file '{path}' in subfolders.",
            error="FileNotFoundError",
        )

    if resolved.is_dir():
        return ActionResult.fail(
            message=f"Path is a directory, not a runnable file: '{resolved}'. Use open_folder instead.",
            error="IsADirectoryError",
        )

    try:
        suffix = resolved.suffix.lower()
        if suffix == ".py":
            proc = subprocess.Popen(
                [sys.executable, str(resolved)],
                cwd=str(resolved.parent),
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            )
            logger.info("Launched python script '%s' (PID=%d)", resolved, proc.pid)
            return ActionResult.ok(
                message=f"Launched Python file '{resolved.name}' from '{resolved.parent}'.",
                data={"name": resolved.name, "path": str(resolved), "pid": proc.pid},
            )
        elif suffix in {".exe", ".bat", ".cmd"}:
            proc = subprocess.Popen(
                [str(resolved)],
                cwd=str(resolved.parent),
            )
            logger.info("Launched executable '%s' (PID=%d)", resolved, proc.pid)
            return ActionResult.ok(
                message=f"Launched executable '{resolved.name}' from '{resolved.parent}'.",
                data={"name": resolved.name, "path": str(resolved), "pid": proc.pid},
            )
        else:
            os.startfile(str(resolved))
            logger.info("Opened file '%s' via Windows shell", resolved)
            return ActionResult.ok(
                message=f"Opened file '{resolved.name}' from '{resolved.parent}'.",
                data={"name": resolved.name, "path": str(resolved)},
            )
    except PermissionError as exc:
        logger.error("Permission denied running file '%s': %s", resolved, exc)
        return ActionResult.fail(
            message=f"Permission denied running file '{resolved.name}'.",
            error="PermissionDenied",
        )
    except Exception as exc:
        logger.error("Error running file '%s': %s", resolved, exc)
        return ActionResult.fail(
            message=f"Could not run file '{resolved.name}': {exc}",
            error=str(exc),
        )
