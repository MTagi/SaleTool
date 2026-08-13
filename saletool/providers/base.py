"""Interface chung cho các nhà cung cấp dữ liệu công ty/liên hệ.

Lưu ý quan trọng: SaleTool KHÔNG tự động hoá trình duyệt để scrape trực tiếp
linkedin.com (vi phạm Terms of Service và có rủi ro pháp lý/khoá tài khoản).
Thay vào đó, mọi provider ở đây đều gọi API chính thức của các nhà cung cấp
dữ liệu bên thứ ba đã tổng hợp/enrich dữ liệu công khai một cách hợp pháp
(vd: Apollo.io, People Data Labs, Proxycurl...). Bạn cần tài khoản/API key
hợp lệ của provider tương ứng.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from saletool.models import Company, Contact, SearchCriteria


class CompanyContactProvider(ABC):
    """Provider phải cung cấp 2 khả năng: tìm công ty, và tìm liên hệ trong công ty đó."""

    name: str = "base"

    @abstractmethod
    def search_companies(self, criteria: SearchCriteria) -> list[Company]:
        """Trả về danh sách công ty phù hợp với criteria (tối đa criteria.max_companies)."""

    @abstractmethod
    def search_contacts(self, company: Company, criteria: SearchCriteria) -> list[Contact]:
        """Trả về danh sách liên hệ (ưu tiên cấp cao) của 1 công ty."""
