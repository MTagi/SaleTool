from saletool.enrichment.search.base import SearchProvider, SearchResult
from saletool.enrichment.search.providers import (
    BraveSearchProvider,
    CodexSearchProvider,
    ExaSearchProvider,
    NoSearchProvider,
    SerperSearchProvider,
    TavilySearchProvider,
)
from saletool.models import SearchSettings

__all__ = ["SearchProvider", "SearchResult", "get_search_provider"]


def get_search_provider(settings: SearchSettings) -> SearchProvider:
    """Create a provider from the configuration saved in Settings."""
    provider = (settings.provider or "none").strip().lower()

    if provider == "none":
        return NoSearchProvider()
    if provider == "brave":
        return BraveSearchProvider(settings.api_key or "")
    if provider == "tavily":
        return TavilySearchProvider(settings.api_key or "")
    if provider == "exa":
        return ExaSearchProvider(settings.api_key or "")
    if provider == "serper":
        return SerperSearchProvider(settings.api_key or "")
    if provider == "codex":
        # All three values may be empty: base_url/model default to local 9Router,
        # while api_key is only needed when 9Router enables REQUIRE_API_KEY.
        return CodexSearchProvider(settings.base_url, settings.model, settings.api_key)

    raise ValueError(f"Unsupported search provider: {provider}")
