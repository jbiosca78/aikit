from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Any, Deque, Dict, Tuple


def _positive_int(value: Any, default: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class ToolCallLimit:
    max_calls_per_request: int = 6

    @classmethod
    def from_config(cls, cfg: Dict[str, Any]) -> "ToolCallLimit":
        value = cfg.get("max_calls_per_request") if isinstance(cfg, dict) else None
        return cls(max_calls_per_request=_positive_int(value, 6))


@dataclass(frozen=True)
class RateLimitPolicy:
    window_seconds: int = 60
    anonymous_max_requests: int = 10
    authenticated_max_requests: int = 60

    @classmethod
    def from_config(cls, cfg: Dict[str, Any]) -> "RateLimitPolicy":
        policy = cfg.get("rate_limit", {}) if isinstance(cfg, dict) else {}
        if not isinstance(policy, dict):
            policy = {}
        return cls(
            window_seconds=_positive_int(policy.get("window_seconds"), 60),
            anonymous_max_requests=_positive_int(policy.get("anonymous_max_requests"), 10),
            authenticated_max_requests=_positive_int(policy.get("authenticated_max_requests"), 60),
        )


class RequestRateLimiter:
    """Limitador local de ventana deslizante por identidad resuelta."""

    def __init__(self, policy: RateLimitPolicy):
        self._policy = policy
        self._requests: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = RLock()

    def check(self, principal_id: str, authenticated: bool) -> Tuple[bool, int]:
        now = monotonic()
        limit = (
            self._policy.authenticated_max_requests
            if authenticated
            else self._policy.anonymous_max_requests
        )
        key = f"{'authenticated' if authenticated else 'anonymous'}:{principal_id}"
        with self._lock:
            requests = self._requests[key]
            while requests and now - requests[0] >= self._policy.window_seconds:
                requests.popleft()
            if len(requests) >= limit:
                retry_after = max(1, int(self._policy.window_seconds - (now - requests[0])))
                return False, retry_after
            requests.append(now)
        return True, 0
