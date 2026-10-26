# ASTRA — Intelligent AI Personal Assistant
## Windows Automation / Action / Desktop Layer

Astra is an intelligent desktop personal assistant providing deterministic Windows automation tools, persistent configuration, voice recognition, speech synthesis, notification dispatching, structured reminder scheduling, and a modern desktop interface.

---

### Architecture Overview

```
User -> Voice / Desktop Chat UI -> AI Core / Intent Adapter -> Planner -> Action Layer -> Windows OS
                                                ↓                        ↑
                                  Reminders & Notifications        TTS & Voice Services
```

---

### Repository Structure

```
Astra/
│
├── actions/                  # 34 Deterministic Windows Automation Tools
│   ├── app_actions.py        # Application Manager (4 tools)
│   ├── file_actions.py       # File & Folder Manager (7 tools)
│   ├── system_actions.py     # System Diagnostics & Controls (18 tools)
│   ├── web_actions.py        # Web Actions & Search (5 tools)
│   └── registry.py           # Tool Registry & Schema Discovery
│
├── voice/                    # Speech-to-Text Input Service
│   ├── devices.py            # Microphone enumeration
│   ├── exceptions.py         # VoiceError hierarchy
│   └── listener.py           # SpeechListener (listen() -> str)
│
├── tts/                      # Text-to-Speech Output Service
│   ├── exceptions.py         # TTSError hierarchy
│   └── synthesizer.py        # SpeechSynthesizer (speak(text), enumerate_voices())
│
├── notifications/            # Windows Desktop Notifications
│   ├── exceptions.py         # NotificationError hierarchy
│   └── service.py            # NotificationService (Windows toast notifications)
│
├── reminders/                # Task Scheduling & Persistence
│   ├── models.py             # Reminder dataclass model
│   ├── storage.py            # Atomic JSON persistence
│   ├── service.py            # ReminderService (schedule, cancel, list, triggers)
│   └── coordinator.py        # Reminder + Notification orchestrator
│
├── ui/                       # Desktop User Interface (PySide6)
│   ├── assistant_interface.py# UI-to-AI Core contract
│   ├── ai_adapter.py         # AI Core adapter & ActionResult mapper
│   ├── main_window.py        # Desktop chat UI, sidebar, bubbles, settings dialog
│   ├── settings.py           # Persistent configuration (JSON store)
│   └── logger.py             # Structured application logger
│
├── tests/                    # 162 Automated Unit & Integration Tests
│   ├── test_foundation.py
│   ├── test_app_actions.py
│   ├── test_file_actions.py
│   ├── test_system_actions.py
│   ├── test_web_actions.py
│   ├── test_registry.py
│   ├── test_settings.py
│   ├── test_settings_ui.py
│   ├── test_voice.py
│   ├── test_tts.py
│   ├── test_notifications.py
│   ├── test_reminders.py
│   ├── test_ai_adapter.py
│   ├── test_voice_flow.py
│   ├── test_notification_flow.py
│   └── test_hardening.py
│
├── app.py                    # Application Entry Point
├── requirements.txt          # Python Dependencies
├── .gitignore
└── README.md
```

---

### Setup & Running

#### 1. Install Dependencies
```powershell
pip install -r requirements.txt
```

#### 2. Run Test Suite (162 Passing Tests)
```powershell
python -m unittest discover -s tests -v
```

#### 3. Run the Desktop UI
```powershell
python app.py
```

The desktop UI features:
- **Sidebar** with conversation history, search, new-chat, settings, and help
- **Session management** — sessions are auto-titled from the first user message and can be restored
- **Chat bubbles** — user (right-aligned) and Astra (left-aligned) with avatars and timestamps
- **Welcome panel** with quick-start suggestion chips
- **Collapsible sidebar** via the ◧ button
- **Settings dialog** with appearance, voice, speech speed, startup, and notification controls

---

### Integration Guide

For full integration details and schemas, see:
👉 **[docs/member1_integration.md](docs/member1_integration.md)**
