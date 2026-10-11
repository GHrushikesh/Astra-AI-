"""Action and Tool Registry for Astra AI Core discovery and execution.

Provides central deterministic action discovery, metadata inspection,
lightweight parameter validation, and safe tool invocation.

Contains Member 1's 34 deterministic Windows automation actions across:
- Applications (4)
- Files & Folders (7)
- System Information (8)
- Windows Controls (10)
- Web (5)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Type

from actions.app_actions import (
    close_application,
    find_application,
    is_application_running,
    open_application,
)
from actions.base import ActionResult, get_logger
from actions.file_actions import (
    create_folder,
    get_file_info,
    move_file,
    open_file,
    open_folder,
    rename_file,
    search_file,
)
from actions.system_actions import (
    get_battery_status,
    get_cpu_usage,
    get_disk_usage,
    get_memory_usage,
    get_network_status,
    get_os_info,
    get_running_processes,
    get_system_info,
    lock_pc,
    mute,
    restart_pc,
    shutdown_pc,
    sleep_pc,
    take_screenshot,
    toggle_mute,
    unmute,
    volume_down,
    volume_up,
)
from actions.web_actions import (
    github_search,
    google_search,
    open_website,
    web_search,
    youtube_search,
)

logger = get_logger("astra.actions.registry")

# Set of actions that MUST require explicit confirmation
CONFIRMATION_REQUIRED_ACTIONS: Set[str] = {
    "sleep_pc",
    "restart_pc",
    "shutdown_pc",
}


@dataclass(frozen=True)
class ParameterDefinition:
    """Specification of a tool parameter."""
    type: str  # "string", "integer", "float", "boolean"
    python_type: Type  # str, int, float, bool
    required: bool = True
    default: Any = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert parameter specification to JSON/AI schema dict."""
        return {
            "type": self.type,
            "required": self.required,
            "default": self.default,
            "description": self.description,
        }


@dataclass
class ToolMetadata:
    """Metadata describing an action tool for AI discovery and planning."""
    name: str
    description: str
    category: str
    parameters: Dict[str, ParameterDefinition]
    function: Callable[..., ActionResult]
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary excluding the callable function."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": {
                p_name: p_def.to_dict()
                for p_name, p_def in self.parameters.items()
            },
            "requires_confirmation": self.requires_confirmation,
        }


class ActionRegistry:
    """Central registry exposing Member 1's automation tools to Astra AI Core."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolMetadata] = {}

    def register(
        self,
        name: str,
        description: str,
        category: str,
        parameters: Dict[str, ParameterDefinition],
        function: Callable[..., ActionResult],
        requires_confirmation: Optional[bool] = None,
    ) -> None:
        """Register an action tool."""
        needs_confirm = (
            requires_confirmation
            if requires_confirmation is not None
            else (name in CONFIRMATION_REQUIRED_ACTIONS)
        )
        metadata = ToolMetadata(
            name=name,
            description=description,
            category=category,
            parameters=parameters,
            function=function,
            requires_confirmation=needs_confirm,
        )
        self._tools[name] = metadata
        logger.debug("Registered tool '%s' (%s)", name, category)

    def get_tool(self, name: str) -> Optional[ToolMetadata]:
        """Retrieve tool metadata object by name."""
        return self._tools.get(name)

    def get_action_metadata(self, name: str) -> Optional[dict[str, Any]]:
        """Retrieve serialized action metadata dictionary by name."""
        tool = self._tools.get(name)
        return tool.to_dict() if tool else None

    def list_actions(self) -> List[dict[str, Any]]:
        """Return a deterministic, sorted list of all registered tool descriptions."""
        return [self._tools[k].to_dict() for k in sorted(self._tools.keys())]

    def _validate_parameters(
        self, tool: ToolMetadata, raw_params: Optional[Dict[str, Any]]
    ) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Validate passed parameters against tool parameter specifications."""
        params = raw_params if raw_params is not None else {}
        if not isinstance(params, dict):
            return None, "Parameters must be provided as a dictionary."

        # 1. Check for unexpected parameters
        for p_name in params:
            if p_name not in tool.parameters:
                return None, f"Unexpected parameter '{p_name}' for action '{tool.name}'."

        validated: Dict[str, Any] = {}

        # 2. Check required parameters and default values
        for p_name, p_def in tool.parameters.items():
            if p_name in params:
                val = params[p_name]
                # Allow None for optional parameters with default None
                if val is None and not p_def.required and p_def.default is None:
                    validated[p_name] = None
                    continue

                # Type checking (safeguard: bool is subclass of int in Python)
                if p_def.python_type is bool:
                    if not isinstance(val, bool):
                        return None, f"Parameter '{p_name}' expected boolean, got {type(val).__name__}."
                elif p_def.python_type is int:
                    if isinstance(val, bool) or not isinstance(val, int):
                        return None, f"Parameter '{p_name}' expected integer, got {type(val).__name__}."
                elif p_def.python_type is float:
                    if isinstance(val, bool) or not isinstance(val, (float, int)):
                        return None, f"Parameter '{p_name}' expected float, got {type(val).__name__}."
                    val = float(val)
                elif p_def.python_type is str:
                    if not isinstance(val, str):
                        return None, f"Parameter '{p_name}' expected string, got {type(val).__name__}."
                validated[p_name] = val
            else:
                if p_def.required:
                    return None, f"Missing required parameter '{p_name}' for action '{tool.name}'."
                validated[p_name] = p_def.default

        return validated, None

    def execute_action(
        self, name: str, parameters: Optional[Dict[str, Any]] = None
    ) -> ActionResult:
        """Execute a registered action with validated parameters.

        Args:
            name: Exact registered action name.
            parameters: Optional parameter dictionary.

        Returns:
            ActionResult indicating execution outcome.
        """
        tool = self._tools.get(name)
        if not tool:
            logger.warning("Attempted to execute unregistered action '%s'", name)
            return ActionResult.fail(
                message=f"Action '{name}' is not registered.",
                error="ActionNotFound",
            )

        validated_params, error_msg = self._validate_parameters(tool, parameters)
        if validated_params is None:
            logger.warning("Validation failed for action '%s': %s", name, error_msg)
            return ActionResult.fail(
                message=f"Validation error for action '{name}': {error_msg}",
                error="ValidationError",
            )

        try:
            logger.info("Executing action '%s' with parameters %s", name, validated_params)
            return tool.function(**validated_params)
        except Exception as exc:
            logger.error("Exception during action '%s' execution: %s", name, exc)
            return ActionResult.fail(
                message=f"Error executing action '{name}': {exc}",
                error=str(exc),
            )

    # Alias for backwards compatibility
    def execute(self, name: str, **kwargs: Any) -> ActionResult:
        """Convenience method accepting keyword arguments."""
        return self.execute_action(name, parameters=kwargs if kwargs else None)


# ------------------------------------------------------------------------------
# GLOBAL REGISTRY & TOOL REGISTRATIONS
# ------------------------------------------------------------------------------

registry = ActionRegistry()


def _register_all_tools(reg: ActionRegistry) -> None:
    """Populate the registry with Member 1's 34 deterministic automation tools."""

    # --------------------------------------------------------------------------
    # 1. APPLICATION MANAGER (4)
    # --------------------------------------------------------------------------
    reg.register(
        name="find_application",
        description="Locate an installed Windows application executable path by name or alias.",
        category="application",
        parameters={
            "name": ParameterDefinition("string", str, required=True, description="Application name or alias"),
        },
        function=find_application,
    )
    reg.register(
        name="open_application",
        description="Launch an installed Windows application asynchronously.",
        category="application",
        parameters={
            "name": ParameterDefinition("string", str, required=True, description="Application name or alias to launch"),
        },
        function=open_application,
    )
    reg.register(
        name="close_application",
        description="Safely terminate active instances of an application.",
        category="application",
        parameters={
            "name": ParameterDefinition("string", str, required=True, description="Application name or executable to close"),
        },
        function=close_application,
    )
    reg.register(
        name="is_application_running",
        description="Check if an application is currently running.",
        category="application",
        parameters={
            "name": ParameterDefinition("string", str, required=True, description="Application name or executable to check"),
        },
        function=is_application_running,
    )

    # --------------------------------------------------------------------------
    # 2. FILE & FOLDER MANAGER (7)
    # --------------------------------------------------------------------------
    reg.register(
        name="open_file",
        description="Open an existing file with its Windows default application.",
        category="file",
        parameters={
            "path": ParameterDefinition("string", str, required=True, description="Path of the file to open"),
        },
        function=open_file,
    )
    reg.register(
        name="open_folder",
        description="Open an existing folder in Windows File Explorer.",
        category="file",
        parameters={
            "path": ParameterDefinition("string", str, required=True, description="Path of the folder to open"),
        },
        function=open_folder,
    )
    reg.register(
        name="search_file",
        description="Search deterministically for a filename or wildcard pattern in a directory.",
        category="file",
        parameters={
            "name": ParameterDefinition("string", str, required=True, description="Filename or pattern (e.g. *.txt)"),
            "location": ParameterDefinition("string", str, required=False, default=None, description="Starting search directory"),
            "max_results": ParameterDefinition("integer", int, required=False, default=50, description="Maximum results to return"),
            "max_depth": ParameterDefinition("integer", int, required=False, default=5, description="Maximum directory traversal depth"),
        },
        function=search_file,
    )
    reg.register(
        name="create_folder",
        description="Safely create a folder, including parent directories.",
        category="file",
        parameters={
            "path": ParameterDefinition("string", str, required=True, description="Path of the folder to create"),
        },
        function=create_folder,
    )
    reg.register(
        name="rename_file",
        description="Safely rename a file or folder with overwrite protection.",
        category="file",
        parameters={
            "old_path": ParameterDefinition("string", str, required=True, description="Current file or folder path"),
            "new_path": ParameterDefinition("string", str, required=True, description="New file or folder path"),
        },
        function=rename_file,
    )
    reg.register(
        name="move_file",
        description="Safely move a file or folder with overwrite protection.",
        category="file",
        parameters={
            "source": ParameterDefinition("string", str, required=True, description="Source path"),
            "destination": ParameterDefinition("string", str, required=True, description="Destination path"),
        },
        function=move_file,
    )
    reg.register(
        name="get_file_info",
        description="Retrieve structured metadata (size, created, modified) for a path.",
        category="file",
        parameters={
            "path": ParameterDefinition("string", str, required=True, description="Path of the file or folder"),
        },
        function=get_file_info,
    )

    # --------------------------------------------------------------------------
    # 3. SYSTEM INFORMATION (8)
    # --------------------------------------------------------------------------
    reg.register(
        name="get_cpu_usage",
        description="Retrieve CPU usage percentage, core counts, and frequency.",
        category="system",
        parameters={
            "interval": ParameterDefinition("float", float, required=False, default=0.1, description="Sampling interval in seconds"),
        },
        function=get_cpu_usage,
    )
    reg.register(
        name="get_memory_usage",
        description="Retrieve total, used, and available RAM metrics.",
        category="system",
        parameters={},
        function=get_memory_usage,
    )
    reg.register(
        name="get_disk_usage",
        description="Retrieve total, used, and free disk space for a drive.",
        category="system",
        parameters={
            "path": ParameterDefinition("string", str, required=False, default="C:\\", description="Drive root or directory to inspect"),
        },
        function=get_disk_usage,
    )
    reg.register(
        name="get_battery_status",
        description="Retrieve battery percentage and charging status safely.",
        category="system",
        parameters={},
        function=get_battery_status,
    )
    reg.register(
        name="get_network_status",
        description="Retrieve network host, IP, and adapter interface metrics.",
        category="system",
        parameters={},
        function=get_network_status,
    )
    reg.register(
        name="get_os_info",
        description="Retrieve Windows version, build, and machine architecture.",
        category="system",
        parameters={},
        function=get_os_info,
    )
    reg.register(
        name="get_running_processes",
        description="Retrieve list of active processes sorted by memory consumption.",
        category="system",
        parameters={
            "limit": ParameterDefinition("integer", int, required=False, default=50, description="Maximum processes to return"),
        },
        function=get_running_processes,
    )
    reg.register(
        name="get_system_info",
        description="Retrieve aggregated system diagnostics (CPU, RAM, disk, battery, network, OS).",
        category="system",
        parameters={},
        function=get_system_info,
    )

    # --------------------------------------------------------------------------
    # 4. WINDOWS CONTROLS (10)
    # --------------------------------------------------------------------------
    reg.register(
        name="volume_up",
        description="Increase system audio volume.",
        category="windows",
        parameters={
            "steps": ParameterDefinition("integer", int, required=False, default=1, description="Volume increments"),
        },
        function=volume_up,
    )
    reg.register(
        name="volume_down",
        description="Decrease system audio volume.",
        category="windows",
        parameters={
            "steps": ParameterDefinition("integer", int, required=False, default=1, description="Volume decrements"),
        },
        function=volume_down,
    )
    reg.register(
        name="mute",
        description="Mute system audio.",
        category="windows",
        parameters={},
        function=mute,
    )
    reg.register(
        name="unmute",
        description="Unmute system audio.",
        category="windows",
        parameters={},
        function=unmute,
    )
    reg.register(
        name="toggle_mute",
        description="Toggle system audio mute state.",
        category="windows",
        parameters={},
        function=toggle_mute,
    )
    reg.register(
        name="take_screenshot",
        description="Capture the screen and save to a file without overwriting.",
        category="windows",
        parameters={
            "save_dir": ParameterDefinition("string", str, required=False, default=None, description="Destination directory"),
            "filename": ParameterDefinition("string", str, required=False, default=None, description="Custom filename"),
        },
        function=take_screenshot,
    )
    reg.register(
        name="lock_pc",
        description="Lock the Windows workstation immediately.",
        category="windows",
        parameters={},
        function=lock_pc,
    )
    reg.register(
        name="sleep_pc",
        description="Put the Windows PC to sleep (requires confirmed=True).",
        category="windows",
        parameters={
            "confirmed": ParameterDefinition("boolean", bool, required=False, default=False, description="Explicit confirmation flag"),
        },
        function=sleep_pc,
        requires_confirmation=True,
    )
    reg.register(
        name="restart_pc",
        description="Restart the Windows PC (requires confirmed=True).",
        category="windows",
        parameters={
            "confirmed": ParameterDefinition("boolean", bool, required=False, default=False, description="Explicit confirmation flag"),
        },
        function=restart_pc,
        requires_confirmation=True,
    )
    reg.register(
        name="shutdown_pc",
        description="Shut down the Windows PC (requires confirmed=True).",
        category="windows",
        parameters={
            "confirmed": ParameterDefinition("boolean", bool, required=False, default=False, description="Explicit confirmation flag"),
        },
        function=shutdown_pc,
        requires_confirmation=True,
    )

    # --------------------------------------------------------------------------
    # 5. WEB ACTIONS (5)
    # --------------------------------------------------------------------------
    reg.register(
        name="open_website",
        description="Open a validated HTTP/HTTPS URL or domain in the default web browser.",
        category="web",
        parameters={
            "url": ParameterDefinition("string", str, required=True, description="Web URL or domain to open"),
        },
        function=open_website,
    )
    reg.register(
        name="web_search",
        description="Perform a general web search in the default web browser.",
        category="web",
        parameters={
            "query": ParameterDefinition("string", str, required=True, description="Search query keywords"),
        },
        function=web_search,
    )
    reg.register(
        name="google_search",
        description="Search Google in the default web browser.",
        category="web",
        parameters={
            "query": ParameterDefinition("string", str, required=True, description="Google search keywords"),
        },
        function=google_search,
    )
    reg.register(
        name="youtube_search",
        description="Search YouTube videos in the default web browser.",
        category="web",
        parameters={
            "query": ParameterDefinition("string", str, required=True, description="YouTube search keywords"),
        },
        function=youtube_search,
    )
    reg.register(
        name="github_search",
        description="Search GitHub repositories and code in the default web browser.",
        category="web",
        parameters={
            "query": ParameterDefinition("string", str, required=True, description="GitHub search keywords"),
        },
        function=github_search,
    )


# Automatically populate the default singleton registry instance
_register_all_tools(registry)


# ------------------------------------------------------------------------------
# CONVENIENCE MODULE FUNCTIONS
# ------------------------------------------------------------------------------

def execute_action(
    name: str, parameters: Optional[Dict[str, Any]] = None
) -> ActionResult:
    """Execute a registered action via the central registry."""
    return registry.execute_action(name, parameters)


def get_action(name: str) -> Optional[ToolMetadata]:
    """Retrieve metadata object for an action."""
    return registry.get_tool(name)


def get_action_metadata(name: str) -> Optional[dict[str, Any]]:
    """Retrieve serialized metadata dictionary for an action."""
    return registry.get_action_metadata(name)


def list_actions() -> List[dict[str, Any]]:
    """List all registered actions in deterministic sorted order."""
    return registry.list_actions()
