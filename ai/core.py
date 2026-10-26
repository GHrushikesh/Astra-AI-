"""Astra AI Core Engine.

Implements AssistantInterface connecting LLM intelligence, conversation memory,
and tool execution through Astra's Action Registry.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from actions.base import ActionResult, get_logger
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

        # 2. Check if API key is configured
        if not self.client.has_api_key():
            # Check for direct offline command fallback
            offline_res = self._try_direct_command(clean)
            if offline_res:
                return offline_res

            return AssistantResponse(
                text=(
                    f"👋 **Welcome to Astra!**\n\n"
                    f"To enable AI intelligence, please open **Settings** (⚙ in the sidebar) "
                    f"and enter your **{self.client.provider} API Key**.\n\n"
                    f"💡 *Tip: You can also use direct commands right now, like:*\n"
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
            logger.error("LLM generation failed: %s", exc)
            return AssistantResponse(
                text=f"AI connection error: {exc}",
                success=False,
                error=str(exc),
            )
        except Exception as exc:
            logger.error("Unexpected error during LLM generation: %s", exc)
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
                    text=f"⚠️ {result.message}\n\nPlease reply **'Yes'** to confirm or **'No'** to cancel.",
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
        """Simple pattern matching for direct commands when API key is not yet set."""
        lowered = text.lower()

        # Open application
        if lowered.startswith("open ") and not lowered.startswith("open http"):
            app_name = text[5:].strip()
            if "." in app_name and ("/" in app_name or "\\" in app_name or app_name.endswith((".txt", ".pdf", ".py"))):
                res = execute_action("open_file", {"path": app_name})
            else:
                res = execute_action("open_application", {"name": app_name})
            return AssistantResponse(text=res.message, success=res.success, error=res.error)

        # Volume
        if "volume up" in lowered or "increase volume" in lowered:
            res = execute_action("volume_up", {"steps": 2})
            return AssistantResponse(text=res.message, success=res.success)
        if "volume down" in lowered or "decrease volume" in lowered:
            res = execute_action("volume_down", {"steps": 2})
            return AssistantResponse(text=res.message, success=res.success)
        if lowered in {"mute", "unmute", "toggle mute"}:
            res = execute_action("toggle_mute", {})
            return AssistantResponse(text=res.message, success=res.success)

        # Screenshot
        if "screenshot" in lowered:
            res = execute_action("take_screenshot", {})
            return AssistantResponse(text=res.message, success=res.success)

        # Diagnostics
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
