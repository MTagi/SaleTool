"""Mã hoá các giá trị nhạy cảm (API key) trước khi lưu xuống DB.

Phạm vi bảo vệ — nói rõ để không hiểu nhầm: lớp này bảo vệ khỏi việc **lộ tình
cờ** (file DB bị commit nhầm, bản backup bị copy đi, ai đó mở file .db bằng
trình xem SQLite). Nó **không** bảo vệ được nếu server đã bị chiếm quyền, vì khoá
giải mã được suy ra từ SALETOOL_SECRET_KEY nằm ngay trên máy đó.

Khoá được suy ra từ SALETOOL_SECRET_KEY bằng HKDF, nên đổi secret key sẽ làm mọi
giá trị đã mã hoá không giải được nữa (người dùng phải nhập lại API key).
"""

from __future__ import annotations

import base64
import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)

_PREFIX = "enc:v1:"
_INFO = b"saletool-settings-encryption-v1"


def _fernet() -> Fernet:
    secret = os.environ.get("SALETOOL_SECRET_KEY")
    if not secret:
        # Không tự sinh khoá ngẫu nhiên ở đây: nếu làm vậy, mọi lần restart sẽ
        # sinh khoá mới và toàn bộ API key đã lưu thành rác không giải được.
        raise RuntimeError(
            "Cần đặt SALETOOL_SECRET_KEY để lưu API key an toàn. "
            "Sinh khoá: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=_INFO,
    ).derive(secret.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt(value: str | None) -> str | None:
    """Mã hoá 1 chuỗi. Trả về None nếu đầu vào rỗng."""
    if not value:
        return None
    if value.startswith(_PREFIX):
        return value  # đã mã hoá rồi, tránh mã hoá 2 lần
    token = _fernet().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{_PREFIX}{token}"


def decrypt(value: str | None) -> str | None:
    """Giải mã. Trả về None nếu rỗng hoặc không giải được (vd: đổi secret key)."""
    if not value:
        return None
    if not value.startswith(_PREFIX):
        # Giá trị lưu từ trước khi bật mã hoá — trả nguyên, để lần lưu sau tự nâng cấp.
        return value

    token = value[len(_PREFIX) :]
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, RuntimeError):
        logger.warning(
            "Không giải mã được giá trị đã lưu — nhiều khả năng SALETOOL_SECRET_KEY đã đổi. "
            "Người dùng cần nhập lại API key trong trang Settings."
        )
        return None


def mask(value: str | None) -> str | None:
    """Tạo bản hiển thị an toàn để trả về frontend: chỉ lộ 4 ký tự cuối."""
    if not value:
        return None
    if len(value) <= 4:
        return "•" * len(value)
    return "•" * 8 + value[-4:]
