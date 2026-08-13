"""Interface lưu trữ tài khoản, độc lập với DB cụ thể.

Toàn bộ API/CLI chỉ nói chuyện qua interface này — muốn đổi từ SQLite sang
MongoDB (hoặc bất kỳ DB nào khác) chỉ cần viết thêm 1 implementation mới,
không phải sửa route hay logic auth.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class UserRepository(ABC):
    @abstractmethod
    def create_user(self, username: str, password_hash: str) -> None:
        """Tạo tài khoản mới. Raise ValueError nếu username đã tồn tại."""

    @abstractmethod
    def get_password_hash(self, username: str) -> str | None:
        """Trả về password hash đã lưu, hoặc None nếu không tìm thấy user."""
