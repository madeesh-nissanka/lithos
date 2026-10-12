# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
HTTP client with rate limiting, retries, and polite pool support.
"""
from __future__ import annotations
from lithos._version import VERSION
import json
import logging
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class RateLimiter:
    """Token bucket rate limiter."""
    requests_per_second: float = 1.0
    burst: int = 5
    _tokens: float = field(init=False, default=0)
    _last_update: float = field(init=False, default=0)
    _lock: Lock = field(init=False, default_factory=Lock)

    def __post_init__(self):
        self._tokens = self.burst
        self._last_update = time.monotonic()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_update
            self._tokens = min(self.burst, self._tokens + elapsed * self.requests_per_second)
            if self._tokens < 1:
                sleep_time = (1 - self._tokens) / self.requests_per_second
                time.sleep(sleep_time)
                self._tokens = 0
            else:
                self._tokens -= 1
            self._last_update = time.monotonic()


class PolitePool:
    """Manages polite pool email for API requests."""
    def __init__(self, email: Optional[str] = None):
        self.email = email or os.environ.get("SCHOLAR_MAILTO", "")

    def get_mailto_param(self) -> str:
        return urllib.parse.quote(self.email) if self.email else ""

    def get_user_agent(self, tool_name: str, version: str) -> str:
        ua = f"{tool_name}/{version}"
        if self.email:
            ua += f" (mailto:{self.email})"
        return ua


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: float = 0.1
    retry_on_status: tuple[int, ...] = (429, 500, 502, 503, 504)

    def get_delay(self, attempt: int) -> float:
        delay = min(self.base_delay * (self.exponential_base ** attempt), self.max_delay)
        jitter_amount = delay * self.jitter * random.random()
        return delay + jitter_amount


class HTTPClient:
    """HTTP client with rate limiting, retries, and polite pool."""

    def __init__(
        self,
        rate_limiter: Optional[RateLimiter] = None,
        retry_policy: Optional[RetryPolicy] = None,
        polite_pool: Optional[PolitePool] = None,
        tool_name: str = "lithos",
        version: str = VERSION,
        default_timeout: int = 30,
    ):
        self.rate_limiter = rate_limiter or RateLimiter()
        self.retry_policy = retry_policy or RetryPolicy()
        self.polite_pool = polite_pool or PolitePool()
        self.tool_name = tool_name
        self.version = version
        self.default_timeout = default_timeout
        self._session_headers = {
            "User-Agent": self.polite_pool.get_user_agent(tool_name, version),
            "Accept": "application/json",
        }

    def _build_request(self, url: str, headers: Optional[dict] = None, method: str = "GET") -> urllib.request.Request:
        merged_headers = {**self._session_headers}
        if headers:
            merged_headers.update(headers)
        req = urllib.request.Request(url, headers=merged_headers, method=method)
        return req

    def _should_retry(self, attempt: int, error: Exception) -> bool:
        if attempt >= self.retry_policy.max_attempts:
            return False
        if isinstance(error, urllib.error.HTTPError):
            return error.code in self.retry_policy.retry_on_status
        if isinstance(error, (urllib.error.URLError, TimeoutError, ConnectionError)):
            return True
        return False

    def get_json(self, url: str, params: Optional[dict] = None, timeout: Optional[int] = None) -> dict:
        """GET request returning parsed JSON."""
        if params:
            separator = "&" if "?" in url else "?"
            url += separator + urllib.parse.urlencode(params)

        attempt = 0
        last_error = None
        while True:
            self.rate_limiter.acquire()
            try:
                req = self._build_request(url)
                with urllib.request.urlopen(req, timeout=timeout or self.default_timeout) as response:
                    data = response.read()
                    return json.loads(data)
            except Exception as e:
                last_error = e
                if not self._should_retry(attempt, e):
                    break
                delay = self.retry_policy.get_delay(attempt)
                logger.warning(f"Request failed (attempt {attempt+1}/{self.retry_policy.max_attempts}): {e}. Retrying in {delay:.1f}s")
                time.sleep(delay)
                attempt += 1

        logger.error(f"Request failed after {attempt+1} attempts: {last_error}")
        raise last_error

    def get_bytes(self, url: str, params: Optional[dict] = None, timeout: Optional[int] = None) -> bytes:
        """GET request returning raw bytes (for PDF/HTML/XML payloads)."""
        if params:
            separator = "&" if "?" in url else "?"
            url += separator + urllib.parse.urlencode(params)

        attempt = 0
        last_error = None
        while True:
            self.rate_limiter.acquire()
            try:
                req = self._build_request(url, headers={"Accept": "application/pdf, text/html, application/xml;q=0.9, */*;q=0.8"})
                with urllib.request.urlopen(req, timeout=timeout or self.default_timeout) as response:
                    return response.read()
            except Exception as e:
                last_error = e
                if not self._should_retry(attempt, e):
                    break
                delay = self.retry_policy.get_delay(attempt)
                logger.warning(f"Request failed (attempt {attempt+1}/{self.retry_policy.max_attempts}): {e}. Retrying in {delay:.1f}s")
                time.sleep(delay)
                attempt += 1

        logger.error(f"Request failed after {attempt+1} attempts: {last_error}")
        raise last_error

    def get_text(self, url: str, params: Optional[dict] = None, timeout: Optional[int] = None) -> str:
        """GET request returning raw text."""
        if params:
            separator = "&" if "?" in url else "?"
            url += separator + urllib.parse.urlencode(params)

        attempt = 0
        last_error = None
        while True:
            self.rate_limiter.acquire()
            try:
                req = self._build_request(url)
                with urllib.request.urlopen(req, timeout=timeout or self.default_timeout) as response:
                    return response.read().decode("utf-8")
            except Exception as e:
                last_error = e
                if not self._should_retry(attempt, e):
                    break
                delay = self.retry_policy.get_delay(attempt)
                logger.warning(f"Request failed (attempt {attempt+1}/{self.retry_policy.max_attempts}): {e}. Retrying in {delay:.1f}s")
                time.sleep(delay)
                attempt += 1

        logger.error(f"Request failed after {attempt+1} attempts: {last_error}")
        raise last_error