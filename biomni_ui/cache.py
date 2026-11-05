"""A small time-limited cache for database calls: the same question inside the window is answered from memory.

Used by the database helpers so a repeated lookup in one session does not hit the network twice. Entries expire after `ttl`
seconds; results that raised an exception are never cached.
"""

from __future__ import annotations

import functools
import threading
import time
from typing import Any, Callable

_LOCK = threading.Lock()
_STORE: dict[tuple[Any, ...], tuple[float, Any]] = {}


def ttl_cache(ttl: float = 3600.0, maxsize: int = 512) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def inner(*args: Any, **kwargs: Any) -> Any:
            key = (fn.__module__, fn.__qualname__, args, tuple(sorted(kwargs.items())))
            now = time.time()
            with _LOCK:
                hit = _STORE.get(key)
                if hit and now - hit[0] < ttl:
                    return hit[1]
            value = fn(*args, **kwargs)  # an exception propagates and nothing is stored
            with _LOCK:
                if len(_STORE) >= maxsize:
                    oldest = min(_STORE, key=lambda k: _STORE[k][0])
                    _STORE.pop(oldest, None)
                _STORE[key] = (now, value)
            return value

        inner.cache_clear = lambda: _STORE.clear()  # type: ignore[attr-defined]
        return inner

    return wrap
