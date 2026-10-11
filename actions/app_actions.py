"""Application management actions for Astra.

Provides deterministic Windows application discovery, launch, monitoring,
and termination tools.

Functions:
- open_application(name: str) -> ActionResult
- close_application(name: str) -> ActionResult
- is_application_running(name: str) -> ActionResult
- find_application(name: str) -> ActionResult
"""

from __future__ import annotations

import os
import shutil
import subprocess
import winreg
from typing import Any, List, Optional, Set
import psutil

from actions.base import ActionResult, get_logger

logger = get_logger("astra.actions.app")

# Friendly names and common aliases mapped to canonical Windows executable names
KNOWN_APP_ALIASES: dict[str, list[str]] = {
    "chrome": ["chrome.exe"],
    "google chrome": ["chrome.exe"],
    "edge": ["msedge.exe"],
    "microsoft edge": ["msedge.exe"],
    "msedge": ["msedge.exe"],
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe", "calculatorapp.exe"],
    "calc": ["calc.exe"],
    "code": ["code.cmd", "code.exe"],
    "vscode": ["code.cmd", "code.exe"],
    "vs code": ["code.cmd", "code.exe"],
    "visual studio code": ["code.cmd", "code.exe"],
    "cmd": ["cmd.exe"],
    "command prompt": ["cmd.exe"],
    "powershell": ["powershell.exe", "pwsh.exe"],
    "terminal": ["wt.exe", "powershell.exe"],
    "windows terminal": ["wt.exe"],
    "paint": ["mspaint.exe"],
    "wordpad": ["wordpad.exe"],
    "taskmgr": ["taskmgr.exe"],
    "task manager": ["taskmgr.exe"],
    "file explorer": ["explorer.exe"],
    "explorer": ["explorer.exe"],
}

# Processes critical to the OS or Astra itself that must NEVER be terminated
PROTECTED_PROCESSES: Set[str] = {
    "system",
    "registry",
    "smss.exe",
    "csrss.exe",
    "wininit.exe",
    "winlogon.exe",
    "services.exe",
    "lsass.exe",
    "svchost.exe",
    "fontdrvhost.exe",
    "dwm.exe",
    "explorer.exe",
    "sihost.exe",
    "taskhostw.exe",
    "runtimebroker.exe",
    "python.exe",
    "pythonw.exe",
    "py.exe",
}


def _normalize_name(name: Any) -> Optional[str]:
    """Validate and clean an input application name."""
    if not isinstance(name, str):
        return None
    cleaned = name.strip()
    return cleaned if cleaned else None


def _get_target_executables(name: str) -> list[str]:
    """Resolve an application name or alias to candidate executable filenames."""
    lowered = name.lower()
    if lowered in KNOWN_APP_ALIASES:
        return KNOWN_APP_ALIASES[lowered]

    # If the user passed something like 'spotify' or 'slack.exe'
    if lowered.endswith(".exe") or lowered.endswith(".cmd") or lowered.endswith(".bat"):
        return [lowered]
    return [f"{lowered}.exe", lowered]


def _search_windows_app_paths(exe_name: str) -> Optional[str]:
    """Search Windows Registry App Paths for registered application executables."""
    subkeys = [
        rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}",
        rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}.exe"
        if not exe_name.endswith(".exe")
        else None,
    ]

    roots = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]

    for root in roots:
        for subkey in subkeys:
            if not subkey:
                continue
            try:
                with winreg.OpenKey(root, subkey) as key:
                    # Default value contains the primary executable path
                    val, _ = winreg.QueryValueEx(key, "")
                    if val and os.path.exists(val):
                        return val
            except (OSError, WindowsError, FileNotFoundError):
                continue
    return None


def _search_common_directories(exe_name: str) -> Optional[str]:
    """Search standard Windows application directories."""
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local_app_data = os.environ.get("LOCALAPPDATA", "")

    search_dirs = [
        program_files,
        program_files_x86,
        os.path.join(local_app_data, "Programs") if local_app_data else None,
    ]

    target = exe_name.lower()
    if not target.endswith(".exe"):
        target = f"{target}.exe"

    for base_dir in search_dirs:
        if not base_dir or not os.path.isdir(base_dir):
            continue
        # Shallow walk (up to 3 levels) to avoid long blocking disk operations
        for root, dirs, files in os.walk(base_dir):
            depth = root[len(base_dir) :].count(os.sep)
            if depth >= 3:
                dirs.clear()  # Don't recurse deeper
                continue
            for file in files:
                if file.lower() == target:
                    full_path = os.path.join(root, file)
                    if os.path.exists(full_path):
                        return full_path
    return None


def find_application(name: str) -> ActionResult:
    """Locate an installed application executable deterministically.

    Search precedence:
    1. Direct file path if valid
    2. System PATH (via shutil.which)
    3. Windows Registry App Paths (HKLM & HKCU)
    4. Standard Program Files / LocalAppData directories

    Args:
        name: Name, alias, or path of the application.

    Returns:
        ActionResult with path details on success, or failure message.
    """
    cleaned_name = _normalize_name(name)
    if not cleaned_name:
        return ActionResult.fail(
            message="Application name must be a non-empty string.",
            error="InvalidInput",
        )

    # 1. Direct path check
    if os.path.isfile(cleaned_name):
        abs_path = os.path.abspath(cleaned_name)
        return ActionResult.ok(
            message=f"Found application '{cleaned_name}' at '{abs_path}'.",
            data={
                "name": cleaned_name,
                "path": abs_path,
                "executable": os.path.basename(abs_path),
            },
        )

    candidates = _get_target_executables(cleaned_name)

    # 2. Check PATH
    for candidate in candidates:
        found_in_path = shutil.which(candidate)
        if found_in_path and os.path.exists(found_in_path):
            abs_path = os.path.abspath(found_in_path)
            return ActionResult.ok(
                message=f"Found application '{cleaned_name}' at '{abs_path}'.",
                data={
                    "name": cleaned_name,
                    "path": abs_path,
                    "executable": os.path.basename(abs_path),
                },
            )

    # 3. Check Windows Registry App Paths
    for candidate in candidates:
        found_in_reg = _search_windows_app_paths(candidate)
        if found_in_reg:
            abs_path = os.path.abspath(found_in_reg)
            return ActionResult.ok(
                message=f"Found application '{cleaned_name}' at '{abs_path}'.",
                data={
                    "name": cleaned_name,
                    "path": abs_path,
                    "executable": os.path.basename(abs_path),
                },
            )

    # 4. Check Common Directories
    for candidate in candidates:
        found_in_dirs = _search_common_directories(candidate)
        if found_in_dirs:
            abs_path = os.path.abspath(found_in_dirs)
            return ActionResult.ok(
                message=f"Found application '{cleaned_name}' at '{abs_path}'.",
                data={
                    "name": cleaned_name,
                    "path": abs_path,
                    "executable": os.path.basename(abs_path),
                },
            )

    return ActionResult.fail(
        message=f"Application '{cleaned_name}' could not be found.",
        error="ApplicationNotFound",
    )


def open_application(name: str) -> ActionResult:
    """Launch an installed Windows application asynchronously.

    Locates the application using `find_application` and starts it
    detached from the current process without blocking.

    Args:
        name: Name, alias, or path of the application.

    Returns:
        ActionResult containing execution details and process PID on success.
    """
    find_result = find_application(name)
    if not find_result.success:
        return find_result

    app_path = find_result.data["path"]
    try:
        # Use CREATE_NEW_PROCESS_GROUP and DETACHED_PROCESS so the child
        # runs independently and does not block Astra.
        creation_flags = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )

        # For batch/cmd scripts, shell=True is needed on Windows
        is_script = app_path.lower().endswith((".cmd", ".bat"))
        proc = subprocess.Popen(
            [app_path] if not is_script else app_path,
            shell=is_script,
            creationflags=creation_flags if not is_script else 0,
            close_fds=True,
        )

        logger.info("Launched application '%s' (PID: %d)", app_path, proc.pid)
        return ActionResult.ok(
            message=f"Application '{name}' opened successfully.",
            data={
                "name": name,
                "path": app_path,
                "pid": proc.pid,
            },
        )
    except PermissionError as exc:
        logger.error("Permission denied when launching '%s': %s", app_path, exc)
        return ActionResult.fail(
            message=f"Permission denied when launching application '{name}'.",
            error="PermissionDenied",
        )
    except OSError as exc:
        # Fallback to os.startfile for Windows shell association handling
        try:
            os.startfile(app_path)
            logger.info("Launched '%s' via os.startfile fallback.", app_path)
            return ActionResult.ok(
                message=f"Application '{name}' opened successfully.",
                data={
                    "name": name,
                    "path": app_path,
                    "pid": None,
                },
            )
        except Exception as fallback_exc:
            logger.error("Failed to launch '%s': %s", app_path, fallback_exc)
            return ActionResult.fail(
                message=f"Failed to launch application '{name}': {fallback_exc}",
                error=str(fallback_exc),
            )
    except Exception as exc:
        logger.error("Unexpected error opening '%s': %s", name, exc)
        return ActionResult.fail(
            message=f"Failed to open application '{name}': {exc}",
            error=str(exc),
        )


def is_application_running(name: str) -> ActionResult:
    """Check if any instances of an application are currently running.

    Performs case-insensitive inspection of active processes against
    the application name and its known executable aliases.

    Args:
        name: Name, alias, or executable of the application.

    Returns:
        ActionResult with running status and list of matching process instances.
    """
    cleaned_name = _normalize_name(name)
    if not cleaned_name:
        return ActionResult.fail(
            message="Application name must be a non-empty string.",
            error="InvalidInput",
        )

    candidates = {c.lower() for c in _get_target_executables(cleaned_name)}
    # Add candidate names without extension for matching (e.g. 'code' for 'code.exe')
    for c in list(candidates):
        if c.endswith((".exe", ".cmd", ".bat")):
            candidates.add(os.path.splitext(c)[0])

    matching_instances: list[dict[str, Any]] = []

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            p_name = proc.info["name"]
            if not p_name:
                continue
            p_name_lower = p_name.lower()
            p_base_lower = os.path.splitext(p_name_lower)[0]

            if p_name_lower in candidates or p_base_lower in candidates:
                matching_instances.append(
                    {
                        "pid": proc.info["pid"],
                        "name": p_name,
                    }
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    is_running = len(matching_instances) > 0
    message = (
        f"Application '{cleaned_name}' is currently running ({len(matching_instances)} instance(s))."
        if is_running
        else f"Application '{cleaned_name}' is not currently running."
    )

    return ActionResult.ok(
        message=message,
        data={
            "running": is_running,
            "count": len(matching_instances),
            "instances": matching_instances,
        },
    )


def close_application(name: str) -> ActionResult:
    """Safely terminate running instances of an application.

    Enforces safety guards:
    - Critical system and Astra processes cannot be closed.
    - Matches exact process names to prevent terminating unintended processes.
    - Attempts graceful termination first before force-killing.

    Args:
        name: Name, alias, or executable of the application.

    Returns:
        ActionResult indicating success and terminated PIDs.
    """
    cleaned_name = _normalize_name(name)
    if not cleaned_name:
        return ActionResult.fail(
            message="Application name must be a non-empty string.",
            error="InvalidInput",
        )

    candidates = {c.lower() for c in _get_target_executables(cleaned_name)}
    for c in list(candidates):
        if c.endswith((".exe", ".cmd", ".bat")):
            candidates.add(os.path.splitext(c)[0])

    # Safety check: Protect critical system processes and Astra itself
    for candidate in candidates:
        candidate_exe = candidate if candidate.endswith(".exe") else f"{candidate}.exe"
        if candidate_exe in PROTECTED_PROCESSES or candidate in PROTECTED_PROCESSES:
            logger.warning("Attempted to close protected process '%s'", candidate)
            return ActionResult.fail(
                message=f"Terminating protected process '{cleaned_name}' is disallowed for system safety.",
                error="ProtectedProcessError",
            )

    target_procs: list[psutil.Process] = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            p_name = proc.info["name"]
            if not p_name:
                continue
            p_name_lower = p_name.lower()
            p_base_lower = os.path.splitext(p_name_lower)[0]

            if p_name_lower in candidates or p_base_lower in candidates:
                target_procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    if not target_procs:
        return ActionResult.fail(
            message=f"Application '{cleaned_name}' is not currently running.",
            error="ProcessNotFound",
        )

    terminated_pids: list[int] = []
    access_denied_count = 0

    # 1. Graceful termination
    for proc in target_procs:
        try:
            proc.terminate()
        except psutil.AccessDenied:
            access_denied_count += 1
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            pass

    # 2. Wait up to 1.5 seconds for processes to exit
    _, alive = psutil.wait_procs(target_procs, timeout=1.5)

    # 3. Force kill any remaining processes
    for proc in alive:
        try:
            proc.kill()
        except psutil.AccessDenied:
            access_denied_count += 1
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            pass

    # Final check of who was terminated
    for proc in target_procs:
        try:
            if not proc.is_running():
                terminated_pids.append(proc.pid)
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            terminated_pids.append(proc.pid)

    if not terminated_pids and access_denied_count > 0:
        return ActionResult.fail(
            message=f"Permission denied when attempting to close application '{cleaned_name}'.",
            error="AccessDenied",
        )

    logger.info(
        "Closed application '%s'. Terminated PIDs: %s",
        cleaned_name,
        terminated_pids,
    )
    return ActionResult.ok(
        message=f"Closed application '{cleaned_name}' ({len(terminated_pids)} instance(s) terminated).",
        data={
            "name": cleaned_name,
            "terminated_pids": terminated_pids,
            "count": len(terminated_pids),
        },
    )
