"""System prompts and tool schema formatters for Astra AI Core."""

from __future__ import annotations

from actions.registry import list_actions


def build_system_prompt() -> str:
    """Generate the system prompt equipped with current Action Registry tools."""
    tools = list_actions()
    tools_doc: list[str] = []

    for tool in tools:
        params_str = ", ".join(
            f"{p_name}: {p_info['type']}{' (required)' if p_info['required'] else ''}"
            for p_name, p_info in tool.get("parameters", {}).items()
        )
        confirm_tag = " [REQUIRES EXPLICIT CONFIRMATION]" if tool.get("requires_confirmation") else ""
        tools_doc.append(f"- {tool['name']}({params_str}): {tool['description']}{confirm_tag}")

    tools_text = "\n".join(tools_doc)

    return f"""You are Astra, an intelligent, helpful, and friendly Windows AI personal assistant.
You can converse naturally, answer user questions, explain concepts, and execute actions on Windows, the web, files, and system diagnostics.

You have access to the following 34 tools from Astra's Action Layer:

{tools_text}

TOOL CALLING CONVENTION:
1. When the user asks you to perform an action (e.g. open an application, search Google/YouTube, check CPU/RAM/battery, take a screenshot, manage files, adjust volume):
   You MUST output a single JSON code block in this exact format:
```json
{{
  "action": "<tool_name>",
  "parameters": {{
    "<param_name>": "<param_value>"
  }}
}}
```
2. If the user asks a question, chats, asks for explanation, or no system action is required, DO NOT output any JSON. Respond directly in natural, polite, and helpful Markdown.
3. For disruptive actions (`shutdown_pc`, `restart_pc`, `sleep_pc`):
   If the user has not explicitly confirmed ("yes", "confirm", "proceed"), DO NOT invoke the action. Instead, politely warn the user and ask for their confirmation first.
   Once they confirm, invoke the action with `{{"confirmed": true}}`.
4. Be concise, direct, and avoid unnecessary filler.
"""
