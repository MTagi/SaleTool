"""Clock that emits strictly increasing timestamps.

These tests exist because `datetime.now()` is NOT precise enough: on Windows,
2,000 consecutive calls produced only two distinct values. See saletool/clock.py.
"""

from datetime import datetime, timezone

from saletool.clock import now, now_iso


def test_consecutive_calls_are_strictly_increasing():
    stamps = [now() for _ in range(5000)]

    assert stamps == sorted(stamps)
    assert len(set(stamps)) == len(stamps), "two timestamps are identical"


def test_plain_datetime_now_really_does_collide():
    """Document why the clock module exists.

    If `datetime.now()` becomes precise enough on all platforms, this test will
    fail. That is a signal to reconsider whether clock.py is still needed, not a bug.
    """
    raw = [datetime.now(timezone.utc) for _ in range(2000)]

    assert len(set(raw)) < len(raw), (
        "datetime.now() no longer produces duplicates — reconsider whether clock.py is still needed"
    )


def test_iso_output_still_parses_as_utc():
    """Monotonicity must not break the timestamp format stored in the database."""
    text = now_iso()

    parsed = datetime.fromisoformat(text)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_stays_close_to_the_real_clock():
    """Accumulated microseconds must not drift far from the actual time."""
    before = datetime.now(timezone.utc)
    for _ in range(10000):
        now()
    issued = now()

    drift = abs((issued - before).total_seconds())
    assert drift < 1.0, f"{drift}s drift from the actual clock"
