"""Đồng hồ phát mốc thời gian tăng nghiêm ngặt.

Bài test này tồn tại vì `datetime.now()` KHÔNG đủ: trên Windows, 2000 lần gọi
liên tiếp chỉ cho ra 2 giá trị khác nhau. Xem saletool/clock.py.
"""

from datetime import datetime, timezone

from saletool.clock import now, now_iso


def test_consecutive_calls_are_strictly_increasing():
    stamps = [now() for _ in range(5000)]

    assert stamps == sorted(stamps)
    assert len(set(stamps)) == len(stamps), "có hai mốc trùng nhau"


def test_plain_datetime_now_really_does_collide():
    """Chốt lại lý do module clock tồn tại.

    Nếu một ngày nào đó `datetime.now()` đủ mịn trên mọi nền tảng thì test này
    fail — và đó là tín hiệu để xem lại có còn cần clock.py nữa không, chứ
    không phải lỗi.
    """
    raw = [datetime.now(timezone.utc) for _ in range(2000)]

    assert len(set(raw)) < len(raw), (
        "datetime.now() không còn trùng lặp — kiểm tra lại xem clock.py có còn cần thiết"
    )


def test_iso_output_still_parses_as_utc():
    """Đơn điệu không được đánh đổi bằng việc làm hỏng định dạng đang lưu trong DB."""
    text = now_iso()

    parsed = datetime.fromisoformat(text)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_stays_close_to_the_real_clock():
    """Cộng dồn micro-giây không được trôi xa giờ thật."""
    before = datetime.now(timezone.utc)
    for _ in range(10000):
        now()
    issued = now()

    drift = abs((issued - before).total_seconds())
    assert drift < 1.0, f"lệch {drift}s so với đồng hồ thật"
