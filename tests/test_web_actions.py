"""Tests for Milestone 6: Web Actions (actions/web_actions.py).

All browser invocations (webbrowser.open) are strictly mocked so no real browser
windows or tabs are ever launched during automated testing.
"""

import unittest
from unittest.mock import patch

from actions.web_actions import (
    github_search,
    google_search,
    open_website,
    web_search,
    youtube_search,
)


class TestWebActions(unittest.TestCase):
    """Unit test suite for Web Actions."""

    # ---------------------------------------------------------
    # open_website tests
    # ---------------------------------------------------------
    @patch("actions.web_actions.webbrowser.open")
    def test_open_website_valid(self, mock_open):
        """open_website accepts valid https URL and opens browser."""
        mock_open.return_value = True
        res = open_website("https://example.com/test")
        self.assertTrue(res.success)
        self.assertEqual(res.data["url"], "https://example.com/test")
        mock_open.assert_called_once_with("https://example.com/test")

    @patch("actions.web_actions.webbrowser.open")
    def test_open_website_domain_normalization(self, mock_open):
        """open_website normalizes bare domains to https."""
        mock_open.return_value = True
        res = open_website("github.com")
        self.assertTrue(res.success)
        self.assertEqual(res.data["url"], "https://github.com")
        mock_open.assert_called_once_with("https://github.com")

    @patch("actions.web_actions.webbrowser.open")
    def test_open_website_domain_with_path_normalized(self, mock_open):
        """open_website normalizes bare domain with subpath to https."""
        mock_open.return_value = True
        res = open_website("python.org/downloads")
        self.assertTrue(res.success)
        self.assertEqual(res.data["url"], "https://python.org/downloads")
        mock_open.assert_called_once_with("https://python.org/downloads")

    def test_open_website_invalid_urls(self):
        """Invalid, empty, or non-string inputs fail cleanly."""
        for invalid in ["", "   ", None, 12345]:  # type: ignore
            res = open_website(invalid)  # type: ignore
            self.assertFalse(res.success)
            self.assertEqual(res.error, "InvalidURL")

    def test_open_website_blocked_schemes(self):
        """Dangerous or unsupported URL schemes are strictly rejected."""
        blocked_urls = [
            "file:///C:/Windows/System32/cmd.exe",
            "javascript:alert('XSS')",
            "data:text/html,<html>hello</html>",
            "vbscript:msgbox('hack')",
            "about:blank",
            "chrome://settings",
        ]
        for url in blocked_urls:
            res = open_website(url)
            self.assertFalse(res.success)
            self.assertEqual(res.error, "InvalidURL")

    @patch("actions.web_actions.webbrowser.open")
    def test_open_website_browser_error(self, mock_open):
        """Browser launcher failure is handled gracefully."""
        mock_open.return_value = False
        res = open_website("https://example.com")
        self.assertFalse(res.success)
        self.assertEqual(res.error, "BrowserOpenError")

    @patch("actions.web_actions.webbrowser.open")
    def test_open_website_exception_handled(self, mock_open):
        """Exceptions in webbrowser.open are caught cleanly."""
        mock_open.side_effect = OSError("Browser binary not found")
        res = open_website("https://example.com")
        self.assertFalse(res.success)
        self.assertIn("Browser binary not found", res.error)

    # ---------------------------------------------------------
    # Search functions tests
    # ---------------------------------------------------------
    @patch("actions.web_actions.webbrowser.open")
    def test_google_search(self, mock_open):
        """google_search formats and opens encoded Google search URL."""
        mock_open.return_value = True
        res = google_search("Python DSA tutorial")
        self.assertTrue(res.success)
        self.assertEqual(res.data["query"], "Python DSA tutorial")
        self.assertEqual(
            res.data["url"],
            "https://www.google.com/search?q=Python+DSA+tutorial",
        )
        mock_open.assert_called_once_with(
            "https://www.google.com/search?q=Python+DSA+tutorial"
        )

    @patch("actions.web_actions.webbrowser.open")
    def test_web_search(self, mock_open):
        """web_search executes default web search."""
        mock_open.return_value = True
        res = web_search("Deep Learning basics")
        self.assertTrue(res.success)
        self.assertEqual(res.data["query"], "Deep Learning basics")
        self.assertIn("https://www.google.com/search?q=", res.data["url"])

    @patch("actions.web_actions.webbrowser.open")
    def test_youtube_search(self, mock_open):
        """youtube_search formats and opens encoded YouTube search URL."""
        mock_open.return_value = True
        res = youtube_search("lofi hip hop radio")
        self.assertTrue(res.success)
        self.assertEqual(res.data["query"], "lofi hip hop radio")
        self.assertEqual(
            res.data["url"],
            "https://www.youtube.com/results?search_query=lofi+hip+hop+radio",
        )
        mock_open.assert_called_once_with(
            "https://www.youtube.com/results?search_query=lofi+hip+hop+radio"
        )

    @patch("actions.web_actions.webbrowser.open")
    def test_github_search(self, mock_open):
        """github_search formats and opens encoded GitHub search URL."""
        mock_open.return_value = True
        res = github_search("fastapi clean architecture")
        self.assertTrue(res.success)
        self.assertEqual(res.data["query"], "fastapi clean architecture")
        self.assertEqual(
            res.data["url"],
            "https://github.com/search?q=fastapi+clean+architecture",
        )
        mock_open.assert_called_once_with(
            "https://github.com/search?q=fastapi+clean+architecture"
        )

    @patch("actions.web_actions.webbrowser.open")
    def test_search_special_characters_encoding(self, mock_open):
        """Special characters (+, &, ?, #, unicode) are properly URL-encoded."""
        mock_open.return_value = True
        res = google_search("C++ & Python #100%")
        self.assertTrue(res.success)
        self.assertIn("C%2B%2B+%26+Python+%23100%25", res.data["url"])

    def test_search_empty_queries_fail(self):
        """Empty or whitespace-only search queries fail gracefully."""
        for invalid_query in ["", "    ", None]:  # type: ignore
            res_g = google_search(invalid_query)  # type: ignore
            self.assertFalse(res_g.success)
            self.assertEqual(res_g.error, "InvalidInput")

            res_yt = youtube_search(invalid_query)  # type: ignore
            self.assertFalse(res_yt.success)
            self.assertEqual(res_yt.error, "InvalidInput")

            res_gh = github_search(invalid_query)  # type: ignore
            self.assertFalse(res_gh.success)
            self.assertEqual(res_gh.error, "InvalidInput")


if __name__ == "__main__":
    unittest.main()
