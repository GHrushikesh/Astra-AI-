"""Universal LLM client supporting Google Gemini, OpenAI, Groq, Ollama, and Anthropic.

Uses standard HTTP requests to ensure lightweight, dependency-free connectivity
without requiring provider-specific heavy SDKs.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional
import requests

from actions.base import get_logger

logger = get_logger("astra.ai.client")


class LLMError(Exception):
    """Raised when an LLM API request fails or returns an error."""


class LLMClient:
    """Universal client for communicating with various LLM providers."""

    DEFAULT_MODELS: Dict[str, str] = {
        "Google Gemini": "gemini-2.5-flash-lite",
        "OpenAI": "gpt-4o-mini",
        "Groq": "llama-3.3-70b-versatile",
        "Ollama / Local": "llama3.2",
        "Anthropic": "claude-3-5-haiku-20241022",
        "Custom": "gpt-4o-mini",
    }

    DEFAULT_ENDPOINTS: Dict[str, str] = {
        "OpenAI": "https://api.openai.com/v1/chat/completions",
        "Groq": "https://api.groq.com/openai/v1/chat/completions",
        "Ollama / Local": "http://localhost:11434/v1/chat/completions",
        "Anthropic": "https://api.anthropic.com/v1/messages",
    }

    def __init__(
        self,
        provider: str = "Google Gemini",
        api_key: str = "",
        model: str = "",
        endpoint: str = "",
        timeout: float = 30.0,
    ) -> None:
        self.provider = provider or "Google Gemini"
        self.api_key = (api_key or "").strip()
        self.model = (model or "").strip() or self.DEFAULT_MODELS.get(self.provider, "gemini-2.5-flash-lite")
        if self.provider == "Google Gemini" and (not self.model or self.model in ("gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-2.0-flash-exp", "gemini-2.5-flash")):
            self.model = "gemini-2.5-flash-lite"
        self.endpoint = (endpoint or "").strip()
        self.timeout = timeout

        # Fallback to environment variables if api_key is empty
        if not self.api_key:
            self._load_key_from_env()

    def _load_key_from_env(self) -> None:
        """Attempt to read API key from standard environment variables."""
        env_map = {
            "Google Gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
            "OpenAI": ["OPENAI_API_KEY"],
            "Groq": ["GROQ_API_KEY"],
            "Anthropic": ["ANTHROPIC_API_KEY"],
        }
        for env_var in env_map.get(self.provider, ["ASTRA_API_KEY"]):
            val = os.environ.get(env_var, "").strip()
            if val:
                self.api_key = val
                logger.info("Loaded API key for '%s' from %s", self.provider, env_var)
                break

    def has_api_key(self) -> bool:
        """Check if an API key is configured or not required (e.g., local Ollama)."""
        if self.provider == "Ollama / Local":
            return True
        return bool(self.api_key)

    def generate(
        self,
        prompt: str,
        system_instruction: str = "",
        history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
    ) -> str:
        """Send a prompt with history to the configured LLM provider.

        Args:
            prompt: User message text.
            system_instruction: System prompt instructing the model.
            history: Optional list of previous turns [{'role': 'user'|'assistant', 'content': str}].
            temperature: Sampling temperature.

        Returns:
            The raw text response from the LLM.

        Raises:
            LLMError: If authentication fails, API errors, or network timeouts occur.
        """
        if not self.has_api_key():
            raise LLMError(
                f"No API key configured for {self.provider}. "
                "Please add your API key in Astra Settings."
            )

        provider_lower = self.provider.lower()
        if "gemini" in provider_lower or "google" in provider_lower:
            return self._generate_gemini(prompt, system_instruction, history, temperature)
        elif "anthropic" in provider_lower or "claude" in provider_lower:
            return self._generate_anthropic(prompt, system_instruction, history, temperature)
        else:
            # OpenAI-compatible: OpenAI, Groq, Ollama, Custom
            return self._generate_openai_compatible(prompt, system_instruction, history, temperature)

    # ──────────────────────────────────────────────────────────────────────────
    # Google Gemini Native REST Implementation
    # ──────────────────────────────────────────────────────────────────────────

    def _generate_gemini(
        self,
        prompt: str,
        system_instruction: str,
        history: Optional[List[Dict[str, str]]],
        temperature: float,
    ) -> str:
        contents: List[Dict[str, Any]] = []
        if history:
            for turn in history:
                role = "user" if turn.get("role") == "user" else "model"
                contents.append({"role": role, "parts": [{"text": turn.get("content", "")}]})

        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 2048,
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        headers = {"Content-Type": "application/json"}

        # Determine primary model and fallback candidates
        primary_model = self.model
        if primary_model in ("gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-2.0-flash-exp", "gemini-2.5-flash", ""):
            primary_model = "gemini-2.5-flash-lite"

        candidate_models = [primary_model]
        for fallback in ("gemini-2.5-flash-lite", "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-flash-latest", "gemini-3.8-flash"):
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        last_error_msg = ""
        for model_name in candidate_models:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                f"?key={self.api_key}"
            )

            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            except requests.exceptions.Timeout:
                raise LLMError(f"Request to Google Gemini timed out after {self.timeout}s.")
            except requests.exceptions.RequestException as exc:
                raise LLMError(f"Network error connecting to Google Gemini: {exc}")

            if resp.status_code == 200:
                self.model = model_name  # Pin the working model
                try:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise LLMError("Google Gemini returned empty candidates list.")
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if not parts:
                        raise LLMError("Google Gemini response contained no text parts.")
                    return str(parts[0].get("text", "")).strip()
                except (KeyError, IndexError, ValueError) as exc:
                    raise LLMError(f"Failed to parse Google Gemini response: {exc}")

            # Capture error details
            error_msg = f"HTTP {resp.status_code}"
            try:
                err_json = resp.json()
                if "error" in err_json and "message" in err_json["error"]:
                    error_msg = err_json["error"]["message"]
            except Exception:
                error_msg = resp.text[:200]
            last_error_msg = error_msg

            if resp.status_code != 404:
                # 400, 401, 403 are auth or permission errors - do not retry models
                raise LLMError(f"Google Gemini API error ({resp.status_code}): {error_msg}")

        # Dynamic fallback: query list of models supported by this API key
        try:
            list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
            list_resp = requests.get(list_url, timeout=6)
            if list_resp.status_code == 200:
                data = list_resp.json()
                discovered = [
                    m["name"].replace("models/", "")
                    for m in data.get("models", [])
                    if "generateContent" in m.get("supportedGenerationMethods", [])
                ]
                for disc_model in discovered:
                    if disc_model in candidate_models:
                        continue
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{disc_model}:generateContent?key={self.api_key}"
                    resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
                    if resp.status_code == 200:
                        self.model = disc_model
                        data = resp.json()
                        parts = data.get("candidates", [])[0].get("content", {}).get("parts", [])
                        return str(parts[0].get("text", "")).strip()
        except Exception:
            pass

        raise LLMError(f"Google Gemini API error (404): {last_error_msg}")

    # ──────────────────────────────────────────────────────────────────────────
    # OpenAI-Compatible Implementation (OpenAI, Groq, Ollama, Custom)
    # ──────────────────────────────────────────────────────────────────────────

    def _generate_openai_compatible(
        self,
        prompt: str,
        system_instruction: str,
        history: Optional[List[Dict[str, str]]],
        temperature: float,
    ) -> str:
        url = self.endpoint or self.DEFAULT_ENDPOINTS.get(self.provider, "https://api.openai.com/v1/chat/completions")

        messages: List[Dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})

        if history:
            for turn in history:
                role = "user" if turn.get("role") == "user" else "assistant"
                messages.append({"role": role, "content": turn.get("content", "")})

        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        except requests.exceptions.Timeout:
            raise LLMError(f"Request to {self.provider} timed out after {self.timeout}s.")
        except requests.exceptions.RequestException as exc:
            raise LLMError(f"Network error connecting to {self.provider}: {exc}")

        if resp.status_code != 200:
            error_msg = f"HTTP {resp.status_code}"
            try:
                err_json = resp.json()
                if "error" in err_json:
                    err_obj = err_json["error"]
                    error_msg = err_obj.get("message", str(err_obj)) if isinstance(err_obj, dict) else str(err_obj)
            except Exception:
                error_msg = resp.text[:200]
            raise LLMError(f"{self.provider} API error ({resp.status_code}): {error_msg}")

        try:
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise LLMError(f"{self.provider} returned no response choices.")
            return str(choices[0].get("message", {}).get("content", "")).strip()
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError(f"Failed to parse {self.provider} response: {exc}")

    # ──────────────────────────────────────────────────────────────────────────
    # Anthropic Claude Implementation
    # ──────────────────────────────────────────────────────────────────────────

    def _generate_anthropic(
        self,
        prompt: str,
        system_instruction: str,
        history: Optional[List[Dict[str, str]]],
        temperature: float,
    ) -> str:
        url = self.endpoint or self.DEFAULT_ENDPOINTS["Anthropic"]

        messages: List[Dict[str, str]] = []
        if history:
            for turn in history:
                role = "user" if turn.get("role") == "user" else "assistant"
                messages.append({"role": role, "content": turn.get("content", "")})

        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "max_tokens": 2048,
            "messages": messages,
            "temperature": temperature,
        }
        if system_instruction:
            payload["system"] = system_instruction

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        except requests.exceptions.Timeout:
            raise LLMError(f"Request to Anthropic timed out after {self.timeout}s.")
        except requests.exceptions.RequestException as exc:
            raise LLMError(f"Network error connecting to Anthropic: {exc}")

        if resp.status_code != 200:
            error_msg = f"HTTP {resp.status_code}"
            try:
                err_json = resp.json()
                if "error" in err_json and "message" in err_json["error"]:
                    error_msg = err_json["error"]["message"]
            except Exception:
                error_msg = resp.text[:200]
            raise LLMError(f"Anthropic API error ({resp.status_code}): {error_msg}")

        try:
            data = resp.json()
            contents = data.get("content", [])
            if not contents:
                raise LLMError("Anthropic returned empty content.")
            return str(contents[0].get("text", "")).strip()
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError(f"Failed to parse Anthropic response: {exc}")
