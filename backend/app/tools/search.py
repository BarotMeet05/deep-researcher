"""
Web Search Tool
Supports Tavily AI Search (primary) with resilient multi-tier DuckDuckGo fallback.
"""
import logging
import re
import urllib.parse
from typing import TypedDict
import httpx
from ddgs import DDGS
from app.config import get_settings

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


def _search_tavily(query: str, api_key: str, max_results: int = 4) -> list[SearchResult]:
    """
    Executes search via Tavily AI Search REST API.
    Returns clean, fact-dense snippets optimized for LLMs.
    """
    logger.info("Executing Tavily AI search for: '%s'", query)
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": False,
    }
    try:
        resp = httpx.post(url, json=payload, timeout=10.0)
        if resp.status_code == 200:
            data = resp.json()
            raw_results = data.get("results", [])
            results: list[SearchResult] = []
            for item in raw_results:
                t = item.get("title", "").strip()
                u = item.get("url", "").strip()
                c = item.get("content", "").strip()
                if u and (t or c):
                    results.append(SearchResult(title=t, url=u, snippet=c))
            if results:
                logger.info("Found %d high-precision results via Tavily for: '%s'", len(results), query)
                return results
        else:
            logger.warning("Tavily search returned status %d: %s", resp.status_code, resp.text)
    except Exception as exc:
        logger.warning("Tavily search request error for '%s': %s", query, exc)

    return []


def _fallback_httpx_search(query: str, max_results: int = 4) -> list[SearchResult]:
    """
    Direct HTTP fallback to DuckDuckGo HTML endpoint with standard browser headers.
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

        link_matches = re.findall(
            r'<a class="result__url" href="([^"]+)">\s*([^<]+)\s*</a>.*?<a class="result__snippet[^"]*"[^>]*>(.*?)</a>',
            html,
            re.DOTALL,
        )
        for href, title, snippet in link_matches[:max_results]:
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
    Unified search entrypoint:
    1. Attempts Tavily AI search if TAVILY_API_KEY is configured.
    2. Falls back to DuckDuckGo multi-engine ('lite', 'auto', HTTP) if Tavily is absent or fails.
    """
    clean_q = _clean_query(query)
    settings = get_settings()

    # 1. Tavily AI Search (Primary if key exists)
    if settings.tavily_api_key and settings.tavily_api_key.strip():
        tavily_results = _search_tavily(clean_q, settings.tavily_api_key.strip(), max_results=max_results)
        if tavily_results:
            return tavily_results
        logger.info("Tavily search yielded 0 results; engaging DuckDuckGo fallback for: '%s'", clean_q)

    logger.info("Executing DuckDuckGo web search: '%s'", clean_q)

    # 2. DuckDuckGo 'lite' backend
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
                    return results
    except Exception as exc:
        logger.debug("DDGS lite backend error for '%s': %s", clean_q, exc)

    # 3. DuckDuckGo 'auto' backend
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
                    return results
    except Exception as exc:
        logger.debug("DDGS auto backend error for '%s': %s", clean_q, exc)

    # 4. Direct HTTP scraper fallback
    fallback_results = _fallback_httpx_search(clean_q, max_results=max_results)
    if fallback_results:
        return fallback_results

    logger.warning("All search engines returned 0 results for query: '%s'", clean_q)
    return []
