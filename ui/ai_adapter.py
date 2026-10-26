"""Integration adapter mapping AI core execution and ActionResults to AssistantResponses."""

from __future__ import annotations

from typing import Any, Callable, Optional

from actions.base import ActionResult
from actions.registry import execute_action
from ui.assistant_interface import AssistantInterface, AssistantResponse


def map_action_result_to_response(
    result: ActionResult,
    success_prefix: str = "",
) -> AssistantResponse:
    """Map a standardized ActionResult to an AssistantResponse for the UI.

    Args:
        result: The ActionResult from the action layer.
        success_prefix: Optional string prepended to the message on success.
    """
    if not isinstance(result, ActionResult):
        return AssistantResponse(
            text="The action layer returned an invalid result.",
            success=False,
            error="Invalid ActionResult type",
        )

    if result.success:
        text = f"{success_prefix} {result.message}".strip() if success_prefix else result.message
        return AssistantResponse(text=text, success=True)
    else:
        return AssistantResponse(
            text=result.message or "I could not complete that request.",
            success=False,
            error=result.error or result.message or "Action execution failed.",
        )


class AICoreAdapter(AssistantInterface):
    """Production-ready adapter connecting Astra's AI core to the presentation UI.

    Supports:
    - Direct invocation of the project lead's AI core processing engine
    - Safe handling of missing or failing AI core
    - Mapping action executions to formatted AssistantResponses
    - Fallback handling for invalid AI core responses
    """

    def __init__(
        self,
        ai_processor: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self._processor = ai_processor

    def process(self, user_text: str) -> AssistantResponse:
        """Process user text and return AssistantResponse."""
        clean = (user_text or "").strip()
        if not clean:
            return AssistantResponse(text="Please provide a message or command.", success=True)

        if self._processor is not None:
            try:
                res = self._processor(clean)
                if isinstance(res, AssistantResponse):
                    return res
                if isinstance(res, ActionResult):
                    return map_action_result_to_response(res)
                if isinstance(res, str):
                    return AssistantResponse(text=res, success=True)
                if isinstance(res, dict) and "text" in res:
                    return AssistantResponse(
                        text=str(res["text"]),
                        success=bool(res.get("success", True)),
                        error=res.get("error"),
                    )
                return AssistantResponse(
                    text="Received unrecognized response format from AI core.",
                    success=False,
                    error="Invalid AI core response format",
                )
            except Exception as exc:
                return AssistantResponse(
                    text="I could not complete that request.",
                    success=False,
                    error=str(exc),
                )

        # Fallback when no external AI processor is injected:
        return AssistantResponse(
            text=f"Astra: {clean}",
            success=True,
        )
