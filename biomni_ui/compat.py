"""Small compatibility shims applied before the agent's tools are imported.

httpx 0.28 removed the `proxies=` argument of Client/AsyncClient (it is `proxy=` now). Several libraries the
tools depend on (scholarly, older SDKs) still pass `proxies=`, which fails with
"Client.__init__() got an unexpected keyword argument 'proxies'". Pinning httpx would risk the other packages,
so the old argument is translated instead.
"""

from __future__ import annotations

from typing import Any


def _translate(kwargs: dict[str, Any]) -> dict[str, Any]:
    if "proxies" not in kwargs:
        return kwargs
    kwargs = dict(kwargs)
    value = kwargs.pop("proxies")
    if isinstance(value, dict):
        # old style: {"http://": url, "https://": url} or {"http": url, "https": url}
        value = next((v for k, v in value.items() if str(k).startswith("https")), None) or next(iter(value.values()), None)
    if value and "proxy" not in kwargs and isinstance(value, str):
        kwargs["proxy"] = value
    return kwargs


def patch_httpx() -> bool:
    """Make httpx accept the removed `proxies=` argument. Returns True if a patch was applied."""
    import httpx

    if getattr(httpx.Client, "_biomni_proxies_shim", False):
        return False
    for cls in (httpx.Client, httpx.AsyncClient):
        original = cls.__init__

        def make(orig):
            def __init__(self, *args, **kwargs):
                orig(self, *args, **_translate(kwargs))

            return __init__

        cls.__init__ = make(original)
        cls._biomni_proxies_shim = True
    return True
