"""System information and Windows control actions for Astra.

Functions (System Information - Milestone 4):
- get_cpu_usage()
- get_memory_usage()
- get_disk_usage(path="C:\\")
- get_battery_status()
- get_network_status()
- get_os_info()
- get_running_processes(limit=50)
- get_system_info()

Functions (Windows Controls - Milestone 5):
- volume_up()
- volume_down()
- mute()
- unmute()
- toggle_mute()
- take_screenshot(save_dir=None)
- lock_pc()
- sleep_pc(confirmed=False)
- restart_pc(confirmed=False)
- shutdown_pc(confirmed=False)
"""

from typing import Optional
from actions.base import ActionResult

__all__ = [
    # System Info
    "get_cpu_usage",
    "get_memory_usage",
    "get_disk_usage",
    "get_battery_status",
    "get_network_status",
    "get_os_info",
    "get_running_processes",
    "get_system_info",
    # Windows Controls
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


# System Information stubs
def get_cpu_usage() -> ActionResult:
    raise NotImplementedError("Scheduled for Milestone 4")


def get_memory_usage() -> ActionResult:
    raise NotImplementedError("Scheduled for Milestone 4")


def get_disk_usage(path: str = "C:\\") -> ActionResult:
    raise NotImplementedError("Scheduled for Milestone 4")


def get_battery_status() -> ActionResult:
    raise NotImplementedError("Scheduled for Milestone 4")


def get_network_status() -> ActionResult:
    raise NotImplementedError("Scheduled for Milestone 4")


def get_os_info() -> ActionResult:
    raise NotImplementedError("Scheduled for Milestone 4")


def get_running_processes(limit: int = 50) -> ActionResult:
    raise NotImplementedError("Scheduled for Milestone 4")


def get_system_info() -> ActionResult:
    raise NotImplementedError("Scheduled for Milestone 4")


# Windows Controls stubs
def volume_up() -> ActionResult:
    raise NotImplementedError("Scheduled for Milestone 5")


def volume_down() -> ActionResult:
    raise NotImplementedError("Scheduled for Milestone 5")


def mute() -> ActionResult:
    raise NotImplementedError("Scheduled for Milestone 5")


def unmute() -> ActionResult:
    raise NotImplementedError("Scheduled for Milestone 5")


def toggle_mute() -> ActionResult:
    raise NotImplementedError("Scheduled for Milestone 5")


def take_screenshot(save_dir: Optional[str] = None) -> ActionResult:
    raise NotImplementedError("Scheduled for Milestone 5")


def lock_pc() -> ActionResult:
    raise NotImplementedError("Scheduled for Milestone 5")


def sleep_pc(confirmed: bool = False) -> ActionResult:
    raise NotImplementedError("Scheduled for Milestone 5")


def restart_pc(confirmed: bool = False) -> ActionResult:
    raise NotImplementedError("Scheduled for Milestone 5")


def shutdown_pc(confirmed: bool = False) -> ActionResult:
    raise NotImplementedError("Scheduled for Milestone 5")
