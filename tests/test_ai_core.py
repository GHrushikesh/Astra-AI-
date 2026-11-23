"""Tests for Astra's AI & LLM integration."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from actions.base import ActionResult
from ai.client import LLMClient, LLMError
from ai.core import AstraAICore
from ai.prompts import build_system_prompt
from ui.assistant_interface import AssistantResponse
from ui.settings import AstraSettings, SettingsStore


class TestPrompts(unittest.TestCase):
    def test_build_system_prompt_includes_tools(self):
        prompt = build_system_prompt()
        self.assertIn("Astra", prompt)
        self.assertIn("open_application", prompt)
        self.assertIn("take_screenshot", prompt)
        self.assertIn("open_website", prompt)
        self.assertIn("```json", prompt)


class TestLLMClient(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_api_key_raises_error(self):
        client = LLMClient(provider="Google Gemini", api_key="")
        with self.assertRaises(LLMError) as ctx:
            client.generate("hello")
        self.assertIn("No API key configured", str(ctx.exception))

    @patch("ai.client.requests.post")
    def test_gemini_api_call(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Hello! How can I help you today?"}
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        client = LLMClient(provider="Google Gemini", api_key="test-gemini-key")
        result = client.generate("Hi", system_instruction="You are Astra.")

        self.assertEqual(result, "Hello! How can I help you today?")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn("key=test-gemini-key", args[0])
        self.assertIn("gemini-2.5-flash-lite:generateContent", args[0])
        payload = kwargs["json"]
        self.assertIn("contents", payload)
        self.assertIn("systemInstruction", payload)

    @patch("ai.client.requests.post")
    def test_gemini_404_auto_fallback(self, mock_post):
        resp_404 = MagicMock()
        resp_404.status_code = 404
        resp_404.json.return_value = {"error": {"message": "models/deprecated is not found"}}

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Fallback succeeded!"}]}}]
        }
        mock_post.side_effect = [resp_404, resp_200]

        client = LLMClient(provider="Google Gemini", api_key="test-gemini-key", model="gemini-old-model")
        result = client.generate("Hi")
        self.assertEqual(result, "Fallback succeeded!")
        self.assertEqual(mock_post.call_count, 2)

    @patch("ai.client.requests.post")
    def test_openai_api_call(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "OpenAI response"
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        client = LLMClient(provider="OpenAI", api_key="sk-test", model="gpt-4o-mini")
        result = client.generate("Hi", system_instruction="You are Astra.")

        self.assertEqual(result, "OpenAI response")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.openai.com/v1/chat/completions")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sk-test")
        payload = kwargs["json"]
        self.assertEqual(payload["model"], "gpt-4o-mini")
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][1]["role"], "user")

    @patch("ai.client.requests.post")
    def test_anthropic_api_call(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": [
                {"type": "text", "text": "Anthropic response"}
            ]
        }
        mock_post.return_value = mock_resp

        client = LLMClient(provider="Anthropic", api_key="sk-ant-test")
        result = client.generate("Hi", system_instruction="System note.")

        self.assertEqual(result, "Anthropic response")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.anthropic.com/v1/messages")
        self.assertEqual(kwargs["headers"]["x-api-key"], "sk-ant-test")
        self.assertEqual(kwargs["json"]["system"], "System note.")

    @patch("ai.client.requests.post")
    def test_ollama_local_call_without_api_key(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Ollama response"}}]
        }
        mock_post.return_value = mock_resp

        client = LLMClient(provider="Ollama / Local", api_key="")
        result = client.generate("Hi")
        self.assertEqual(result, "Ollama response")
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "http://localhost:11434/v1/chat/completions")

    @patch("ai.client.requests.post")
    def test_http_error_raises_llm_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"error": {"message": "Invalid API key provided"}}
        mock_post.return_value = mock_resp

        client = LLMClient(provider="OpenAI", api_key="bad-key")
        with self.assertRaises(LLMError) as ctx:
            client.generate("Hi")
        self.assertIn("Invalid API key provided", str(ctx.exception))


class TestAstraAICore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.settings_file = Path(self.temp_dir.name) / "settings.json"
        self.store = SettingsStore(self.settings_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_missing_api_key_friendly_message(self):
        core = AstraAICore(settings_store=self.store)
        res = core.process("Tell me about quantum physics")
        self.assertTrue(res.success)
        self.assertIn("API Key", res.text)
        self.assertIn("Settings", res.text)

    def test_offline_command_fallback_without_api_key(self):
        core = AstraAICore(settings_store=self.store)
        with patch("actions.registry.registry.execute_action") as mock_exec:
            mock_exec.return_value = ActionResult(
                success=True,
                message="Volume increased.",
                data={"level": 50},
            )
            res = core.process("volume up")
            self.assertTrue(res.success)
            self.assertIn("Volume increased", res.text)
            mock_exec.assert_called_once_with("volume_up", {"steps": 2})

    def test_conversational_llm_response(self):
        settings = AstraSettings(llm_provider="Google Gemini", llm_api_key="valid-key")
        self.store.save(settings)
        core = AstraAICore(settings_store=self.store)

        with patch.object(core.client, "generate", return_value="Hello! I am Astra."):
            res = core.process("Hello")
            self.assertTrue(res.success)
            self.assertEqual(res.text, "Hello! I am Astra.")

    def test_tool_call_execution(self):
        settings = AstraSettings(llm_provider="Google Gemini", llm_api_key="valid-key")
        self.store.save(settings)
        core = AstraAICore(settings_store=self.store)

        tool_json = '```json\n{"action": "web_search", "parameters": {"query": "python 3.12 release"}}\n```'
        with patch.object(core.client, "generate", return_value=tool_json):
            with patch("actions.registry.registry.execute_action") as mock_exec:
                mock_exec.return_value = ActionResult(
                    success=True,
                    message="Search query opened: python 3.12 release",
                    data={"url": "https://www.google.com/search?q=python+3.12+release"},
                )
                res = core.process("Search for python 3.12 release")
                self.assertTrue(res.success)
                self.assertIn("Search query opened", res.text)
                mock_exec.assert_called_once_with("web_search", {"query": "python 3.12 release"})

    def test_dangerous_action_confirmation_flow(self):
        settings = AstraSettings(llm_provider="Google Gemini", llm_api_key="valid-key")
        self.store.save(settings)
        core = AstraAICore(settings_store=self.store)

        with patch("actions.registry.registry.execute_action") as mock_exec:
            mock_exec.return_value = ActionResult(
                success=False,
                message="Shutdown requires confirmation.",
                error="ConfirmationRequired",
            )
            tool_json = '```json\n{"action": "shutdown_pc", "parameters": {}}\n```'
            with patch.object(core.client, "generate", return_value=tool_json):
                res = core.process("Shut down my computer")
                self.assertIn("confirm", res.text.lower())
                self.assertEqual(core._pending_confirmation, "shutdown_pc")

        # 2. Confirming executes the action with confirmed=True
        with patch("actions.registry.registry.execute_action") as mock_exec:
            mock_exec.return_value = ActionResult(
                success=True,
                message="System shutdown initiated.",
                data={},
            )
            res_confirm = core.process("yes")
            self.assertTrue(res_confirm.success)
            self.assertIn("System shutdown initiated", res_confirm.text)
            mock_exec.assert_called_once_with("shutdown_pc", {"confirmed": True})
            self.assertIsNone(core._pending_confirmation)

    def test_settings_update(self):
        core = AstraAICore(settings_store=self.store)
        self.assertEqual(core.client.api_key, "")

        new_settings = AstraSettings(
            llm_provider="OpenAI",
            llm_api_key="sk-new-key",
            llm_model="gpt-4o",
            llm_endpoint="https://custom.endpoint/v1",
        )
        core.update_settings(new_settings)

        self.assertEqual(core.client.provider, "OpenAI")
        self.assertEqual(core.client.api_key, "sk-new-key")
        self.assertEqual(core.client.model, "gpt-4o")
        self.assertEqual(core.client.endpoint, "https://custom.endpoint/v1")

    def test_direct_create_folder_under_subfolder(self):
        """Direct command 'create folder <path>' creates the nested directory immediately."""
        core = AstraAICore(settings_store=self.store)
        target = Path(self.temp_dir.name) / "e_drive_sim" / "some_folder" / "sub_folder"
        res = core.process(f"create folder {target}")
        self.assertTrue(res.success)
        self.assertTrue(target.is_dir())
        self.assertIn("created successfully", res.text.lower())

    def test_direct_create_folder_in_location_syntax(self):
        """Direct command 'create folder <name> in <loc>' creates folder properly."""
        core = AstraAICore(settings_store=self.store)
        parent = Path(self.temp_dir.name) / "workspace"
        res = core.process(f"create folder my_project in {parent}")
        self.assertTrue(res.success)
        expected = parent / "my_project"
        self.assertTrue(expected.is_dir())

    def test_direct_open_folder_command(self):
        """Direct command 'open folder <path>' calls open_folder."""
        core = AstraAICore(settings_store=self.store)
        target = Path(self.temp_dir.name) / "test_dir"
        target.mkdir()

        with patch("actions.file_actions.os.startfile") as mock_startfile:
            res = core.process(f"open folder {target}")
            self.assertTrue(res.success)
            mock_startfile.assert_called_once_with(str(target.resolve()))

    def test_direct_list_folder_command(self):
        """Direct command 'list folder <path>' lists directory contents."""
        core = AstraAICore(settings_store=self.store)
        target = Path(self.temp_dir.name) / "browse_me"
        target.mkdir()
        (target / "doc.txt").write_text("content", encoding="utf-8")

        res = core.process(f"list folder {target}")
        self.assertTrue(res.success)
        self.assertIn("doc.txt", res.text)

    def test_direct_smart_create_folder_under_particular_folder(self):
        """Direct command 'create a folder under d drive under this perticular folder <parent>'."""
        core = AstraAICore(settings_store=self.store)
        mock_parent = Path(self.temp_dir.name) / "mock_drive" / "sub" / "CineCritic"
        mock_parent.mkdir(parents=True)

        with patch("actions.file_actions.find_folder_path", return_value=mock_parent):
            res = core.process("create a folder under d drive under this perticular folder CineCritic called reviews")
            self.assertTrue(res.success)
            self.assertTrue((mock_parent / "reviews").is_dir())
            self.assertIn("created successfully", res.text.lower())

    @patch("actions.file_actions.subprocess.Popen")
    def test_direct_run_file_from_any_subfolder(self, mock_popen):
        """Direct command 'run file <name> from any subfolders' finds and executes file."""
        core = AstraAICore(settings_store=self.store)
        script = Path(self.temp_dir.name) / "src" / "deep" / "custom_task.py"
        script.parent.mkdir(parents=True)
        script.write_text("print('running')", encoding="utf-8")

        mock_proc = mock_popen.return_value
        mock_proc.pid = 4321

        with patch("actions.file_actions.find_file_path", return_value=script):
            res = core.process("run file custom_task.py from any subfolders")
            self.assertTrue(res.success)
            self.assertIn("custom_task.py", res.text)


if __name__ == "__main__":
    unittest.main()
