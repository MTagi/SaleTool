"""Nguồn thời gian duy nhất cho các mốc `created_at` được dùng để sắp xếp.

Vì sao cần cả một module cho việc gọi `datetime.now()`:

`datetime.now()` trên Windows lấy giờ từ đồng hồ hệ thống có bước nhảy ~15,6ms.
Đo trên chính máy dev của dự án: **2000 lần gọi liên tiếp chỉ ra 2 giá trị khác
nhau**, có nhóm 1333 lần cho ra đúng cùng một chuỗi ISO. Nên hai bản ghi lưu
cách nhau vài mili-giây gần như chắc chắn mang `created_at` y hệt.

Hậu quả không chỉ là test chớp tắt: `ORDER BY created_at DESC` khi hai dòng
bằng nhau thì thứ tự do engine tự quyết — trang History có thể xếp sai, và
`/api/download` không kèm `run_id` (lấy "lần chạy gần nhất") có thể trả về đúng
cái cũ hơn.

Cách xử lý: phát ra chuỗi ISO **tăng nghiêm ngặt**. Nếu đồng hồ chưa nhích qua
giá trị vừa phát, cộng thêm 1 micro-giây. Sai số tối đa bằng số bản ghi ghi
trong một tick (micro-giây), không ai nhìn thấy được, nhưng đủ để thứ tự trở
nên xác định.

Sửa ở đây thay vì thêm cột tiebreaker vì đó là cách duy nhất chữa được **cả
hai** backend: SQLite còn có `rowid` để bấu víu, còn Mongo dùng `_id` là UUID
ngẫu nhiên nên không có khoá nào mang thứ tự chèn.

Giới hạn cần biết: đơn điệu trong phạm vi **một tiến trình**. Chạy nhiều tiến
trình cùng ghi vào một DB thì vẫn có thể trùng — chấp nhận được với một tool
nội bộ chạy một server, và với SQLite thì tiebreaker `rowid` vẫn đỡ được.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

_ONE_MICROSECOND = timedelta(microseconds=1)

# Khoá vì FastAPI chạy route `def` (không async) trong threadpool — hai request
# có thể vào đây cùng lúc thật.
_lock = threading.Lock()
_last: datetime | None = None


def now() -> datetime:
    """Giờ UTC hiện tại, đảm bảo lớn hơn nghiêm ngặt mọi giá trị đã phát trước đó."""
    global _last

    with _lock:
        current = datetime.now(timezone.utc)
        if _last is not None and current <= _last:
            current = _last + _ONE_MICROSECOND
        _last = current
        return current


def now_iso() -> str:
    """Như `now()` nhưng trả chuỗi ISO-8601 — dạng đang lưu trong DB."""
    return now().isoformat()
