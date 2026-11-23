"""Astra AI Core Engine.

Implements AssistantInterface connecting LLM intelligence, conversation memory,
and tool execution through Astra's Action Registry.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from actions.base import ActionResult, get_logger
from actions.file_actions import _resolve_safe_path
from actions.registry import execute_action
from ai.client import LLMClient, LLMError
from ai.prompts import build_system_prompt
from ui.assistant_interface import AssistantInterface, AssistantResponse
from ui.settings import AstraSettings, SettingsStore

logger = get_logger("astra.ai.core")


class AstraAICore(AssistantInterface):
    """Main AI assistant brain for Astra.

    Integrates LLM reasoning with Astra's 34 deterministic automation tools,
    persistent conversation memory, and safe confirmation dialogs.
    """

    def __init__(
        self,
        settings_store: Optional[SettingsStore] = None,
        settings: Optional[AstraSettings] = None,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        self._settings_store = settings_store or SettingsStore()
        if settings is not None:
            self._settings = settings
        else:
            try:
                self._settings = self._settings_store.load()
            except Exception:
                self._settings = AstraSettings()

        self.client = llm_client or self._create_client_from_settings(self._settings)
        self.system_prompt = build_system_prompt()
        self.history: List[Dict[str, str]] = []
        self._pending_confirmation: Optional[str] = None

    def _create_client_from_settings(self, settings: AstraSettings) -> LLMClient:
        """Instantiate an LLMClient based on current settings."""
        provider = getattr(settings, "llm_provider", "Google Gemini")
        api_key = getattr(settings, "llm_api_key", "")
        model = getattr(settings, "llm_model", "")
        endpoint = getattr(settings, "llm_endpoint", "")
        return LLMClient(
            provider=provider,
            api_key=api_key,
            model=model,
            endpoint=endpoint,
        )

    def update_settings(self, settings: AstraSettings) -> None:
        """Update active settings and recreate the LLM client."""
        self._settings = settings
        self.client = self._create_client_from_settings(settings)
        logger.info("Updated Astra AI Core settings: provider=%s, model=%s", self.client.provider, self.client.model)

    def clear_history(self) -> None:
        """Clear conversation turn history."""
        self.history.clear()
        self._pending_confirmation = None

    def process(self, user_text: str) -> AssistantResponse:
        """Process a user query or command and return an AssistantResponse."""
        clean = (user_text or "").strip()
        if not clean:
            return AssistantResponse(
                text="Please provide a message or command.",
                success=True,
            )

        # 1. Handle pending confirmation (for shutdown, restart, sleep)
        if self._pending_confirmation:
            action = self._pending_confirmation
            self._pending_confirmation = None
            if clean.lower() in {"yes", "y", "confirm", "proceed", "ok", "do it", "sure"}:
                res = execute_action(action, {"confirmed": True})
                return AssistantResponse(text=res.message, success=res.success, error=res.error)
            else:
                return AssistantResponse(
                    text=f"Action '{action}' was cancelled.",
                    success=True,
                )

        # Check direct command first for instant deterministic response
        direct_res = self._try_direct_command(clean)
        if direct_res:
            return direct_res

        # 2. Check if API key is configured
        if not self.client.has_api_key():
            return AssistantResponse(
                text=(
                    f"**Welcome to Astra**\n\n"
                    f"To enable AI intelligence, please open **Settings** (in the sidebar) "
                    f"and enter your **Google Gemini API Key**.\n\n"
                    f"*Tip: You can also use direct commands right now, like:*\n"
                    f"- `create folder E:\\Study\\test`\n"
                    f"- `open folder E:\\Study`\n"
                    f"- `open chrome` or `open notepad`\n"
                    f"- `volume up` or `mute`\n"
                    f"- `take screenshot`\n"
                    f"- `cpu usage` or `battery`\n"
                    f"- `search google for python`"
                ),
                success=True,
            )

        # 3. Call LLM
        try:
            raw_response = self.client.generate(
                prompt=clean,
                system_instruction=self.system_prompt,
                history=self.history[-10:],  # keep last 10 turns
            )
        except LLMError as exc:
            logger.warning("LLM generation failed, checking direct command fallback: %s", exc)
            fallback_res = self._try_direct_command(clean)
            if fallback_res:
                return fallback_res
            return AssistantResponse(
                text=f"AI connection error: {exc}",
                success=False,
                error=str(exc),
            )
        except Exception as exc:
            logger.error("Unexpected error during LLM generation: %s", exc)
            fallback_res = self._try_direct_command(clean)
            if fallback_res:
                return fallback_res
            return AssistantResponse(
                text=f"An unexpected error occurred: {exc}",
                success=False,
                error=str(exc),
            )

        # 4. Check if LLM requested a tool action
        tool_call = self._extract_tool_call(raw_response)
        if tool_call:
            action_name = tool_call.get("action", "")
            parameters = tool_call.get("parameters", {})
            logger.info("LLM triggered tool: '%s' with parameters %s", action_name, parameters)

            result = execute_action(action_name, parameters)
            if not result.success and result.error == "ConfirmationRequired":
                self._pending_confirmation = action_name
                return AssistantResponse(
                    text=f"{result.message}\n\nPlease reply **'Yes'** to confirm or **'No'** to cancel.",
                    success=True,
                )

            # Store user & assistant response in history
            self.history.append({"role": "user", "content": clean})
            self.history.append({"role": "assistant", "content": result.message})

            return AssistantResponse(
                text=result.message,
                success=result.success,
                error=result.error,
            )

        # 5. Natural conversation response
        self.history.append({"role": "user", "content": clean})
        self.history.append({"role": "assistant", "content": raw_response})

        return AssistantResponse(text=raw_response, success=True)

    def _extract_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract a structured JSON tool call from LLM output if present."""
        if not text:
            return None

        # Look for markdown code block containing JSON
        pattern = r"```(?:json)?\s*(\{\s*\"action\"\s*:.*?)\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if isinstance(data, dict) and "action" in data:
                    return data
            except Exception:
                pass

        # Also attempt direct JSON parsing if the whole response is a JSON object
        trimmed = text.strip()
        if trimmed.startswith("{") and trimmed.endswith("}"):
            try:
                data = json.loads(trimmed)
                if isinstance(data, dict) and "action" in data:
                    return data
            except Exception:
                pass

        return None

    def _try_direct_command(self, text: str) -> Optional[AssistantResponse]:
        """Simple pattern matching for direct automation commands."""
        lowered = text.lower().strip()

        # -------------------------------------------------------------
        # 1. Run File from any Subfolder
        # e.g., "run file test_tts.py from any subfolders", "run app.py"
        # -------------------------------------------------------------
        match_run = re.match(
            r"^(?:run|execute|start)\s+(?:file\s+)?([^\s]+\.[a-zA-Z0-9]+)(?:\s+from\s+(?:any\s+)?(?:subfolders?|subdirectories|sub\s+folders?))?$",
            text.strip(),
            re.IGNORECASE,
        )
        if match_run:
            target_file = match_run.group(1).strip()
            res = execute_action("run_file", {"path": target_file})
            return AssistantResponse(text=res.message, success=res.success, error=res.error)

        # -------------------------------------------------------------
        # 2. Smart Folder Creation without requiring full paths
        # e.g., "create a folder under d drive under this perticular folder CineCritic"
        #       "create a folder test under d drive under Prac1"
        # -------------------------------------------------------------
        norm_text = re.sub(r"\bperticular\b", "particular", text.strip(), flags=re.IGNORECASE)
        match_smart_drive = re.match(
            r"^(?:create|make)\s+(?:a\s+)?folder(?:\s+(?:named|called)\s+([^\s]+))?\s+under\s+([a-zA-Z])(?:\s+drive)?\s+under\s+(?:this\s+)?(?:particular\s+)?(?:folder\s+)?([^\s]+)(?:\s+(?:named|called)\s+([^\s]+))?$",
            norm_text,
            re.IGNORECASE,
        )
        if match_smart_drive:
            new1, drive_letter, parent_name, new2 = match_smart_drive.groups()
            new_name = new1 or new2 or "new_folder"
            res = execute_action(
                "smart_create_folder",
                {
                    "parent_folder": parent_name,
                    "new_folder_name": new_name,
                    "drive": drive_letter,
                },
            )
            return AssistantResponse(text=res.message, success=res.success, error=res.error)

        match_smart_parent = re.match(
            r"^(?:create|make)\s+(?:a\s+)?folder(?:\s+(?:named|called)\s+([^\s]+))?\s+under\s+(?:this\s+)?(?:particular\s+)?(?:folder\s+)?([^\s]+)(?:\s+(?:named|called)\s+([^\s]+))?$",
            norm_text,
            re.IGNORECASE,
        )
        if match_smart_parent:
            new1, parent_name, new2 = match_smart_parent.groups()
            if not re.match(r"^[a-zA-Z](?:\s+drive)?$", parent_name, re.I) and "\\" not in parent_name and "/" not in parent_name:
                new_name = new1 or new2 or "new_folder"
                res = execute_action(
                    "smart_create_folder",
                    {
                        "parent_folder": parent_name,
                        "new_folder_name": new_name,
                        "drive": None,
                    },
                )
                return AssistantResponse(text=res.message, success=res.success, error=res.error)

        # -------------------------------------------------------------
        # 3. Explicit Path Folder Creation
        # e.g., "create folder E:\Study\test", "create folder test in E:\Study",
        #       "make folder ...", "mkdir ...", "new folder ..."
        # -------------------------------------------------------------
        match_create = (
            re.match(r"^(?:create|make|add|new)\s+(?:a\s+)?(?:folder|directory)\s+(.+)$", text, re.IGNORECASE)
            or re.match(r"^mkdir\s+(.+)$", text, re.IGNORECASE)
        )
        if match_create:
            target = match_create.group(1).strip()
            # Pattern: "<name> in/under <location>"
            match_in = re.match(r"^(.+?)\s+(?:in|under|inside)\s+(.+)$", target, re.IGNORECASE)
            # Pattern: "under <location> named/called <name>"
            match_named = re.match(r"^(?:under|in|inside)\s+(.+?)\s+(?:named|called)\s+(.+)$", target, re.IGNORECASE)

            if match_named:
                loc = match_named.group(1).strip()
                name = match_named.group(2).strip().strip("\"'")
                target_path = f"{loc}/{name}"
            elif match_in:
                name = match_in.group(1).strip().strip("\"'")
                loc = match_in.group(2).strip()
                target_path = f"{loc}/{name}"
            else:
                target_path = target

            res = execute_action("create_folder", {"path": target_path})
            return AssistantResponse(text=res.message, success=res.success, error=res.error)

        # -------------------------------------------------------------
        # 2. File and Folder Opening / Exploring
        # -------------------------------------------------------------
        if lowered.startswith("open ") and not lowered.startswith("open http"):
            target = text[5:].strip()

            # Explicit folder open: "open folder <path>", "open directory <path>"
            if target.lower().startswith("folder "):
                folder_path = target[7:].strip()
                res = execute_action("open_folder", {"path": folder_path})
                return AssistantResponse(text=res.message, success=res.success, error=res.error)
            if target.lower().startswith("directory "):
                folder_path = target[10:].strip()
                res = execute_action("open_folder", {"path": folder_path})
                return AssistantResponse(text=res.message, success=res.success, error=res.error)

            # Explicit file open: "open file <path>"
            if target.lower().startswith("file "):
                file_path = target[5:].strip()
                res = execute_action("open_file", {"path": file_path})
                return AssistantResponse(text=res.message, success=res.success, error=res.error)

            # Heuristic detection for file/folder path vs application name
            cleaned = target.strip("\"'")
            if (
                ":" in cleaned
                or "/" in cleaned
                or "\\" in cleaned
                or cleaned.endswith((".txt", ".pdf", ".py", ".docx", ".xlsx", ".csv", ".json", ".md", ".log"))
            ):
                resolved = _resolve_safe_path(cleaned)
                if resolved and resolved.exists() and resolved.is_dir():
                    res = execute_action("open_folder", {"path": str(resolved)})
                else:
                    res = execute_action("open_file", {"path": cleaned})
                return AssistantResponse(text=res.message, success=res.success, error=res.error)
            else:
                res = execute_action("open_application", {"name": target})
                return AssistantResponse(text=res.message, success=res.success, error=res.error)

        # "explore folder <path>" or "explore <path>"
        if lowered.startswith("explore "):
            folder_path = text[8:].strip()
            if folder_path.lower().startswith("folder "):
                folder_path = folder_path[7:].strip()
            res = execute_action("open_folder", {"path": folder_path})
            return AssistantResponse(text=res.message, success=res.success, error=res.error)

        # -------------------------------------------------------------
        # 3. Folder Listing
        # e.g., "list folder <path>", "list files in <path>", "dir <path>"
        # -------------------------------------------------------------
        match_list = (
            re.match(r"^list\s+(?:the\s+)?(?:folder|directory|files\s+(?:in|under)?)\s+(.+)$", text, re.IGNORECASE)
            or re.match(r"^dir\s+(.+)$", text, re.IGNORECASE)
        )
        if match_list:
            dir_path = match_list.group(1).strip()
            res = execute_action("list_folder", {"path": dir_path})
            return AssistantResponse(text=res.message, success=res.success, error=res.error)

        # -------------------------------------------------------------
        # 4. File Reading
        # e.g., "read file <path>", "show file <path>"
        # -------------------------------------------------------------
        match_read = re.match(r"^(?:read|view|show|cat)\s+(?:file\s+)?(.+?\.[a-zA-Z0-9]+)$", text, re.IGNORECASE)
        if match_read:
            file_path = match_read.group(1).strip()
            res = execute_action("read_file", {"path": file_path})
            return AssistantResponse(text=res.message, success=res.success, error=res.error)

        # -------------------------------------------------------------
        # 5. File / Folder Information
        # e.g., "file info <path>", "folder info <path>", "get info <path>"
        # -------------------------------------------------------------
        match_info = re.match(r"^(?:get\s+)?(?:file|folder)?\s*info\s+(.+)$", text, re.IGNORECASE)
        if match_info:
            info_path = match_info.group(1).strip()
            res = execute_action("get_file_info", {"path": info_path})
            return AssistantResponse(text=res.message, success=res.success, error=res.error)

        # -------------------------------------------------------------
        # 6. File / Folder Renaming & Moving
        # e.g., "rename file <old> to <new>", "rename <old> to <new>"
        #       "move file <src> to <dst>", "move <src> to <dst>"
        # -------------------------------------------------------------
        match_rename = re.match(r"^rename\s+(?:file\s+|folder\s+)?(.+?)\s+to\s+(.+)$", text, re.IGNORECASE)
        if match_rename:
            old_p = match_rename.group(1).strip()
            new_p = match_rename.group(2).strip()
            res = execute_action("rename_file", {"old_path": old_p, "new_path": new_p})
            return AssistantResponse(text=res.message, success=res.success, error=res.error)

        match_move = re.match(r"^move\s+(?:file\s+|folder\s+)?(.+?)\s+to\s+(.+)$", text, re.IGNORECASE)
        if match_move:
            src = match_move.group(1).strip()
            dst = match_move.group(2).strip()
            res = execute_action("move_file", {"source": src, "destination": dst})
            return AssistantResponse(text=res.message, success=res.success, error=res.error)

        # -------------------------------------------------------------
        # 7. File / Folder Deletion
        # -------------------------------------------------------------
        match_del_file = re.match(r"^(?:delete|remove)\s+file\s+(.+)$", text, re.IGNORECASE)
        if match_del_file:
            target = match_del_file.group(1).strip()
            res = execute_action("delete_file", {"path": target})
            return AssistantResponse(text=res.message, success=res.success, error=res.error)

        match_del_dir = re.match(r"^(?:delete|remove)\s+(?:folder|directory)\s+(.+)$", text, re.IGNORECASE)
        if match_del_dir:
            target = match_del_dir.group(1).strip()
            res = execute_action("delete_folder", {"path": target})
            return AssistantResponse(text=res.message, success=res.success, error=res.error)

        # -------------------------------------------------------------
        # 8. Volume Controls
        # -------------------------------------------------------------
        if "volume up" in lowered or "increase volume" in lowered:
            res = execute_action("volume_up", {"steps": 2})
            return AssistantResponse(text=res.message, success=res.success)
        if "volume down" in lowered or "decrease volume" in lowered:
            res = execute_action("volume_down", {"steps": 2})
            return AssistantResponse(text=res.message, success=res.success)
        if lowered in {"mute", "unmute", "toggle mute"}:
            res = execute_action("toggle_mute", {})
            return AssistantResponse(text=res.message, success=res.success)

        # -------------------------------------------------------------
        # 9. Screenshot
        # -------------------------------------------------------------
        if "screenshot" in lowered:
            res = execute_action("take_screenshot", {})
            return AssistantResponse(text=res.message, success=res.success)

        # -------------------------------------------------------------
        # 10. Diagnostics
        # -------------------------------------------------------------
        if "cpu" in lowered:
            res = execute_action("get_cpu_usage", {})
            return AssistantResponse(text=res.message, success=res.success)
        if "battery" in lowered:
            res = execute_action("get_battery_status", {})
            return AssistantResponse(text=res.message, success=res.success)
        if "ram" in lowered or "memory" in lowered:
            res = execute_action("get_memory_usage", {})
            return AssistantResponse(text=res.message, success=res.success)

        return None
