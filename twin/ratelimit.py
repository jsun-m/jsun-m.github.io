"""In-memory rate limiting. Per-container and reset on cold start — acceptable
at portfolio scale; swap for Redis/a Beam volume if it ever matters (v2)."""

import time
from collections import defaultdict, deque

PER_MINUTE = 4
PER_HOUR = 20
GLOBAL_PER_DAY = 500  # runaway-cost fuse across all callers

_hits: dict[str, deque] = defaultdict(deque)
_global_hits: deque = deque()


def client_ip(headers, fallback: str) -> str:
    fwd = headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else fallback


def check(ip: str) -> str | None:
    """Record a hit; return an error string if over a limit, else None."""
    now = time.monotonic()

    while _global_hits and now - _global_hits[0] > 86_400:
        _global_hits.popleft()
    if len(_global_hits) >= GLOBAL_PER_DAY:
        return "the twin is over its daily budget — try again tomorrow"

    q = _hits[ip]
    while q and now - q[0] > 3_600:
        q.popleft()
    if len(q) >= PER_HOUR:
        return "hourly limit reached — come back in a bit"
    if sum(1 for t in q if now - t < 60) >= PER_MINUTE:
        return "throttled — try again in a minute"

    q.append(now)
    _global_hits.append(now)
    return None
