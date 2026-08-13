"""Interface lưu trữ tài khoản và lịch sử tìm kiếm, độc lập với DB cụ thể.

Toàn bộ API/CLI chỉ nói chuyện qua interface này — muốn đổi từ SQLite sang
MongoDB (hoặc bất kỳ DB nào khác) chỉ cần viết thêm 1 implementation mới,
không phải sửa route hay logic auth/search.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from saletool.models import (
    AppSettings,
    CompanyResult,
    EnrichJobDetail,
    EnrichJobSummary,
    SearchCriteria,
    SearchRunDetail,
    SearchRunSummary,
)


class UserRepository(ABC):
    @abstractmethod
    def create_user(self, username: str, password_hash: str) -> None:
        """Tạo tài khoản mới. Raise ValueError nếu username đã tồn tại."""

    @abstractmethod
    def get_password_hash(self, username: str) -> str | None:
        """Trả về password hash đã lưu, hoặc None nếu không tìm thấy user."""

    @abstractmethod
    def update_password_hash(self, username: str, password_hash: str) -> None:
        """Cập nhật password hash cho user đã tồn tại. Raise ValueError nếu không tìm thấy."""


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


class SettingsRepository(ABC):
    """Cấu hình phạm vi toàn hệ thống (1 bản ghi duy nhất), không per-user.

    API key được lưu ở dạng đã mã hoá — xem saletool/crypto.py.
    """

    @abstractmethod
    def get_settings(self) -> AppSettings:
        """Trả về cấu hình hiện tại (kèm API key đã giải mã). Trả về mặc định nếu chưa từng lưu."""

    @abstractmethod
    def save_settings(self, settings: AppSettings, updated_by: str) -> AppSettings:
        """Ghi đè cấu hình. Trả về bản đã lưu (kèm updated_at/updated_by)."""


class EnrichJobRepository(ABC):
    """Lưu trạng thái các job enrich chạy nền."""

    @abstractmethod
    def create_job(self, job: EnrichJobDetail) -> None:
        """Tạo bản ghi job mới."""

    @abstractmethod
    def update_job(self, job: EnrichJobDetail) -> None:
        """Ghi đè trạng thái job (dùng để cập nhật tiến độ)."""

    @abstractmethod
    def get_job(self, username: str, job_id: str) -> EnrichJobDetail | None:
        """Chi tiết 1 job. None nếu không tồn tại hoặc không thuộc user này."""

    @abstractmethod
    def list_jobs(self, username: str, limit: int = 20) -> list[EnrichJobSummary]:
        """Các job gần nhất của user, mới nhất trước."""
