"""Interface lưu trữ tài khoản và lịch sử tìm kiếm, độc lập với DB cụ thể.

Toàn bộ API/CLI chỉ nói chuyện qua interface này — muốn đổi từ SQLite sang
MongoDB (hoặc bất kỳ DB nào khác) chỉ cần viết thêm 1 implementation mới,
không phải sửa route hay logic auth/search.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from saletool.models import CompanyResult, SearchCriteria, SearchRunDetail, SearchRunSummary


class UserRepository(ABC):
    @abstractmethod
    def create_user(self, username: str, password_hash: str) -> None:
        """Tạo tài khoản mới. Raise ValueError nếu username đã tồn tại."""

    @abstractmethod
    def get_password_hash(self, username: str) -> str | None:
        """Trả về password hash đã lưu, hoặc None nếu không tìm thấy user."""


class SearchRunRepository(ABC):
    @abstractmethod
    def save_run(
        self,
        username: str,
        provider: str,
        criteria: SearchCriteria,
        results: list[CompanyResult],
    ) -> SearchRunSummary:
        """Lưu 1 lần chạy search, trả về summary (kèm id + created_at đã sinh)."""

    @abstractmethod
    def list_runs(self, username: str, limit: int = 20) -> list[SearchRunSummary]:
        """Liệt kê các lần search gần nhất của user, mới nhất trước."""

    @abstractmethod
    def get_run(self, username: str, run_id: str) -> SearchRunDetail | None:
        """Chi tiết đầy đủ (kèm results) 1 lần search. None nếu không tồn tại
        hoặc không thuộc về user này (không cho xem lịch sử của người khác)."""

    @abstractmethod
    def get_latest_run(self, username: str) -> SearchRunDetail | None:
        """Lần search gần nhất của user — dùng cho tải file khi không chỉ định run_id."""
