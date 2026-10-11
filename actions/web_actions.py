"""Web actions for Astra.

Functions:
- open_website(url)
- web_search(query)
- google_search(query)
- youtube_search(query)
- github_search(query)

To be implemented in Milestone 6.
"""

from actions.base import ActionResult

__all__ = [
    "open_website",
    "web_search",
    "google_search",
    "youtube_search",
    "github_search",
]


def open_website(url: str) -> ActionResult:
    """Open a URL in the user's default web browser."""
    raise NotImplementedError("Scheduled for Milestone 6")


def web_search(query: str) -> ActionResult:
    """Perform a web search in the default web browser."""
    raise NotImplementedError("Scheduled for Milestone 6")


def google_search(query: str) -> ActionResult:
    """Search Google in the default web browser."""
    raise NotImplementedError("Scheduled for Milestone 6")


def youtube_search(query: str) -> ActionResult:
    """Search YouTube in the default web browser."""
    raise NotImplementedError("Scheduled for Milestone 6")


def github_search(query: str) -> ActionResult:
    """Search GitHub in the default web browser."""
    raise NotImplementedError("Scheduled for Milestone 6")
