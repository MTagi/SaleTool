"""Data models dùng chung cho toàn bộ pipeline."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

# Các mức seniority thường gặp (khớp với cách Apollo.io/PDL phân loại),
# dùng để lọc "các cấp cao" của công ty.
SENIORITY_LEVELS = [
    "owner",
    "founder",
    "c_suite",
    "partner",
    "vp",
    "head",
    "director",
    "manager",
    "senior",
    "entry",
    "intern",
]

DEFAULT_SENIOR_LEVELS = ["owner", "founder", "c_suite", "partner", "vp", "head", "director"]


class SearchCriteria(BaseModel):
    """Input format mô tả mục tiêu tìm kiếm công ty.

    Đây chính là "1 input format" mà người dùng cung cấp để tool tìm ra
    danh sách công ty phù hợp trên LinkedIn.
    """

    industries: list[str] = Field(default_factory=list, description="Ngành nghề, vd: 'Software', 'Retail'")
    keywords: list[str] = Field(default_factory=list, description="Từ khoá mô tả công ty/lĩnh vực kinh doanh")
    locations: list[str] = Field(default_factory=list, description="Vị trí địa lý, vd: 'Vietnam', 'Ho Chi Minh City'")
    company_size_min: Optional[int] = Field(default=None, ge=0)
    company_size_max: Optional[int] = Field(default=None, ge=0)
    target_titles: list[str] = Field(
        default_factory=list, description="Chức danh cụ thể muốn tìm, vd: 'CEO', 'Head of Sales'"
    )
    seniority_levels: list[str] = Field(
        default_factory=lambda: list(DEFAULT_SENIOR_LEVELS),
        description="Các cấp bậc liên hệ muốn lấy ra (mặc định: các cấp quản lý cao trở lên)",
    )
    max_companies: int = Field(default=20, gt=0, description="Số lượng công ty tối đa cần tìm")
    max_contacts_per_company: int = Field(default=5, gt=0, description="Số liên hệ tối đa lấy ra mỗi công ty")


class Company(BaseModel):
    name: str
    linkedin_url: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    employee_count: Optional[int] = None
    provider_id: Optional[str] = Field(default=None, description="ID nội bộ của nhà cung cấp dữ liệu")


class Contact(BaseModel):
    full_name: str
    title: Optional[str] = None
    seniority: Optional[str] = None
    linkedin_url: Optional[str] = None
    email: Optional[str] = None
    company_name: Optional[str] = None


class CompanyResult(BaseModel):
    """Kết quả cuối cùng: 1 công ty phù hợp kèm danh sách liên hệ cấp cao tìm được."""

    company: Company
    contacts: list[Contact] = Field(default_factory=list)


class SearchRunSummary(BaseModel):
    """1 dòng lịch sử tìm kiếm — đủ thông tin để hiển thị danh sách, chưa kèm
    kết quả đầy đủ (xem SearchRunDetail)."""

    id: str = Field(description="UUID, dùng để tra lại chi tiết/tải file")
    username: str
    created_at: str = Field(description="ISO 8601 UTC, vd: 2026-08-13T10:00:00+00:00")
    provider: str
    criteria: SearchCriteria
    total_companies: int
    total_contacts: int


class SearchRunDetail(SearchRunSummary):
    """1 lần tìm kiếm kèm đầy đủ kết quả — dùng khi xem lại 1 lần chạy trong lịch sử."""

    results: list[CompanyResult] = Field(default_factory=list)

