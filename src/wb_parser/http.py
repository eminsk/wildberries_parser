"""
Resilient HTTP Transport Layer for Wildberries SDK (Sync & Async).

Features:
- Chrome TLS/HTTP2 fingerprinting via `curl_cffi` with transparent fallback to `httpx`.
- Forced IPv4 routing (`CURLOPT_IPRESOLVE_V4` / `local_address='0.0.0.0'`) to avoid
  stalled CDN IPv6 routes observed on Windows.
- Exponential backoff with jitter for 429 / 5xx / transient CDN timeouts.
- Proxy support (HTTP / SOCKS5) and optional MobileProxy.space rotation trigger.
- Clean classification of WBAAS gateway blocks (498 / 403) without attempting PoW bypasses.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from wb_parser.exceptions import (
    WBAntiBotError,
    WBNetworkError,
    WBNotFoundError,
    WBRateLimitError,
)

try:
    from curl_cffi import requests as cffi_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:  # pragma: no cover
    cffi_requests = None
    CURL_CFFI_AVAILABLE = False

logger = logging.getLogger("wb_parser.http")

# libcurl option constants for IPv4 preference and fast connect failover
_CURLOPT_IPRESOLVE = 113
_CURL_IPRESOLVE_V4 = 1
_CURLOPT_CONNECTTIMEOUT_MS = 156

DEFAULT_HEADERS: Dict[str, str] = {
    "Accept": "*/*",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://www.wildberries.ru",
    "Referer": "https://www.wildberries.ru/",
}


def parse_cookie_header(cookie_str: Optional[str]) -> Dict[str, str]:
    """Parse a raw HTTP Cookie header string into a dict."""
    if not cookie_str or not cookie_str.strip():
        return {}
    cookies: Dict[str, str] = {}
    for part in cookie_str.split(";"):
        if "=" in part:
            key, val = part.split("=", 1)
            key = key.strip()
            if key:
                cookies[key] = val.strip()
    return cookies


@dataclass
class HttpResponse:
    """Normalized HTTP response wrapper independent of backend transport."""

    status_code: int
    text: str
    content: bytes
    headers: Dict[str, str]

    def json(self) -> Any:
        import json
        return json.loads(self.content.decode("utf-8"))


class BaseWBTransport:
    """Shared header, status handling, and retry calculation logic."""

    def __init__(
        self,
        *,
        proxy: Optional[str] = None,
        proxy_change_url: Optional[str] = None,
        cookies: Optional[str] = None,
        wbaas_token: Optional[str] = None,
        timeout: float = 12.0,
        max_retries: int = 3,
        force_ipv4: bool = True,
        impersonate: str = "chrome124",
    ) -> None:
        self.proxy = proxy.strip() if proxy and proxy.strip() else None
        self.proxy_change_url = (
            proxy_change_url.strip() if proxy_change_url and proxy_change_url.strip() else None
        )
        self.cookies_dict = parse_cookie_header(cookies)
        self.wbaas_token = wbaas_token.strip() if wbaas_token and wbaas_token.strip() else None
        if self.wbaas_token:
            self.cookies_dict.setdefault("x_wbaas_token", self.wbaas_token)
        self.timeout = float(timeout)
        self.max_retries = max(1, int(max_retries))
        self.force_ipv4 = bool(force_ipv4)
        self.impersonate = impersonate

    def build_headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = dict(DEFAULT_HEADERS)
        if not CURL_CFFI_AVAILABLE:
            headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            )
        if self.wbaas_token:
            headers["x-wbaas-token"] = self.wbaas_token
        if extra:
            headers.update(extra)
        return headers

    def _raise_for_status(self, resp: HttpResponse, url: str) -> None:
        code = resp.status_code
        if code == 404:
            raise WBNotFoundError(f"Resource not found (404): {url}")
        if code in (429, 439):
            raise WBRateLimitError(f"Wildberries rate limit HTTP {code} at {url}")
        if code in (498, 403):
            server = resp.headers.get("server", "")
            hint = (
                "WBAAS protection (498/403). Supply a residential/mobile RU proxy "
                "or valid browser cookies / x-wbaas-token."
            )
            raise WBAntiBotError(
                f"HTTP {code} ({server or 'WAF'}) blocked {url}. {hint}",
                status_code=code,
                url=url,
            )
        if code >= 500:
            raise WBNetworkError(f"Wildberries upstream server error {code} at {url}")
        if code >= 400:
            raise WBNetworkError(f"HTTP error {code} at {url}")

    def _backoff(self, attempt: int) -> float:
        return min(8.0, (0.6 * (2 ** attempt)) + random.uniform(0.15, 0.55))

    def _cffi_kwargs(self) -> Dict[str, Any]:
        """Build shared keyword arguments for `curl_cffi` Session / AsyncSession."""
        curl_opts: Dict[int, Any] = {
            _CURLOPT_CONNECTTIMEOUT_MS: min(7000, max(2000, int(self.timeout * 1000)))
        }
        if self.force_ipv4:
            curl_opts[_CURLOPT_IPRESOLVE] = _CURL_IPRESOLVE_V4
        proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
        return {
            "impersonate": self.impersonate,
            "timeout": self.timeout,
            "proxies": proxies,
            "curl_options": curl_opts,
        }


class SyncWBTransport(BaseWBTransport):
    """Synchronous transport with Chrome TLS fingerprinting + IPv4 failover."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._cffi_session = None
        self._httpx_client: Optional[httpx.Client] = None
        self._init_clients()

    def _init_clients(self) -> None:
        if CURL_CFFI_AVAILABLE and cffi_requests is not None:
            self._cffi_session = cffi_requests.Session(**self._cffi_kwargs())
            if self.cookies_dict:
                self._cffi_session.cookies.update(self.cookies_dict)
        else:  # pragma: no cover
            transport = (
                httpx.HTTPTransport(local_address="0.0.0.0")
                if self.force_ipv4
                else None
            )
            self._httpx_client = httpx.Client(
                http2=True,
                timeout=httpx.Timeout(self.timeout),
                proxy=self.proxy,
                transport=transport,
                cookies=self.cookies_dict or None,
            )

    def _raw_get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> HttpResponse:
        req_headers = self.build_headers(headers)
        if self._cffi_session is not None:
            r = self._cffi_session.get(url, params=params, headers=req_headers)
            return HttpResponse(
                status_code=r.status_code,
                text=r.text,
                content=r.content,
                headers={k.lower(): v for k, v in r.headers.items()},
            )
        assert self._httpx_client is not None
        r = self._httpx_client.get(url, params=params, headers=req_headers)
        return HttpResponse(
            status_code=r.status_code,
            text=r.text,
            content=r.content,
            headers={k.lower(): v for k, v in r.headers.items()},
        )

    def rotate_proxy(self) -> bool:
        """Trigger proxy IP rotation URL if configured."""
        if not self.proxy_change_url:
            return False
        try:
            with httpx.Client(timeout=8.0) as c:
                r = c.get(self.proxy_change_url)
                logger.info(f"Proxy IP rotation requested: HTTP {r.status_code}")
                time.sleep(2.0)
                return r.status_code < 400
        except Exception as exc:
            logger.warning(f"Proxy rotation request failed: {exc}")
            return False

    def get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Fetch JSON payload with automatic retries on transient errors and rate limits."""
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                resp = self._raw_get(url, params=params, headers=headers)
                if resp.status_code in (429, 500, 502, 503, 504) and attempt + 1 < self.max_retries:
                    logger.warning(f"HTTP {resp.status_code} for {url}, retrying ({attempt + 1}/{self.max_retries})")
                    if resp.status_code == 429 and self.proxy_change_url:
                        self.rotate_proxy()
                    time.sleep(self._backoff(attempt))
                    continue
                self._raise_for_status(resp, url)
                return resp.json()
            except (WBNotFoundError, WBAntiBotError):
                raise
            except (WBRateLimitError, WBNetworkError) as exc:
                last_exc = exc
                if attempt + 1 < self.max_retries:
                    time.sleep(self._backoff(attempt))
                    continue
                raise
            except Exception as exc:
                last_exc = exc
                logger.debug(f"Attempt {attempt + 1} failed for {url}: {exc}")
                if attempt + 1 < self.max_retries:
                    self.close()
                    self._init_clients()
                    time.sleep(self._backoff(attempt))
                    continue
                raise WBNetworkError(f"Request failed for {url}: {exc}") from exc
        raise WBNetworkError(f"Request failed for {url}: {last_exc}")

    def ping(self, url: str = "https://cdn.wbbasket.ru/api/v3/upstreams") -> Dict[str, Any]:
        """Measure latency and HTTP status to a live WB endpoint (used in CLI/GUI diagnostics)."""
        t0 = time.perf_counter()
        try:
            resp = self._raw_get(url)
            ms = round((time.perf_counter() - t0) * 1000, 1)
            return {
                "ok": resp.status_code == 200,
                "status_code": resp.status_code,
                "latency_ms": ms,
                "bytes": len(resp.content),
                "tls": "curl_cffi" if self._cffi_session else "httpx",
            }
        except Exception as exc:
            ms = round((time.perf_counter() - t0) * 1000, 1)
            return {
                "ok": False,
                "status_code": 0,
                "latency_ms": ms,
                "error": str(exc),
                "tls": "curl_cffi" if self._cffi_session else "httpx",
            }

    def close(self) -> None:
        if self._cffi_session is not None:
            try:
                self._cffi_session.close()
            except Exception:
                pass
        if self._httpx_client is not None:
            try:
                self._httpx_client.close()
            except Exception:
                pass


class AsyncWBTransport(BaseWBTransport):
    """Asynchronous transport using `curl_cffi.AsyncSession` or `httpx.AsyncClient`."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._cffi_session = None
        self._httpx_client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self) -> None:
        if self._cffi_session is not None or self._httpx_client is not None:
            return
        if CURL_CFFI_AVAILABLE and cffi_requests is not None:
            self._cffi_session = cffi_requests.AsyncSession(**self._cffi_kwargs())
            if self.cookies_dict:
                self._cffi_session.cookies.update(self.cookies_dict)
        else:  # pragma: no cover
            transport = (
                httpx.AsyncHTTPTransport(local_address="0.0.0.0")
                if self.force_ipv4
                else None
            )
            self._httpx_client = httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(self.timeout),
                proxy=self.proxy,
                transport=transport,
                cookies=self.cookies_dict or None,
            )

    async def _raw_get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> HttpResponse:
        await self._ensure_client()
        req_headers = self.build_headers(headers)
        if self._cffi_session is not None:
            r = await self._cffi_session.get(url, params=params, headers=req_headers)
            return HttpResponse(
                status_code=r.status_code,
                text=r.text,
                content=r.content,
                headers={k.lower(): v for k, v in r.headers.items()},
            )
        assert self._httpx_client is not None
        r = await self._httpx_client.get(url, params=params, headers=req_headers)
        return HttpResponse(
            status_code=r.status_code,
            text=r.text,
            content=r.content,
            headers={k.lower(): v for k, v in r.headers.items()},
        )

    async def get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Async fetch JSON payload with retries and jitter."""
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                resp = await self._raw_get(url, params=params, headers=headers)
                if resp.status_code in (429, 500, 502, 503, 504) and attempt + 1 < self.max_retries:
                    await asyncio.sleep(self._backoff(attempt))
                    continue
                self._raise_for_status(resp, url)
                return resp.json()
            except (WBNotFoundError, WBAntiBotError):
                raise
            except (WBRateLimitError, WBNetworkError) as exc:
                last_exc = exc
                if attempt + 1 < self.max_retries:
                    await asyncio.sleep(self._backoff(attempt))
                    continue
                raise
            except Exception as exc:
                last_exc = exc
                if attempt + 1 < self.max_retries:
                    await asyncio.sleep(self._backoff(attempt))
                    continue
                raise WBNetworkError(f"Async request failed for {url}: {exc}") from exc
        raise WBNetworkError(f"Async request failed for {url}: {last_exc}")

    async def close(self) -> None:
        if self._cffi_session is not None:
            try:
                await self._cffi_session.close()
            except Exception:
                pass
        if self._httpx_client is not None:
            try:
                await self._httpx_client.aclose()
            except Exception:
                pass
