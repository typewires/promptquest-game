from __future__ import annotations

from dataclasses import dataclass
import time
from threading import Lock
from typing import Callable, Dict, Generic, Hashable, Optional, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class _Entry(Generic[T]):
    expires_at: float
    value: T


class TTLCache(Generic[T]):
    def __init__(self, *, default_ttl_seconds: int = 600, maxsize: int = 2048) -> None:
        self.default_ttl_seconds = default_ttl_seconds
        self.maxsize = maxsize
        self._lock = Lock()
        self._data: Dict[Hashable, _Entry[T]] = {}

    def get(self, key: Hashable) -> Optional[T]:
        now = time.time()
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._data.pop(key, None)
                return None
            return entry.value

    def set(self, key: Hashable, value: T, *, ttl_seconds: int | None = None) -> None:
        ttl = self.default_ttl_seconds if ttl_seconds is None else ttl_seconds
        expires_at = time.time() + max(0, ttl)
        with self._lock:
            if len(self._data) >= self.maxsize:
                self._evict_one_locked()
            self._data[key] = _Entry(expires_at=expires_at, value=value)

    def get_or_set(self, key: Hashable, compute: Callable[[], T], *, ttl_seconds: int | None = None) -> T:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = compute()
        self.set(key, value, ttl_seconds=ttl_seconds)
        return value

    def _evict_one_locked(self) -> None:
        now = time.time()
        expired_keys = [k for k, v in self._data.items() if v.expires_at <= now]
        for k in expired_keys:
            self._data.pop(k, None)
            if len(self._data) < self.maxsize:
                return
        if not self._data:
            return
        oldest_key = min(self._data.items(), key=lambda kv: kv[1].expires_at)[0]
        self._data.pop(oldest_key, None)
