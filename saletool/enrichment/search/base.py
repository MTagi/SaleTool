"""Interface cho công cụ web search — dùng để tìm các trang BÊN NGOÀI nói về
công ty (website của chính công ty thì không cần search, xem discovery.py).

Cùng mô hình với CompanyContactProvider: đổi nhà cung cấp không phải sửa
pipeline.
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
        """Trả về danh sách kết quả. Raise nếu cấu hình sai/không kết nối được."""
