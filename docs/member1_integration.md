# ASTRA — Intelligent AI Personal Assistant
## Member 1: Windows Automation / Action / Tool Layer — Integration Contract

**Document Version:** 1.0.0  
**Author:** Member 1 (Windows Automation Engineer)  
**Target Audience:** Project Lead, AI Core Developer, Orchestration/Planner Engineer  

---

## 1. Executive Summary & Architectural Scope

This document defines the formal integration contract between **ASTRA's AI Core** and **Member 1's Action / Tool Layer**. 

### Division of Responsibilities

```
                                USER
                                 ↓
                     Voice / Text / Chat UI
                                 ↓
               ASTRA AI Core / LLM Reasoning Engine
          (Intent Recognition, Memory, Context, Planner)
                                 ↓
═══════════════════════════════════════════════════════════════
        MEMBER 1 BOUNDARY (Windows Automation Layer)
═══════════════════════════════════════════════════════════════
                                 ↓
                        Action Registry
                                 ↓
                       Parameter Validation
                                 ↓
                   Explicit Registered Action
                                 ↓
               Windows OS / Subprocesses / Filesystem
                                 ↓
                       Standardized ActionResult
═══════════════════════════════════════════════════════════════
                                 ↓
                          AI Core Explains
                                 ↓
                            Final Output
```

### What Member 1 Provides
- **Deterministic Python Tools**: 34 tested, isolated automation functions.
- **Strict Data Envelope (`ActionResult`)**: Every tool call returns consistent structured data, never unformatted prose or raw exceptions.
- **Central Action Registry**: A single discovery and invocation gateway (`actions.registry.execute_action`).
- **Hardware & OS Safety Guards**: Non-destructive file operations, protected system process blacklists, and explicit confirmation guards for disruptive system controls.

### What Member 1 Does NOT Provide
- **Zero AI / Intent Recognition**: Does not decide what the user wants or parse natural language.
- **Zero Prompts / LLM Orchestration**: Does not connect to Ollama, OpenAI, Qwen, or any model.
- **Zero GUI / Voice**: PySide6 UI, microphone STT, TTS, and chat windows are handled by other team members.
- **Zero Memory / Reminders**: Conversation state, context databases, and reminders belong to other project modules.

---

## 2. Standardized Result Envelope: `ActionResult`

All 34 tools return an instance of `ActionResult` (defined in `actions.base`). Callers can access fields both as attributes (`result.success`) and as dictionary keys (`result["success"]`), or serialize with `.to_dict()`.

### Envelope Schema
```python
@dataclass(frozen=True)
class ActionResult(Mapping[str, Any]):
    success: bool            # True if operation succeeded, False otherwise
    message: str            # Concise human/machine readable summary
    data: Any = None        # Structured dictionary containing returned values
    error: Optional[str] = None  # Machine-readable error code if success is False
```

### Success Payload Example
```json
{
  "success": true,
  "message": "Application 'chrome' opened successfully.",
  "data": {
    "name": "chrome",
    "path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "pid": 14208
  },
  "error": null
}
```

### Failure Payload Example
```json
{
  "success": false,
  "message": "Application 'ghost_app' could not be found.",
  "data": null,
  "error": "ApplicationNotFound"
}
```

---

## 3. Action Registry API

The central registry lives in `actions.registry`. The AI Core developer only needs to import `execute_action`, `list_actions`, or `get_action_metadata`.

### 3.1 `list_actions() -> list[dict]`
Returns a deterministic, sorted list of schemas for all 34 registered tools. Use this to construct function-calling / tool-use prompts for the LLM.

```python
from actions.registry import list_actions

tools = list_actions()
print(f"Discovered {len(tools)} tools.")
# tools[0] -> {"name": "close_application", "description": "...", "parameters": {...}, ...}
```

### 3.2 `get_action_metadata(name: str) -> Optional[dict]`
Retrieves schema and parameter requirements for a single action.

```python
from actions.registry import get_action_metadata

meta = get_action_metadata("open_application")
# meta -> {"name": "open_application", "parameters": {"name": {"type": "string", "required": True}}, ...}
```

### 3.3 `execute_action(name: str, parameters: Optional[dict] = None) -> ActionResult`
Validates parameters, checks required types, and executes the target action safely without `eval()`, `exec()`, or arbitrary shell calls.

```python
from actions.registry import execute_action

# Safe invocation
result = execute_action("open_application", {"name": "notepad"})
if result.success:
    print(f"Launched PID: {result.data['pid']}")
else:
    print(f"Failed: {result.error} - {result.message}")
```

---

## 4. Confirmation Model for Dangerous Operations

Three actions are flagged with `"requires_confirmation": True`:
1. `sleep_pc`
2. `restart_pc`
3. `shutdown_pc`

All other 31 actions have `"requires_confirmation": False`.

### How Confirmation Works
- The registry defaults `confirmed = False`.
- If `confirmed=False` (or omitted), the function aborts immediately and returns `error="ConfirmationRequired"`.
- The machine is **never** shut down or restarted without `confirmed=True`.

### Conversational Flow in the AI Core
```
User: "Turn off my computer."
   ↓
AI Core discovers "shutdown_pc" has requires_confirmation = true.
   ↓
AI Core responds: "Shutting down will close all active applications. Are you sure you want to proceed?"
   ↓
User: "Yes, go ahead."
   ↓
AI Core calls: execute_action("shutdown_pc", {"confirmed": True})
```

---

## 5. Comprehensive Catalog of All 34 Actions

### 5.1 Applications (4 Tools)

#### 1. `find_application`
- **Category:** `application`
- **Description:** Locate an installed Windows application executable path by name, alias, registry App Paths, or system PATH.
- **Parameters:**
  - `name` (`string`, **required**): Name, alias (e.g. `"chrome"`, `"vscode"`, `"calculator"`), or file path.
- **Returns (`data`):** `{"name": str, "path": str, "executable": str}`
- **Confirmation Required:** `False`
- **Errors:** `InvalidInput`, `ApplicationNotFound`

#### 2. `open_application`
- **Category:** `application`
- **Description:** Launch an installed Windows application asynchronously without blocking Astra.
- **Parameters:**
  - `name` (`string`, **required**): Name or alias of the application to launch.
- **Returns (`data`):** `{"name": str, "path": str, "pid": Optional[int]}`
- **Confirmation Required:** `False`
- **Errors:** `ApplicationNotFound`, `PermissionDenied`, `OSError`

#### 3. `close_application`
- **Category:** `application`
- **Description:** Safely terminate running instances of an application. Attempts graceful termination first, then forces kill after timeout.
- **Parameters:**
  - `name` (`string`, **required**): Name, alias, or executable of the process to close.
- **Returns (`data`):** `{"name": str, "terminated_pids": list[int], "count": int}`
- **Confirmation Required:** `False`
- **Safety / Errors:** Critical system processes (`explorer.exe`, `python.exe`, `svchost.exe`, etc.) are protected and return `ProtectedProcessError`. If not running, returns `ProcessNotFound`.

#### 4. `is_application_running`
- **Category:** `application`
- **Description:** Check if any instances of an application are currently active in memory.
- **Parameters:**
  - `name` (`string`, **required**): Application name or executable.
- **Returns (`data`):** `{"running": bool, "count": int, "instances": [{"pid": int, "name": str}]}`
- **Confirmation Required:** `False`
- **Errors:** `InvalidInput`

---

### 5.2 Files & Folders (7 Tools)

#### 5. `open_file`
- **Category:** `file`
- **Description:** Open an existing file with its default registered Windows application.
- **Parameters:**
  - `path` (`string`, **required**): Absolute or user-relative path to the file.
- **Returns (`data`):** `{"name": str, "path": str}`
- **Confirmation Required:** `False`
- **Errors:** `FileNotFoundError`, `IsADirectoryError`, `PermissionDenied`

#### 6. `open_folder`
- **Category:** `file`
- **Description:** Open an existing directory in Windows File Explorer.
- **Parameters:**
  - `path` (`string`, **required**): Path of the directory to open.
- **Returns (`data`):** `{"name": str, "path": str}`
- **Confirmation Required:** `False`
- **Errors:** `FileNotFoundError`, `NotADirectoryError`, `PermissionDenied`

#### 7. `search_file`
- **Category:** `file`
- **Description:** Search deterministically for files matching a name or wildcard pattern within a bounded directory.
- **Parameters:**
  - `name` (`string`, **required**): Filename or wildcard pattern (e.g. `"report.pdf"`, `"*.txt"`).
  - `location` (`string`, *optional*, default: `None`): Root search directory (defaults to current directory to prevent full drive thrashing).
  - `max_results` (`integer`, *optional*, default: `50`): Maximum results to return.
  - `max_depth` (`integer`, *optional*, default: `5`): Maximum directory traversal depth.
- **Returns (`data`):** `{"query": str, "location": str, "count": int, "files": [{"name": str, "path": str, "size": int, "modified": str}]}`
- **Confirmation Required:** `False`
- **Errors:** `FileNotFoundError`, `NotADirectoryError`, `InvalidInput`

#### 8. `create_folder`
- **Category:** `file`
- **Description:** Safely create a directory path, including any missing parent directories.
- **Parameters:**
  - `path` (`string`, **required**): Target directory path.
- **Returns (`data`):** `{"path": str, "created": bool}` (`created: false` if already existed).
- **Confirmation Required:** `False`
- **Errors:** `FileExistsError` (if path is an existing regular file), `PermissionDenied`

#### 9. `rename_file`
- **Category:** `file`
- **Description:** Safely rename a file or folder. Rejects operations that would overwrite existing files.
- **Parameters:**
  - `old_path` (`string`, **required**): Current file or folder path.
  - `new_path` (`string`, **required**): New target path.
- **Returns (`data`):** `{"old_path": str, "new_path": str, "name": str}`
- **Confirmation Required:** `False`
- **Errors:** `FileNotFoundError`, `FileExistsError` (overwrite guard), `PermissionDenied`

#### 10. `move_file`
- **Category:** `file`
- **Description:** Safely move a file or folder into a directory or new path with non-destructive overwrite guards.
- **Parameters:**
  - `source` (`string`, **required**): Source path to move.
  - `destination` (`string`, **required**): Destination folder or target path.
- **Returns (`data`):** `{"source": str, "destination": str}`
- **Confirmation Required:** `False`
- **Errors:** `FileNotFoundError`, `FileExistsError`, `InvalidMoveError` (cannot move folder into itself)

#### 11. `get_file_info`
- **Category:** `file`
- **Description:** Retrieve structured filesystem metadata for a path.
- **Parameters:**
  - `path` (`string`, **required**): Path to inspect.
- **Returns (`data`):**
  ```json
  {
    "name": "data.csv",
    "path": "C:\\Users\\...\\data.csv",
    "extension": ".csv",
    "size": 4096,
    "created_time": "2026-10-11T05:00:00+00:00",
    "modified_time": "2026-10-11T05:30:00+00:00",
    "is_file": true,
    "is_dir": false
  }
  ```
- **Confirmation Required:** `False`
- **Errors:** `FileNotFoundError`, `PermissionDenied`

---

### 5.3 System Information (8 Tools)

#### 12. `get_cpu_usage`
- **Category:** `system`
- **Description:** Retrieve CPU utilization percentage, logical/physical core counts, and frequencies.
- **Parameters:**
  - `interval` (`float`, *optional*, default: `0.1`): Sampling interval in seconds.
- **Returns (`data`):** `{"percent": float, "cores_logical": int, "cores_physical": int, "frequency_mhz": {"current": float, "min": float, "max": float}}`
- **Confirmation Required:** `False`

#### 13. `get_memory_usage`
- **Category:** `system`
- **Description:** Retrieve total, used, available RAM metrics in bytes and gigabytes.
- **Parameters:** None.
- **Returns (`data`):** `{"total_bytes": int, "available_bytes": int, "used_bytes": int, "percent": float, "total_gb": float, "used_gb": float, "available_gb": float}`
- **Confirmation Required:** `False`

#### 14. `get_disk_usage`
- **Category:** `system`
- **Description:** Retrieve total, used, and free disk capacity and percentage for a drive.
- **Parameters:**
  - `path` (`string`, *optional*, default: `"C:\\"`): Drive partition or directory.
- **Returns (`data`):** `{"path": str, "total_bytes": int, "used_bytes": int, "free_bytes": int, "percent": float, "total_gb": float, "used_gb": float, "free_gb": float}`
- **Confirmation Required:** `False`

#### 15. `get_battery_status`
- **Category:** `system`
- **Description:** Retrieve battery charge percentage and charging status. Safely indicates when no battery exists (e.g. on desktop PCs).
- **Parameters:** None.
- **Returns (`data`):** `{"has_battery": bool, "percent": Optional[float], "power_plugged": Optional[bool], "seconds_left": Optional[int]}`
- **Confirmation Required:** `False`

#### 16. `get_network_status`
- **Category:** `system`
- **Description:** Retrieve network host, local IP, network interface states, and I/O counters.
- **Parameters:** None.
- **Returns (`data`):** `{"hostname": str, "ip_address": str, "interfaces": [{"name": str, "is_up": bool, "speed_mbps": int, "ipv4_addresses": list[str]}], "bytes_sent": int, "bytes_recv": int}`
- **Confirmation Required:** `False`

#### 17. `get_os_info`
- **Category:** `system`
- **Description:** Retrieve Windows operating system name, release, build, architecture, and Python runtime version.
- **Parameters:** None.
- **Returns (`data`):** `{"system": str, "release": str, "version": str, "architecture": str, "processor": str, "hostname": str, "python_version": str}`
- **Confirmation Required:** `False`

#### 18. `get_running_processes`
- **Category:** `system`
- **Description:** Retrieve list of running processes sorted descending by memory consumption.
- **Parameters:**
  - `limit` (`integer`, *optional*, default: `50`): Maximum processes to return.
- **Returns (`data`):** `{"count": int, "total_running": int, "processes": [{"pid": int, "name": str, "status": str, "memory_percent": float}]}`
- **Confirmation Required:** `False`

#### 19. `get_system_info`
- **Category:** `system`
- **Description:** Retrieve complete aggregated diagnostics (CPU, RAM, disk, battery, network, OS) in a single call.
- **Parameters:** None.
- **Returns (`data`):** `{"os": dict, "cpu": dict, "memory": dict, "disk": dict, "battery": dict, "network": dict}`
- **Confirmation Required:** `False`

---

### 5.4 Windows Controls (10 Tools)

#### 20. `volume_up`
- **Category:** `windows`
- **Description:** Increase master audio volume using Windows multimedia key events.
- **Parameters:**
  - `steps` (`integer`, *optional*, default: `1`): Number of volume increments.
- **Returns (`data`):** `{"action": "volume_up", "steps": int}`
- **Confirmation Required:** `False`

#### 21. `volume_down`
- **Category:** `windows`
- **Description:** Decrease master audio volume using Windows multimedia key events.
- **Parameters:**
  - `steps` (`integer`, *optional*, default: `1`): Number of volume decrements.
- **Returns (`data`):** `{"action": "volume_down", "steps": int}`
- **Confirmation Required:** `False`

#### 22. `mute`
- **Category:** `windows`
- **Description:** Mute master audio.
- **Parameters:** None.
- **Returns (`data`):** `{"action": "mute"}`
- **Confirmation Required:** `False`

#### 23. `unmute`
- **Category:** `windows`
- **Description:** Unmute master audio.
- **Parameters:** None.
- **Returns (`data`):** `{"action": "unmute"}`
- **Confirmation Required:** `False`

#### 24. `toggle_mute`
- **Category:** `windows`
- **Description:** Toggle audio mute state.
- **Parameters:** None.
- **Returns (`data`):** `{"action": "toggle_mute"}`
- **Confirmation Required:** `False`

#### 25. `take_screenshot`
- **Category:** `windows`
- **Description:** Capture current desktop screen and save to disk without overwriting previous screenshots.
- **Parameters:**
  - `save_dir` (`string`, *optional*, default: `None`): Destination folder (defaults to `%USERPROFILE%\Pictures\Screenshots`).
  - `filename` (`string`, *optional*, default: `None`): Custom filename.
- **Returns (`data`):** `{"path": str, "filename": str, "width": int, "height": int, "format": "PNG"}`
- **Confirmation Required:** `False`

#### 26. `lock_pc`
- **Category:** `windows`
- **Description:** Immediately lock the Windows workstation (reversible security action).
- **Parameters:** None.
- **Returns (`data`):** `{"locked": True}`
- **Confirmation Required:** `False`

#### 27. `sleep_pc`
- **Category:** `windows`
- **Description:** Put the Windows PC to sleep.
- **Parameters:**
  - `confirmed` (`boolean`, *optional*, default: `False`): Explicit confirmation flag.
- **Returns (`data`):** `{"action": "sleep_pc", "confirmed": True}`
- **Confirmation Required:** `True`
- **Safety:** Aborts with `error="ConfirmationRequired"` unless `confirmed=True`.

#### 28. `restart_pc`
- **Category:** `windows`
- **Description:** Restart the Windows PC.
- **Parameters:**
  - `confirmed` (`boolean`, *optional*, default: `False`): Explicit confirmation flag.
- **Returns (`data`):** `{"action": "restart_pc", "confirmed": True}`
- **Confirmation Required:** `True`
- **Safety:** Aborts with `error="ConfirmationRequired"` unless `confirmed=True`.

#### 29. `shutdown_pc`
- **Category:** `windows`
- **Description:** Shut down the Windows PC.
- **Parameters:**
  - `confirmed` (`boolean`, *optional*, default: `False`): Explicit confirmation flag.
- **Returns (`data`):** `{"action": "shutdown_pc", "confirmed": True}`
- **Confirmation Required:** `True`
- **Safety:** Aborts with `error="ConfirmationRequired"` unless `confirmed=True`.

---

### 5.5 Web Actions (5 Tools)

#### 30. `open_website`
- **Category:** `web`
- **Description:** Open a validated HTTP/HTTPS URL or domain in the default browser. Normalizes bare domains (`github.com` -> `https://github.com`) and blocks dangerous schemes (`file://`, `javascript:`).
- **Parameters:**
  - `url` (`string`, **required**): Web URL or domain to open.
- **Returns (`data`):** `{"url": str, "original_input": str}`
- **Confirmation Required:** `False`
- **Errors:** `InvalidURL`, `BrowserOpenError`

#### 31. `web_search`
- **Category:** `web`
- **Description:** Perform a general web search (Google) in the default web browser.
- **Parameters:**
  - `query` (`string`, **required**): Search terms.
- **Returns (`data`):** `{"query": str, "url": str}`
- **Confirmation Required:** `False`
- **Errors:** `InvalidInput`

#### 32. `google_search`
- **Category:** `web`
- **Description:** Search Google in the default browser with URL-encoded query parameters.
- **Parameters:**
  - `query` (`string`, **required**): Search terms.
- **Returns (`data`):** `{"query": str, "url": str}`
- **Confirmation Required:** `False`
- **Errors:** `InvalidInput`

#### 33. `youtube_search`
- **Category:** `web`
- **Description:** Search YouTube videos in the default browser.
- **Parameters:**
  - `query` (`string`, **required**): Video keywords.
- **Returns (`data`):** `{"query": str, "url": str}`
- **Confirmation Required:** `False`
- **Errors:** `InvalidInput`

#### 34. `github_search`
- **Category:** `web`
- **Description:** Search GitHub repositories and code in the default browser.
- **Parameters:**
  - `query` (`string`, **required**): Search keywords.
- **Returns (`data`):** `{"query": str, "url": str}`
- **Confirmation Required:** `False`
- **Errors:** `InvalidInput`

---

## 6. End-to-End AI Integration Examples

The following code snippets demonstrate how the Project Lead / AI Core will consume the Action Registry:

### Example 1: Launch Application
```python
from actions.registry import execute_action

# User asks: "Open Google Chrome"
# AI Core planner extracts: tool="open_application", params={"name": "chrome"}
result = execute_action("open_application", {"name": "chrome"})

if result.success:
    print(f"Assistant: Chrome has been opened (PID: {result.data['pid']}).")
else:
    print(f"Assistant: I could not find or open Chrome: {result.message}")
```

### Example 2: YouTube Search
```python
from actions.registry import execute_action

# User asks: "Find tutorials for Python recursion on YouTube"
# AI Core planner extracts: tool="youtube_search", params={"query": "Python recursion tutorial"}
result = execute_action("youtube_search", {"query": "Python recursion tutorial"})

if result.success:
    print(f"Assistant: I've opened YouTube search for '{result.data['query']}'.")
```

### Example 3: System Diagnostics Query
```python
from actions.registry import execute_action

# User asks: "How much RAM is currently in use?"
# AI Core planner extracts: tool="get_memory_usage", params={}
result = execute_action("get_memory_usage", {})

if result.success:
    mem = result.data
    print(f"Assistant: Memory utilization is at {mem['percent']}% ({mem['used_gb']} GB used out of {mem['total_gb']} GB).")
```

### Example 4: Conversational Power Action
```python
from actions.registry import execute_action, get_action_metadata

# User asks: "Restart my laptop"
meta = get_action_metadata("restart_pc")

if meta["requires_confirmation"]:
    # 1. First invocation without confirmation
    pre_check = execute_action("restart_pc", {"confirmed": False})
    assert pre_check.success is False
    assert pre_check.error == "ConfirmationRequired"
    
    # 2. AI Core engages user:
    # "Restarting your computer will close all unsaved work. Would you like me to proceed?"
    user_confirmed = True  # From conversational dialog
    
    # 3. Confirmed invocation
    if user_confirmed:
        result = execute_action("restart_pc", {"confirmed": True})
        print("Assistant: Restart sequence initiated.")
```

---

## 7. Quality Assurance & Verification Results

All automated tests use mock objects for hardware, power, process termination, and browser opening, preventing disruption to the host machine.

### Test Execution Command
```powershell
py -m unittest discover -s tests -v
```

### Official Test Breakdown (101 / 101 Tests Passing)

| Test Module | Coverage Domain | Tests | Status |
| :--- | :--- | :---: | :---: |
| `tests/test_foundation.py` | `ActionResult`, Mapping protocol, logging, imports | 7 | **PASS** |
| `tests/test_app_actions.py` | App lookup, detached launch, process inspection, protected termination | 15 | **PASS** |
| `tests/test_file_actions.py` | Open file/folder, sandbox search, safe create/rename/move, metadata | 22 | **PASS** |
| `tests/test_system_actions.py` | Hardware metrics, battery detection, volume, screenshot, power guards | 30 | **PASS** |
| `tests/test_web_actions.py` | URL validation, protocol allowlisting, search query encoding | 13 | **PASS** |
| `tests/test_registry.py` | 34-tool registration, schema exports, type validation, confirmation enforcement | 14 | **PASS** |
| **TOTAL** | **Full Action Layer Test Suite** | **101** | **ALL PASS (100%)** |

---

## 8. Completion Confirmation

**Member 1's development lifecycle is complete.**
All 34 deterministic automation tools, parameter validation routines, confirmation safety guards, and integration contracts are finalized, tested, and ready for connection to ASTRA's AI Core.
