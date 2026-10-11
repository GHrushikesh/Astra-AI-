"""Web actions for Astra.

Provides deterministic web navigation and search queries launched
via the user's default browser without third-party scraping or API keys.

Functions:
- open_website(url: str) -> ActionResult
- web_search(query: str) -> ActionResult
- google_search(query: str) -> ActionResult
- youtube_search(query: str) -> ActionResult
- github_search(query: str) -> ActionResult
"""

from __future__ import annotations

from typing import Any, Optional, Tuple
import urllib.parse
import webbrowser

from actions.base import ActionResult, get_logger

logger = get_logger("astra.actions.web")

# Strictly allowed URL protocols for web navigation
ALLOWED_SCHEMES = {"http", "https"}


def _normalize_and_validate_url(raw_url: Any) -> Tuple[Optional[str], Optional[str]]:
    """Validate and normalize a URL, enforcing HTTPS and scheme safety.

    Args:
        raw_url: The URL or domain string to inspect.

    Returns:
        A tuple of (normalized_url, error_message).
    """
    if not isinstance(raw_url, str):
        return None, "URL must be a non-empty string."

    url = raw_url.strip()
    if not url:
        return None, "URL cannot be empty."

    # Inspect parsed components
    parsed = urllib.parse.urlparse(url)

    # If scheme is omitted (e.g. 'github.com' or 'www.google.com')
    if not parsed.scheme:
        # Check if the user passed something like 'javascript:alert(1)' or 'file:test'
        if ":" in url.split("/")[0]:
            candidate_scheme = url.split(":")[0].lower()
            if candidate_scheme not in ALLOWED_SCHEMES:
                return None, f"Disallowed or dangerous URL scheme: '{candidate_scheme}:'."
        url = f"https://{url}"
        parsed = urllib.parse.urlparse(url)

    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        return None, f"Disallowed URL scheme '{scheme}:'. Only http and https are permitted."

    if not parsed.netloc:
        return None, f"Invalid URL '{raw_url}': missing valid domain/host."

    return url, None


def open_website(url: str) -> ActionResult:
    """Open a validated web URL in the user's default browser.

    Automatically normalizes bare domains (e.g. 'github.com' -> 'https://github.com')
    and blocks non-HTTP/HTTPS schemes (e.g. file://, javascript:).

    Args:
        url: The web URL or domain to open.

    Returns:
        ActionResult with the final validated URL.
    """
    normalized_url, error_msg = _normalize_and_validate_url(url)
    if not normalized_url:
        logger.warning("Rejected invalid URL '%s': %s", url, error_msg)
        return ActionResult.fail(
            message=error_msg or "Invalid URL.",
            error="InvalidURL",
        )

    try:
        opened = webbrowser.open(normalized_url)
        if not opened:
            logger.warning("webbrowser.open returned False for '%s'", normalized_url)
            return ActionResult.fail(
                message=f"Failed to open default web browser for '{normalized_url}'.",
                error="BrowserOpenError",
            )

        logger.info("Opened URL '%s' in default browser", normalized_url)
        return ActionResult.ok(
            message=f"Opened website '{normalized_url}'.",
            data={
                "url": normalized_url,
                "original_input": url,
            },
        )
    except Exception as exc:
        logger.error("Error opening URL '%s': %s", normalized_url, exc)
        return ActionResult.fail(
            message=f"Error opening browser for '{normalized_url}': {exc}",
            error=str(exc),
        )


def _validate_query(raw_query: Any) -> Tuple[Optional[str], Optional[str]]:
    """Validate and clean a search query string."""
    if not isinstance(raw_query, str):
        return None, "Search query must be a string."
    cleaned = raw_query.strip()
    if not cleaned:
        return None, "Search query cannot be empty."
    return cleaned, None


def google_search(query: str) -> ActionResult:
    """Search Google in the user's default web browser.

    Args:
        query: Search keywords or query string.

    Returns:
        ActionResult containing search query and target URL.
    """
    clean_query, error_msg = _validate_query(query)
    if not clean_query:
        return ActionResult.fail(
            message=error_msg or "Invalid query.",
            error="InvalidInput",
        )

    encoded = urllib.parse.quote_plus(clean_query)
    url = f"https://www.google.com/search?q={encoded}"

    res = open_website(url)
    if not res.success:
        return res

    return ActionResult.ok(
        message=f"Opened Google search for '{clean_query}'.",
        data={"query": clean_query, "url": url},
    )


def web_search(query: str) -> ActionResult:
    """Perform a general web search in the user's default web browser.

    Delegates to the primary web search engine (Google).

    Args:
        query: Search keywords or query string.

    Returns:
        ActionResult containing search query and target URL.
    """
    clean_query, error_msg = _validate_query(query)
    if not clean_query:
        return ActionResult.fail(
            message=error_msg or "Invalid query.",
            error="InvalidInput",
        )

    return google_search(clean_query)


def youtube_search(query: str) -> ActionResult:
    """Search YouTube in the user's default web browser.

    Args:
        query: Video search query or keywords.

    Returns:
        ActionResult containing search query and YouTube search URL.
    """
    clean_query, error_msg = _validate_query(query)
    if not clean_query:
        return ActionResult.fail(
            message=error_msg or "Invalid query.",
            error="InvalidInput",
        )

    encoded = urllib.parse.quote_plus(clean_query)
    url = f"https://www.youtube.com/results?search_query={encoded}"

    res = open_website(url)
    if not res.success:
        return res

    return ActionResult.ok(
        message=f"Opened YouTube search for '{clean_query}'.",
        data={"query": clean_query, "url": url},
    )


def github_search(query: str) -> ActionResult:
    """Search GitHub repositories/code in the user's default web browser.

    Args:
        query: GitHub search query or repository name.

    Returns:
        ActionResult containing search query and GitHub search URL.
    """
    clean_query, error_msg = _validate_query(query)
    if not clean_query:
        return ActionResult.fail(
            message=error_msg or "Invalid query.",
            error="InvalidInput",
        )

    encoded = urllib.parse.quote_plus(clean_query)
    url = f"https://github.com/search?q={encoded}"

    res = open_website(url)
    if not res.success:
        return res

    return ActionResult.ok(
        message=f"Opened GitHub search for '{clean_query}'.",
        data={"query": clean_query, "url": url},
    )
