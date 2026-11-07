"""
Web Search Tool
Robust multi-backend search with automatic fallbacks for cloud environments.
"""
import logging
import re
import urllib.parse
from typing import TypedDict
import httpx
from ddgs import DDGS

logger = logging.getLogger(__name__)


class SearchResult(TypedDict):
    title: str
    url: str
    snippet: str


def _clean_query(query: str) -> str:
    """Cleans punctuation, quotes, and noise from search query."""
    cleaned = re.sub(r'["\'\(\)\[\]\{\}]', '', query)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def _fallback_httpx_search(query: str, max_results: int = 4) -> list[SearchResult]:
    """
    Direct HTTP fallback to DuckDuckGo HTML endpoint with standard browser headers.
    Used if DDGS library encounters rate limits or datacenter IP blocks.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    try:
        resp = httpx.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers=headers,
            timeout=8.0,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return []

        html = resp.text
        results: list[SearchResult] = []

        # Simple regex extraction of DuckDuckGo HTML results (avoids heavy bs4 dependency)
        # Matches result links and snippets
        link_matches = re.findall(
            r'<a class="result__url" href="([^"]+)">\s*([^<]+)\s*</a>.*?<a class="result__snippet[^"]*"[^>]*>(.*?)</a>',
            html,
            re.DOTALL,
        )
        for href, title, snippet in link_matches[:max_results]:
            # Clean DuckDuckGo redirect url if needed
            clean_url = href.strip()
            if "uddg=" in clean_url:
                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(clean_url).query)
                clean_url = parsed.get("uddg", [clean_url])[0]

            clean_snippet = re.sub(r'<[^>]+>', '', snippet).strip()
            clean_title = re.sub(r'<[^>]+>', '', title).strip()

            if clean_url and (clean_title or clean_snippet):
                results.append(SearchResult(title=clean_title, url=clean_url, snippet=clean_snippet))

        return results
    except Exception as e:
        logger.warning("Fallback HTTP search failed for '%s': %s", query, e)
        return []


def search_web(query: str, max_results: int = 4) -> list[SearchResult]:
    """
    Execute a robust web search with automatic retry across backends ('lite', 'auto', and HTTP fallback).
    """
    clean_q = _clean_query(query)
    logger.info("Executing web search: '%s'", clean_q)

    # Attempt 1: DDGS with 'lite' backend (most reliable on cloud datacenter IPs)
    try:
        with DDGS(timeout=8) as ddgs:
            raw = list(ddgs.text(clean_q, backend="lite", max_results=max_results))
            if raw:
                results = []
                for item in raw:
                    t = item.get("title", "").strip()
                    u = item.get("href", "").strip()
                    s = item.get("body", "").strip()
                    if u and (t or s):
                        results.append(SearchResult(title=t, url=u, snippet=s))
                if results:
                    logger.info("Found %d results via DDGS lite for: '%s'", len(results), clean_q)
                    return results
    except Exception as exc:
        logger.debug("DDGS lite backend error for '%s': %s", clean_q, exc)

    # Attempt 2: DDGS with 'auto' backend
    try:
        with DDGS(timeout=8) as ddgs:
            raw = list(ddgs.text(clean_q, backend="auto", max_results=max_results))
            if raw:
                results = []
                for item in raw:
                    t = item.get("title", "").strip()
                    u = item.get("href", "").strip()
                    s = item.get("body", "").strip()
                    if u and (t or s):
                        results.append(SearchResult(title=t, url=u, snippet=s))
                if results:
                    logger.info("Found %d results via DDGS auto for: '%s'", len(results), clean_q)
                    return results
    except Exception as exc:
        logger.debug("DDGS auto backend error for '%s': %s", clean_q, exc)

    # Attempt 3: Direct HTTP fallback
    logger.info("Falling back to direct HTTP search for: '%s'", clean_q)
    fallback_results = _fallback_httpx_search(clean_q, max_results=max_results)
    if fallback_results:
        logger.info("Found %d results via HTTP fallback for: '%s'", len(fallback_results), clean_q)
        return fallback_results

    logger.warning("All search methods returned 0 results for: '%s'", clean_q)
    return []
