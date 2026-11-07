"""
Web Search Tool
Wraps DuckDuckGo Search (via ddgs) to provide 100% free web search.
"""
import logging
from typing import TypedDict
from ddgs import DDGS

logger = logging.getLogger(__name__)


class SearchResult(TypedDict):
    title: str
    url: str
    snippet: str


def search_web(query: str, max_results: int = 4) -> list[SearchResult]:
    """
    Execute a DuckDuckGo web search for a single query.
    Returns cleaned list of SearchResult dictionaries.
    """
    logger.info("Executing web search: %s", query)
    try:
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results))
            
        results: list[SearchResult] = []
        for item in raw_results:
            title = item.get("title", "").strip()
            url = item.get("href", "").strip()
            snippet = item.get("body", "").strip()
            if url and (title or snippet):
                results.append(SearchResult(title=title, url=url, snippet=snippet))

        logger.info("Found %d search results for: %s", len(results), query)
        return results

    except Exception as exc:
        logger.warning("Search query failed for '%s': %s", query, exc)
        return []
