from saletool.enrichment.search.base import SearchProvider, SearchResult
from saletool.enrichment.search.providers import (
    BraveSearchProvider,
    ExaSearchProvider,
    NoSearchProvider,
    SearxngSearchProvider,
    SerperSearchProvider,
    TavilySearchProvider,
)
from saletool.models import SearchSettings

__all__ = ["SearchProvider", "SearchResult", "get_search_provider"]


def get_search_provider(settings: SearchSettings) -> SearchProvider:
    """Khởi tạo provider theo cấu hình đã lưu ở trang Settings."""
    provider = (settings.provider or "none").strip().lower()

    if provider == "none":
        return NoSearchProvider()
    if provider == "searxng":
        return SearxngSearchProvider(settings.searxng_url or "")
    if provider == "brave":
        return BraveSearchProvider(settings.api_key or "")
    if provider == "tavily":
        return TavilySearchProvider(settings.api_key or "")
    if provider == "exa":
        return ExaSearchProvider(settings.api_key or "")
    if provider == "serper":
        return SerperSearchProvider(settings.api_key or "")

    raise ValueError(f"Unsupported search provider: {provider}")
