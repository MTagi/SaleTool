"""Single source of timestamps for sortable `created_at` values.

Why a separate module is needed for `datetime.now()`:

On Windows, `datetime.now()` reads a system clock with ~15.6 ms increments.
Measured on this project's development machine: **2,000 consecutive calls produced
only 2 distinct values**, with a run of 1,333 calls returning the same ISO string.
Records saved milliseconds apart are therefore very likely to share `created_at`.

This causes more than flaky tests: when timestamps match, `ORDER BY created_at DESC`
leaves ordering up to the database engine. The History page can be misordered, and
`/api/download` without `run_id` (which returns the "most recent run") can return
an older run.

The fix is to emit strictly increasing ISO strings. If the clock has not advanced
beyond the last value, add one microsecond. The maximum drift is one microsecond
per record written within a clock tick: imperceptible, but enough to make ordering
deterministic.

Fixing timestamps here avoids adding a tiebreaker column and works for **both**
backends: SQLite has `rowid`, but Mongo uses random UUIDs for `_id` and has no
insertion-order key to rely on.

The guarantee applies within **one process**. Multiple processes writing to the
same database can still collide. This is acceptable for an internal tool running
one server; SQLite's `rowid` remains a fallback tiebreaker.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

_ONE_MICROSECOND = timedelta(microseconds=1)

# Lock because FastAPI runs synchronous (`def`) routes in a thread pool, where two
# requests can enter this function concurrently.
_lock = threading.Lock()
_last: datetime | None = None


def now() -> datetime:
    """Return the current UTC time, strictly greater than every previously emitted value."""
    global _last

    with _lock:
        current = datetime.now(timezone.utc)
        if _last is not None and current <= _last:
            current = _last + _ONE_MICROSECOND
        _last = current
        return current


def now_iso() -> str:
    """Like `now()`, but return an ISO-8601 string, the format stored in the database."""
    return now().isoformat()
