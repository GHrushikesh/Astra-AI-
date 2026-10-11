"""System information and Windows control actions for Astra.

Provides read-only hardware/OS diagnostics (Milestone 4) and
deterministic Windows OS controls (Milestone 5).

Milestone 4 Functions:
- get_cpu_usage() -> ActionResult
- get_memory_usage() -> ActionResult
- get_disk_usage(path="C:\\") -> ActionResult
- get_battery_status() -> ActionResult
- get_network_status() -> ActionResult
- get_os_info() -> ActionResult
- get_running_processes(limit=50) -> ActionResult
- get_system_info() -> ActionResult

Milestone 5 Functions:
- volume_up(steps=1) -> ActionResult
- volume_down(steps=1) -> ActionResult
- mute() -> ActionResult
- unmute() -> ActionResult
- toggle_mute() -> ActionResult
- take_screenshot(save_dir=None, filename=None) -> ActionResult
- lock_pc() -> ActionResult
- sleep_pc(confirmed=False) -> ActionResult
- restart_pc(confirmed=False) -> ActionResult
- shutdown_pc(confirmed=False) -> ActionResult
"""

from __future__ import annotations

import ctypes
from datetime import datetime
import os
from pathlib import Path
import platform
import socket
import subprocess
import time
from typing import Any, Dict, List, Optional
from PIL import ImageGrab
import psutil

from actions.base import ActionResult, get_logger

logger = get_logger("astra.actions.system")

# Windows Virtual-Key codes for multimedia
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
KEYEVENTF_KEYUP = 0x0002

__all__ = [
    # System Info (Milestone 4)
    "get_cpu_usage",
    "get_memory_usage",
    "get_disk_usage",
    "get_battery_status",
    "get_network_status",
    "get_os_info",
    "get_running_processes",
    "get_system_info",
    # Windows Controls (Milestone 5)
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
]


# ==============================================================================
# MILESTONE 4: SYSTEM INFORMATION
# ==============================================================================

def get_cpu_usage(interval: float = 0.1) -> ActionResult:
    """Retrieve CPU usage percentage, core counts, and frequency.

    Args:
        interval: Sampling interval in seconds for cpu_percent (default: 0.1).

    Returns:
        ActionResult containing structured CPU metrics.
    """
    try:
        percent = psutil.cpu_percent(interval=interval)
        cores_logical = psutil.cpu_count(logical=True)
        cores_physical = psutil.cpu_count(logical=False)
        freq = psutil.cpu_freq()

        data: dict[str, Any] = {
            "percent": percent,
            "cores_logical": cores_logical,
            "cores_physical": cores_physical,
            "frequency_mhz": {
                "current": freq.current if freq else None,
                "min": freq.min if freq else None,
                "max": freq.max if freq else None,
            },
        }

        return ActionResult.ok(
            message=f"CPU usage: {percent}%",
            data=data,
        )
    except Exception as exc:
        logger.error("Failed to retrieve CPU usage: %s", exc)
        return ActionResult.fail(
            message=f"Failed to retrieve CPU usage: {exc}",
            error=str(exc),
        )


def get_memory_usage() -> ActionResult:
    """Retrieve RAM total, used, available, and percentage metrics.

    Returns:
        ActionResult containing structured memory diagnostics.
    """
    try:
        mem = psutil.virtual_memory()
        total_gb = round(mem.total / (1024**3), 2)
        used_gb = round(mem.used / (1024**3), 2)
        available_gb = round(mem.available / (1024**3), 2)

        data: dict[str, Any] = {
            "total_bytes": mem.total,
            "available_bytes": mem.available,
            "used_bytes": mem.used,
            "percent": mem.percent,
            "total_gb": total_gb,
            "used_gb": used_gb,
            "available_gb": available_gb,
        }

        return ActionResult.ok(
            message=f"Memory usage: {mem.percent}% ({used_gb} GB / {total_gb} GB)",
            data=data,
        )
    except Exception as exc:
        logger.error("Failed to retrieve memory usage: %s", exc)
        return ActionResult.fail(
            message=f"Failed to retrieve memory usage: {exc}",
            error=str(exc),
        )


def get_disk_usage(path: str = "C:\\") -> ActionResult:
    """Retrieve total, used, free disk space and percentage for a path.

    Args:
        path: Drive root or directory to inspect (default: 'C:\\').

    Returns:
        ActionResult containing structured disk metrics.
    """
    try:
        target_path = (
            path
            if os.path.exists(path)
            else os.path.splitdrive(os.getcwd())[0] + "\\"
        )
        usage = psutil.disk_usage(target_path)

        total_gb = round(usage.total / (1024**3), 2)
        used_gb = round(usage.used / (1024**3), 2)
        free_gb = round(usage.free / (1024**3), 2)

        data: dict[str, Any] = {
            "path": target_path,
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "percent": usage.percent,
            "total_gb": total_gb,
            "used_gb": used_gb,
            "free_gb": free_gb,
        }

        return ActionResult.ok(
            message=f"Disk usage for '{target_path}': {usage.percent}% ({used_gb} GB / {total_gb} GB)",
            data=data,
        )
    except Exception as exc:
        logger.error("Failed to retrieve disk usage for '%s': %s", path, exc)
        return ActionResult.fail(
            message=f"Failed to retrieve disk usage for '{path}': {exc}",
            error=str(exc),
        )


def get_battery_status() -> ActionResult:
    """Retrieve battery percentage and charging status safely.

    Handles systems without batteries (such as desktop PCs) gracefully.

    Returns:
        ActionResult with battery data or indication of no battery.
    """
    try:
        battery = psutil.sensors_battery()
        if battery is None:
            return ActionResult.ok(
                message="No battery detected on this system.",
                data={
                    "has_battery": False,
                    "percent": None,
                    "power_plugged": None,
                    "seconds_left": None,
                },
            )

        seconds_left = (
            battery.secsleft
            if battery.secsleft != psutil.POWER_TIME_UNLIMITED
            else None
        )
        data: dict[str, Any] = {
            "has_battery": True,
            "percent": battery.percent,
            "power_plugged": battery.power_plugged,
            "seconds_left": seconds_left,
        }

        status_str = "Plugged in" if battery.power_plugged else "Discharging"
        return ActionResult.ok(
            message=f"Battery: {battery.percent}% ({status_str})",
            data=data,
        )
    except Exception as exc:
        logger.error("Failed to retrieve battery status: %s", exc)
        return ActionResult.fail(
            message=f"Failed to retrieve battery status: {exc}",
            error=str(exc),
        )


def get_network_status() -> ActionResult:
    """Retrieve network connection status and interface metrics.

    Does not modify any network settings.

    Returns:
        ActionResult containing hostname, local IP, interfaces, and traffic counters.
    """
    try:
        hostname = socket.gethostname()
        try:
            ip_address = socket.gethostbyname(hostname)
        except Exception:
            ip_address = "127.0.0.1"

        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
        io_counters = psutil.net_io_counters()

        interfaces: list[dict[str, Any]] = []
        for if_name, stat in stats.items():
            if_addrs = [
                addr.address
                for addr in addrs.get(if_name, [])
                if addr.family == socket.AF_INET
            ]
            interfaces.append(
                {
                    "name": if_name,
                    "is_up": stat.isup,
                    "speed_mbps": stat.speed,
                    "ipv4_addresses": if_addrs,
                }
            )

        data: dict[str, Any] = {
            "hostname": hostname,
            "ip_address": ip_address,
            "interfaces": interfaces,
            "bytes_sent": io_counters.bytes_sent if io_counters else 0,
            "bytes_recv": io_counters.bytes_recv if io_counters else 0,
        }

        return ActionResult.ok(
            message=f"Network status retrieved for '{hostname}' ({ip_address})",
            data=data,
        )
    except Exception as exc:
        logger.error("Failed to retrieve network status: %s", exc)
        return ActionResult.fail(
            message=f"Failed to retrieve network status: {exc}",
            error=str(exc),
        )


def get_os_info() -> ActionResult:
    """Retrieve Windows operating system and architecture information.

    Returns:
        ActionResult containing OS name, release, build, and hardware architecture.
    """
    try:
        data: dict[str, Any] = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "hostname": platform.node(),
            "python_version": platform.python_version(),
        }

        return ActionResult.ok(
            message=f"OS: {platform.system()} {platform.release()} (Build {platform.version()})",
            data=data,
        )
    except Exception as exc:
        logger.error("Failed to retrieve OS info: %s", exc)
        return ActionResult.fail(
            message=f"Failed to retrieve OS info: {exc}",
            error=str(exc),
        )


def get_running_processes(limit: int = 50) -> ActionResult:
    """Retrieve structured list of active processes sorted by memory usage.

    Gracefully handles processes that terminate or are inaccessible during inspection.

    Args:
        limit: Maximum number of processes to return (default: 50).

    Returns:
        ActionResult containing list of active process metadata.
    """
    try:
        procs: list[dict[str, Any]] = []
        for proc in psutil.process_iter(
            ["pid", "name", "status", "memory_percent"]
        ):
            try:
                info = proc.info
                procs.append(
                    {
                        "pid": info["pid"],
                        "name": info["name"] or "Unknown",
                        "status": info["status"] or "unknown",
                        "memory_percent": round(
                            info["memory_percent"] or 0.0, 2
                        ),
                    }
                )
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue

        procs.sort(key=lambda p: p["memory_percent"], reverse=True)
        bounded = procs[:limit]

        data: dict[str, Any] = {
            "count": len(bounded),
            "total_running": len(procs),
            "processes": bounded,
        }

        return ActionResult.ok(
            message=f"Retrieved {len(bounded)} of {len(procs)} active processes.",
            data=data,
        )
    except Exception as exc:
        logger.error("Failed to retrieve running processes: %s", exc)
        return ActionResult.fail(
            message=f"Failed to retrieve running processes: {exc}",
            error=str(exc),
        )


def get_system_info() -> ActionResult:
    """Aggregate CPU, memory, disk, battery, network, and OS diagnostics into one structured payload.

    Returns:
        ActionResult containing complete system diagnostics for the AI Core.
    """
    os_info = get_os_info()
    cpu_info = get_cpu_usage()
    mem_info = get_memory_usage()
    disk_info = get_disk_usage()
    battery_info = get_battery_status()
    net_info = get_network_status()

    combined: dict[str, Any] = {
        "os": os_info.data,
        "cpu": cpu_info.data,
        "memory": mem_info.data,
        "disk": disk_info.data,
        "battery": battery_info.data,
        "network": net_info.data,
    }

    return ActionResult.ok(
        message="System diagnostics retrieved successfully.",
        data=combined,
    )


# ==============================================================================
# MILESTONE 5: BASIC WINDOWS CONTROLS
# ==============================================================================

def _send_volume_key(vk: int, count: int = 1) -> None:
    """Send Windows multimedia virtual-key events using user32.keybd_event."""
    user32 = ctypes.windll.user32
    for _ in range(max(1, count)):
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def volume_up(steps: int = 1) -> ActionResult:
    """Increase system volume using Windows multimedia key events.

    Args:
        steps: Number of volume increments to apply (default: 1).

    Returns:
        ActionResult with operation status.
    """
    try:
        _send_volume_key(VK_VOLUME_UP, count=steps)
        logger.info("Volume increased by %d step(s)", steps)
        return ActionResult.ok(
            message=f"Volume increased ({steps} step(s)).",
            data={"action": "volume_up", "steps": steps},
        )
    except Exception as exc:
        logger.error("Failed to increase volume: %s", exc)
        return ActionResult.fail(
            message=f"Failed to increase volume: {exc}",
            error=str(exc),
        )


def volume_down(steps: int = 1) -> ActionResult:
    """Decrease system volume using Windows multimedia key events.

    Args:
        steps: Number of volume decrements to apply (default: 1).

    Returns:
        ActionResult with operation status.
    """
    try:
        _send_volume_key(VK_VOLUME_DOWN, count=steps)
        logger.info("Volume decreased by %d step(s)", steps)
        return ActionResult.ok(
            message=f"Volume decreased ({steps} step(s)).",
            data={"action": "volume_down", "steps": steps},
        )
    except Exception as exc:
        logger.error("Failed to decrease volume: %s", exc)
        return ActionResult.fail(
            message=f"Failed to decrease volume: {exc}",
            error=str(exc),
        )


def toggle_mute() -> ActionResult:
    """Toggle system audio mute state using Windows multimedia key event.

    Returns:
        ActionResult with operation status.
    """
    try:
        _send_volume_key(VK_VOLUME_MUTE, count=1)
        logger.info("Volume mute toggled")
        return ActionResult.ok(
            message="Volume mute toggled.",
            data={"action": "toggle_mute"},
        )
    except Exception as exc:
        logger.error("Failed to toggle mute: %s", exc)
        return ActionResult.fail(
            message=f"Failed to toggle mute: {exc}",
            error=str(exc),
        )


def mute() -> ActionResult:
    """Mute system audio.

    Uses Windows multimedia mute key event to ensure mute state.

    Returns:
        ActionResult with operation status.
    """
    try:
        _send_volume_key(VK_VOLUME_MUTE, count=1)
        logger.info("Audio mute triggered")
        return ActionResult.ok(
            message="Audio mute triggered.",
            data={"action": "mute"},
        )
    except Exception as exc:
        logger.error("Failed to mute audio: %s", exc)
        return ActionResult.fail(
            message=f"Failed to mute audio: {exc}",
            error=str(exc),
        )


def unmute() -> ActionResult:
    """Unmute system audio.

    On Windows, emitting volume-up immediately cancels the mute state without
    unintended volume jumps.

    Returns:
        ActionResult with operation status.
    """
    try:
        # On Windows, pressing Volume Up immediately unmutes the master channel.
        # Following with Volume Down balances the level back.
        _send_volume_key(VK_VOLUME_UP, count=1)
        _send_volume_key(VK_VOLUME_DOWN, count=1)
        logger.info("Audio unmuted")
        return ActionResult.ok(
            message="Audio unmuted.",
            data={"action": "unmute"},
        )
    except Exception as exc:
        logger.error("Failed to unmute audio: %s", exc)
        return ActionResult.fail(
            message=f"Failed to unmute audio: {exc}",
            error=str(exc),
        )


def take_screenshot(
    save_dir: Optional[str] = None,
    filename: Optional[str] = None,
) -> ActionResult:
    """Capture the screen and save to a file without overwriting.

    Uses Pillow (ImageGrab) for capturing. Generates a timestamped filename
    by default and automatically resolves collisions.

    Args:
        save_dir: Destination directory (defaults to user's Pictures/Screenshots or cwd/screenshots).
        filename: Optional custom filename (e.g. 'capture.png').

    Returns:
        ActionResult with saved path, dimensions, and filename.
    """
    try:
        # 1. Determine target directory
        if save_dir:
            target_dir = Path(os.path.expandvars(save_dir)).expanduser().resolve()
        else:
            user_profile = os.environ.get("USERPROFILE")
            if user_profile and os.path.isdir(os.path.join(user_profile, "Pictures")):
                target_dir = Path(user_profile) / "Pictures" / "Screenshots"
            else:
                target_dir = Path.cwd() / "screenshots"

        target_dir.mkdir(parents=True, exist_ok=True)

        # 2. Determine unique target filename
        if filename and filename.strip():
            base_name = filename.strip()
            if not base_name.lower().endswith(".png"):
                base_name += ".png"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"screenshot_{timestamp}.png"

        stem = Path(base_name).stem
        ext = Path(base_name).suffix or ".png"

        target_path = target_dir / f"{stem}{ext}"
        counter = 1
        while target_path.exists():
            target_path = target_dir / f"{stem}_{counter}{ext}"
            counter += 1

        # 3. Capture screen and save
        screenshot = ImageGrab.grab()
        screenshot.save(str(target_path), format="PNG")
        logger.info("Saved screenshot to '%s'", target_path)

        return ActionResult.ok(
            message=f"Screenshot saved to '{target_path.name}'.",
            data={
                "path": str(target_path),
                "filename": target_path.name,
                "width": screenshot.width,
                "height": screenshot.height,
                "format": "PNG",
            },
        )
    except Exception as exc:
        logger.error("Failed to take screenshot: %s", exc)
        return ActionResult.fail(
            message=f"Failed to capture screenshot: {exc}",
            error=str(exc),
        )


def lock_pc() -> ActionResult:
    """Lock the Windows workstation immediately.

    This is a reversible security action that calls Windows LockWorkStation API.

    Returns:
        ActionResult indicating whether lock was initiated.
    """
    try:
        # LockWorkStation returns non-zero on success
        res = ctypes.windll.user32.LockWorkStation()
        if res == 0:
            return ActionResult.fail(
                message="Windows LockWorkStation API failed.",
                error="LockFailed",
            )
        logger.info("Windows workstation locked")
        return ActionResult.ok(
            message="Workstation locked successfully.",
            data={"locked": True},
        )
    except Exception as exc:
        logger.error("Failed to lock workstation: %s", exc)
        return ActionResult.fail(
            message=f"Failed to lock workstation: {exc}",
            error=str(exc),
        )


def sleep_pc(confirmed: bool = False) -> ActionResult:
    """Put the Windows PC to sleep.

    Requires explicit confirmation (confirmed=True) to prevent disruptive execution.

    Args:
        confirmed: Explicit confirmation flag (must be True to execute).

    Returns:
        ActionResult indicating sleep initiation or confirmation requirement.
    """
    if not confirmed:
        return ActionResult.fail(
            message="Action 'sleep_pc' requires explicit confirmation. Pass confirmed=True to execute.",
            error="ConfirmationRequired",
            data={"action": "sleep_pc", "confirmed": False, "requires_confirmation": True},
        )

    try:
        logger.warning("Initiating PC sleep (confirmed=True)")
        # Call SetSuspendState(bHibernate=0, bForce=1, bWakeupEventsDisabled=0)
        res = ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
        return ActionResult.ok(
            message="PC sleep state initiated successfully.",
            data={"action": "sleep_pc", "confirmed": True, "result": res},
        )
    except Exception as exc:
        logger.error("Failed to put PC to sleep: %s", exc)
        return ActionResult.fail(
            message=f"Failed to put PC to sleep: {exc}",
            error=str(exc),
        )


def restart_pc(confirmed: bool = False) -> ActionResult:
    """Restart the Windows PC.

    Requires explicit confirmation (confirmed=True) to prevent disruptive execution.

    Args:
        confirmed: Explicit confirmation flag (must be True to execute).

    Returns:
        ActionResult indicating restart initiation or confirmation requirement.
    """
    if not confirmed:
        return ActionResult.fail(
            message="Action 'restart_pc' requires explicit confirmation. Pass confirmed=True to execute.",
            error="ConfirmationRequired",
            data={"action": "restart_pc", "confirmed": False, "requires_confirmation": True},
        )

    try:
        logger.warning("Initiating PC restart (confirmed=True)")
        # Execute Windows shutdown /r /t 0
        subprocess.run(["shutdown", "/r", "/t", "0"], check=True)
        return ActionResult.ok(
            message="PC restart initiated successfully.",
            data={"action": "restart_pc", "confirmed": True},
        )
    except Exception as exc:
        logger.error("Failed to restart PC: %s", exc)
        return ActionResult.fail(
            message=f"Failed to restart PC: {exc}",
            error=str(exc),
        )


def shutdown_pc(confirmed: bool = False) -> ActionResult:
    """Shut down the Windows PC.

    Requires explicit confirmation (confirmed=True) to prevent disruptive execution.

    Args:
        confirmed: Explicit confirmation flag (must be True to execute).

    Returns:
        ActionResult indicating shutdown initiation or confirmation requirement.
    """
    if not confirmed:
        return ActionResult.fail(
            message="Action 'shutdown_pc' requires explicit confirmation. Pass confirmed=True to execute.",
            error="ConfirmationRequired",
            data={"action": "shutdown_pc", "confirmed": False, "requires_confirmation": True},
        )

    try:
        logger.warning("Initiating PC shutdown (confirmed=True)")
        # Execute Windows shutdown /s /t 0
        subprocess.run(["shutdown", "/s", "/t", "0"], check=True)
        return ActionResult.ok(
            message="PC shutdown initiated successfully.",
            data={"action": "shutdown_pc", "confirmed": True},
        )
    except Exception as exc:
        logger.error("Failed to shut down PC: %s", exc)
        return ActionResult.fail(
            message=f"Failed to shut down PC: {exc}",
            error=str(exc),
        )
