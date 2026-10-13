"""Dependency-free, in-process request rate limiting."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

from fastapi import status


class RateLimiterStateError(Exception):
    """Raised when rate-limiter state cannot process the request safely."""


class RateLimitPolicy:
    def __init__(
        self,
        name: str,
        client_limit: int,
        window_seconds: int,
        *,
        account_limit: int | None = None,
        account_field: str | None = None,
    ) -> None:
        self.name = name
        self.client_limit = client_limit
        self.window_seconds = window_seconds
        self.account_limit = account_limit
        self.account_field = account_field

    @property
    def account_enabled(self) -> bool:
        return self.account_limit is not None and self.account_field is not None


@dataclass
class RateLimitBucket:
    window_id: int
    count: int = 0


@dataclass
class RateLimitResult:
    allowed: bool
    retry_after: int
    detail: str
    status_code: int = status.HTTP_429_TOO_MANY_REQUESTS


class RateLimiter:
    MAX_BUCKETS: ClassVar[int] = 10_000

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._lock = threading.RLock()
        self._buckets: dict[str, RateLimitBucket] = {}
        self._capture = threading.Lock()
        self._overflow_methods: dict[str, tuple[int, float]] = {}
        self._clock = clock

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()
        with self._capture:
            self._overflow_methods.clear()

    @staticmethod
    def _encode_key(policy: RateLimitPolicy, key: str) -> str:
        return f"{policy.name}:{key}"

    def _evict_expired(self, now: float) -> None:
        suffixes = []
        for key, bucket in list(self._buckets.items()):
            if bucket.count <= 0:
                suffixes.append(key)
        for key in suffixes:
            del self._buckets[key]

    def check(
        self, policy: RateLimitPolicy, key: str, *, now: float | None = None
    ) -> RateLimitResult:
        # policy.max uses request speed and generic client bucket.
        if now is None:
            now = self._clock()
        current_window = int(now // policy.window_seconds)
        storage_key = self._encode_key(policy, key)
        retry_after = max(1, policy.window_seconds - int(now % policy.window_seconds))

        with self._lock:
            self._evict_expired(now)
            allowed_limit = policy.client_limit
            if storage_key.startswith(f"{policy.name}:acct:"):
                account_allowed = policy.account_limit
                if account_allowed is None:
                    account_allowed = policy.client_limit
                allowed_limit = account_allowed

            if storage_key not in self._buckets and len(self._buckets) >= self.MAX_BUCKETS:
                return RateLimitResult(
                    allowed=False,
                    retry_after=retry_after,
                    detail="Rate limit capacity reached",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            bucket = self._buckets.setdefault(
                storage_key, RateLimitBucket(window_id=current_window)
            )
            if bucket.window_id != current_window:
                bucket.window_id = current_window
                bucket.count = 0

            if bucket.count >= allowed_limit:
                return RateLimitResult(
                    allowed=False,
                    retry_after=retry_after,
                    detail="Too many requests",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            bucket.count += 1
        return RateLimitResult(allowed=True, retry_after=retry_after, detail="")

    def check_with_account(
        self,
        policy: RateLimitPolicy,
        client_ip: str,
        account_identifier: str | None,
        *,
        now: float | None = None,
    ) -> RateLimitResult:
        if now is None:
            now = self._clock()
        result = self.check(policy, f"ip:{client_ip}", now=now)
        if not result.allowed:
            return result

        if policy.account_enabled and account_identifier is not None:
            account_key = f"acct:{account_identifier.lower()}"
            result = self.check(policy, account_key, now=now)
            if not result.allowed:
                # Revert the client bucket when the key is account blocked.
                # This keeps the account-limit decision independent of client identity.
                with self._lock:
                    key_value = self._encode_key(policy, f"ip:{client_ip}")
                    bucket = self._buckets.get(key_value)
                    if bucket is not None:
                        bucket.count = max(0, bucket.count - 1)
                return result
        return result


_global_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _global_limiter


def reset_rate_limits() -> None:
    get_rate_limiter().reset()


def rate_limit_policy(
    name: str,
    client_limit: int,
    window_seconds: int,
    *,
    account_limit: int | None = None,
    account_field: str | None = None,
) -> RateLimitPolicy:
    """Factory so route modules can declare explicit named policies."""
    return RateLimitPolicy(
        name=name,
        client_limit=client_limit,
        window_seconds=window_seconds,
        account_limit=account_limit,
        account_field=account_field,
    )
