"""File and folder management actions for Astra.

Provides deterministic tools for file inspection, folder creation,
safe renaming, non-destructive moving, and Windows shell file opening.

Functions:
- open_file(path: str) -> ActionResult
- open_folder(path: str) -> ActionResult
- search_file(name: str, location: Optional[str] = None) -> ActionResult
- create_folder(path: str) -> ActionResult
- rename_file(old_path: str, new_path: str) -> ActionResult
- move_file(source: str, destination: str) -> ActionResult
- get_file_info(path: str) -> ActionResult
"""

from __future__ import annotations

from datetime import datetime, timezone
import fnmatch
import os
from pathlib import Path
import shutil
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
    "appdata",
}


def _resolve_safe_path(raw_path: Any) -> Optional[Path]:
    """Validate, expand, and resolve a file/folder path."""
    if not isinstance(raw_path, (str, Path)):
        return None
    raw_str = str(raw_path).strip()
    if not raw_str:
        return None
    try:
        # Expand environment variables (%USERPROFILE%) and user home (~)
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
