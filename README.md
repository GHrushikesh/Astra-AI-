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
│   ├── __init__.py           # Package exports (ActionResult, errors, logger)
│   ├── base.py               # Standardized ActionResult envelope & error hierarchy
│   ├── app_actions.py        # Application Manager (open, close, status, find)
│   ├── file_actions.py       # File & Folder Manager (Milestone 3)
│   ├── system_actions.py     # System Diagnostics & Windows Controls (Milestones 4-5)
│   ├── web_actions.py        # Web Actions & Search (Milestone 6)
│   └── registry.py           # Tool Registry & Schema Discovery (Milestone 7)
│
├── tests/
│   ├── __init__.py
│   ├── test_foundation.py    # Foundation and ActionResult tests
│   └── test_app_actions.py   # Application Manager tests
│
├── requirements.txt          # Python dependencies (psutil, Pillow)
└── .gitignore
```

---

### Implemented Modules

#### Milestone 1: Foundation
- `ActionResult`: Standardized return envelope implementing the Python mapping protocol (both attribute access `res.success` and dictionary access `res["success"]`).
- `ActionError` & `ActionConfirmationRequired`: Structured exception hierarchy.
- Logging with `NullHandler` allowing seamless integration with the host application.

#### Milestone 2: Application Manager (`actions/app_actions.py`)
- `find_application(name)`: Deterministically locates executables using direct paths, system PATH, Windows Registry `App Paths`, and common program directories.
- `open_application(name)`: Asynchronously launches applications detached from the host process.
- `is_application_running(name)`: Inspects active processes using case-insensitive exact matching.
- `close_application(name)`: Safely terminates running processes with graceful termination first, protected process safeguards (`PROTECTED_PROCESSES`), and permission handling.

---

### Setup & Testing

#### 1. Install Dependencies
```powershell
pip install -r requirements.txt
```

#### 2. Run Test Suite
```powershell
py -m unittest discover -s tests -v
```
