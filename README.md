# ASTRA — Intelligent AI Personal Assistant
## Windows Automation / Action / Tool Layer (Member 1)

This repository contains the Windows automation and action layer for **ASTRA**, designed to provide reliable, deterministic execution tools for the ASTRA AI Core.

---

### Architecture Overview

```
User -> Text/Voice -> AI Intent -> Planner -> Action Layer (This Module) -> Windows OS
```

This module provides deterministic Python tool functions with a standardized result contract (`ActionResult`):

```json
{
  "success": true,
  "message": "Application 'chrome' opened successfully.",
  "data": { "path": "...", "pid": 1234 },
  "error": null
}
```

---

### Repository Structure

```
Astra/
│
├── actions/
│   ├── __init__.py           # Package exports (ActionResult, execute_action, registry)
│   ├── base.py               # Standardized ActionResult envelope & error hierarchy
│   ├── app_actions.py        # Application Manager (4 tools)
│   ├── file_actions.py       # File & Folder Manager (7 tools)
│   ├── system_actions.py     # System Diagnostics & Windows Controls (18 tools)
│   ├── web_actions.py        # Web Actions & Search (5 tools)
│   └── registry.py           # Tool Registry & Schema Discovery (34 tools registered)
│
├── docs/
│   └── member1_integration.md # Complete Integration Contract for Project Lead / AI Core
│
├── tests/
│   ├── __init__.py
│   ├── test_foundation.py    # Foundation and ActionResult tests (7 tests)
│   ├── test_app_actions.py   # Application Manager tests (15 tests)
│   ├── test_file_actions.py  # File & Folder Manager tests (22 tests)
│   ├── test_system_actions.py# System Info & Windows Controls tests (30 tests)
│   ├── test_web_actions.py   # Web Actions tests (13 tests)
│   └── test_registry.py      # Action Registry & Validation tests (14 tests)
│
│
├── ui/
│   ├── __init__.py            # Desktop UI package exports
│   ├── assistant_interface.py # UI-to-AI-core response contract
│   ├── settings.py            # Persistent user settings model and store
│   └── main_window.py         # PySide6 chat window (sidebar, sessions, bubbles)
├── app.py                     # Desktop application entry point
├── requirements.txt           # Python dependencies (psutil, Pillow, PySide6)
├── .gitignore
└── README.md
```

---

### Implemented Modules & Capabilities (34 Tools Total)

1. **Application Manager (`actions/app_actions.py` - 4 Tools)**
   - `find_application`, `open_application`, `close_application`, `is_application_running`
   - Registry App Paths + PATH + common directory resolution. Detached asynchronous execution. Protected process guards.

2. **File & Folder Manager (`actions/file_actions.py` - 7 Tools)**
   - `open_file`, `open_folder`, `search_file`, `create_folder`, `rename_file`, `move_file`, `get_file_info`
   - Windows default app launch, bounded recursive search, overwrite-protected rename and move, directory self-move blocking, structured file metadata. Zero silent deletion.

3. **System Information (`actions/system_actions.py` - 8 Tools)**
   - `get_cpu_usage`, `get_memory_usage`, `get_disk_usage`, `get_battery_status`, `get_network_status`, `get_os_info`, `get_running_processes`, `get_system_info`
   - Read-only hardware & OS metrics using `psutil`, `socket`, and `platform`. Graceful battery fallback for desktop PCs.

4. **Windows Controls (`actions/system_actions.py` - 10 Tools)**
   - `volume_up`, `volume_down`, `mute`, `unmute`, `toggle_mute`, `take_screenshot`, `lock_pc`, `sleep_pc`, `restart_pc`, `shutdown_pc`
   - Direct Windows multimedia key events (`user32.keybd_event`). Timestamped collision-resistant screenshots (`Pillow`). Workstation lock (`user32.LockWorkStation`). Confirmation-guarded power controls (`sleep_pc`, `restart_pc`, `shutdown_pc` require `confirmed=True`).

5. **Web Actions (`actions/web_actions.py` - 5 Tools)**
   - `open_website`, `web_search`, `google_search`, `youtube_search`, `github_search`
   - Default browser integration (`webbrowser`). URL scheme allowlisting (`http`/`https` only; blocks `file://`, `javascript:`). Safe URL encoding (`urllib.parse.quote_plus`).

6. **Action & Tool Registry (`actions/registry.py` - 34 Tools Registered)**
   - Central discovery, metadata serialization (`list_actions`, `get_action_metadata`), lightweight parameter validation, confirmation checking, and execution dispatching (`execute_action`).

---

### Integration Guide

For full integration details, parameter schemas, confirmation handling, and AI Core code examples, refer to:
👉 **[docs/member1_integration.md](docs/member1_integration.md)**

```python
from actions.registry import execute_action, list_actions

# Discover available tools
tools = list_actions()

# Execute an action
result = execute_action("open_application", {"name": "chrome"})
if result.success:
    print(result.message)  # "Application 'chrome' opened successfully."
    print(result.data)     # {"name": "chrome", "path": "...", "pid": 1234}
```

---

### Setup & Testing

#### 1. Install Dependencies
```powershell
pip install -r requirements.txt
```

#### 2. Run Test Suite (101 Tests Passing)
```powershell
py -m unittest discover -s tests -v
```

#### 3. Run the desktop UI
```powershell
py app.py
```

The desktop UI features:
- **Sidebar** with conversation history, search, new-chat, settings, and help
- **Session management** — sessions are auto-titled from the first user message and can be restored
- **Chat bubbles** — user (right-aligned) and Astra (left-aligned) with avatars and timestamps
- **Welcome panel** with quick-start suggestion chips
- **Collapsible sidebar** via the ◧ button
- **Settings dialog** with voice, speech speed, appearance, notification, and startup controls

> The current UI uses a temporary echo assistant until the project lead integrates
> the AI core through `AssistantInterface.process(user_text)`.

Settings are stored per user under `%LOCALAPPDATA%\\Astra\\settings.json` on
Windows. Voice device choices remain integration values until the voice services
are implemented.
