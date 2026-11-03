"""Interface for web search tools, used to find pages OUTSIDE the company
website (the company website itself does not need search; see discovery.py).

Like CompanyContactProvider, changing providers does not require pipeline edits.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class SearchResult(BaseModel):
    url: str
    title: str | None = None
    snippet: str | None = None


class SearchProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """Return a list of results. Raise if configuration is invalid or connection fails."""
