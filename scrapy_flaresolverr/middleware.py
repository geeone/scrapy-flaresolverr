"""Scrapy downloader middleware for stateless FlareSolverr requests."""

from __future__ import annotations

from dataclasses import dataclass
import math
import threading
from typing import Any, NoReturn, cast

from scrapy import Spider, signals
from scrapy.crawler import Crawler
from scrapy.http import HtmlResponse, Request
from twisted.internet.defer import Deferred
from twisted.internet.threads import deferToThread
from twisted.python.failure import Failure

from scrapy_flaresolverr.backends import BackendPool, FlareSolverrBackend
from scrapy_flaresolverr.client import FlareSolverrClient
from scrapy_flaresolverr.exceptions import (
    FlareSolverrConcurrencyError,
    FlareSolverrUnsupportedRequestError,
)
from scrapy_flaresolverr.responses import build_html_response
from scrapy_flaresolverr.settings import FlareSolverrSettings
from scrapy_flaresolverr.stats import FlareSolverrStats


@dataclass(frozen=True, slots=True)
class _PreparedRequest:
    """Validated options required to execute one FlareSolverr request."""

    backend: FlareSolverrBackend
    max_timeout_ms: int
    request_timeout_seconds: float
    wait_in_seconds: float | None
    disable_media: bool
    return_screenshot: bool


class FlareSolverrMiddleware:
    """Route opt-in Scrapy GET requests through FlareSolverr backends."""

    def __init__(
        self,
        *,
        settings: FlareSolverrSettings,
        backend_pool: BackendPool,
        client: FlareSolverrClient,
        stats: FlareSolverrStats,
    ) -> None:
        self.settings = settings
        self.backend_pool = backend_pool
        self.client = client
        self.stats = stats
        self._semaphore = threading.BoundedSemaphore(
            settings.max_concurrent
        )

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> FlareSolverrMiddleware:
        """Create the middleware from Scrapy settings."""

        settings = FlareSolverrSettings.from_scrapy_settings(
            crawler.settings
        )

        middleware = cls(
            settings=settings,
            backend_pool=BackendPool(settings.urls),
            client=FlareSolverrClient(
                auth_token=settings.auth_token
            ),
            stats=FlareSolverrStats(crawler.stats),
        )

        crawler.signals.connect(
            middleware.spider_opened,
            signal=signals.spider_opened,
        )

        return middleware

    def spider_opened(self, spider: Spider) -> None:
        """Log the enabled FlareSolverr backend configuration."""

        backends = ", ".join(
            backend.url
            for backend in self.backend_pool.backends
        )

        spider.logger.info(
            "scrapy-flaresolverr enabled with %d backend(s): %s",
            len(self.backend_pool.backends),
            backends,
        )

    def process_request(
        self,
        request: Request,
        spider: Spider,
    ) -> Deferred[HtmlResponse] | None:
        """Process an explicitly enabled request through FlareSolverr."""

        options = self._request_options(request)
        if options is None:
            return None

        if request.method.upper() != "GET":
            self.stats.increment("unsupported_request")
            raise FlareSolverrUnsupportedRequestError(
                "scrapy-flaresolverr v0.1 supports GET requests only, "
                f"got {request.method}"
            )

        prepared = self._prepare_request(options)

        request.meta["flaresolverr_used"] = True
        request.meta["flaresolverr_backend"] = prepared.backend.url
        self.stats.increment("request_count")

        deferred: Deferred[Any] = deferToThread(
            self._execute_flaresolverr_request,
            request.url,
            prepared,
        )

        deferred.addCallbacks(
            callback=lambda solution: self._handle_success(
                request=request,
                solution=solution,
            ),
            errback=self._handle_error,
        )

        return cast(Deferred[HtmlResponse], deferred)

    def _prepare_request(
        self,
        options: dict[str, Any],
    ) -> _PreparedRequest:
        """Validate and normalize request-level FlareSolverr options."""

        backend = self.backend_pool.resolve(
            _optional_string(
                options.get("backend"),
                name="backend",
            )
        )

        max_timeout_ms = _positive_int(
            options.get("max_timeout"),
            default=self.settings.max_timeout_ms,
            name="max_timeout",
        )

        request_timeout_seconds = _positive_float(
            options.get("request_timeout"),
            default=max(
                self.settings.request_timeout_seconds,
                max_timeout_ms / 1000 + 15,
            ),
            name="request_timeout",
        )

        wait_in_seconds = _optional_non_negative_float(
            options.get("wait_in_seconds"),
            name="wait_in_seconds",
        )

        disable_media = _boolean(
            options.get("disable_media"),
            default=self.settings.disable_media,
            name="disable_media",
        )

        return_screenshot = _boolean(
            options.get("return_screenshot"),
            default=False,
            name="return_screenshot",
        )

        return _PreparedRequest(
            backend=backend,
            max_timeout_ms=max_timeout_ms,
            request_timeout_seconds=request_timeout_seconds,
            wait_in_seconds=wait_in_seconds,
            disable_media=disable_media,
            return_screenshot=return_screenshot,
        )

    def _execute_flaresolverr_request(
        self,
        url: str,
        prepared: _PreparedRequest,
    ) -> Any:
        """Execute the blocking FlareSolverr request in a worker thread."""

        acquired = self._semaphore.acquire(
            timeout=self.settings.concurrency_wait_timeout
        )

        if not acquired:
            raise FlareSolverrConcurrencyError(
                "Timed out while waiting for a FlareSolverr concurrency slot"
            )

        try:
            return self.client.request_get(
                endpoint=prepared.backend.url,
                url=url,
                max_timeout_ms=prepared.max_timeout_ms,
                request_timeout_seconds=prepared.request_timeout_seconds,
                wait_in_seconds=prepared.wait_in_seconds,
                disable_media=prepared.disable_media,
                return_screenshot=prepared.return_screenshot,
            )
        finally:
            self._semaphore.release()

    def _handle_success(
        self,
        *,
        request: Request,
        solution: Any,
    ) -> HtmlResponse:
        """Build the Scrapy response after returning to the reactor thread."""

        self.stats.increment("response_count")

        return build_html_response(
            request=request,
            solution=solution,
        )

    def _handle_error(self, failure: Failure) -> NoReturn:
        """Record request errors and propagate the original exception."""

        self.stats.increment("request_error")

        if failure.check(FlareSolverrConcurrencyError):
            self.stats.increment("concurrency_timeout")

        failure.raiseException()

    @staticmethod
    def _request_options(
        request: Request,
    ) -> dict[str, Any] | None:
        """Return options for an explicitly enabled FlareSolverr request."""

        value = request.meta.get("flaresolverr")

        if isinstance(value, dict):
            return dict(value)

        if value is True:
            return {}

        if request.meta.get("use_flaresolverr") is True:
            return {}

        return None


def _optional_string(
    value: Any,
    *,
    name: str,
) -> str | None:
    """Parse an optional non-empty string option."""

    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(
            f"FlareSolverr option {name!r} must be a string"
        )

    parsed = value.strip()
    if not parsed:
        raise ValueError(
            f"FlareSolverr option {name!r} must not be empty"
        )

    return parsed


def _positive_int(
    value: Any,
    *,
    default: int,
    name: str,
) -> int:
    """Parse a strictly positive integer option."""

    if value is None:
        return default

    if isinstance(value, bool):
        raise ValueError(
            f"FlareSolverr option {name!r} must be an integer"
        )

    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = int(value.strip())
        except ValueError as exc:
            raise ValueError(
                f"FlareSolverr option {name!r} must be an integer"
            ) from exc
    else:
        raise ValueError(
            f"FlareSolverr option {name!r} must be an integer"
        )

    if parsed < 1:
        raise ValueError(
            f"FlareSolverr option {name!r} must be greater than zero"
        )

    return parsed


def _positive_float(
    value: Any,
    *,
    default: float,
    name: str,
) -> float:
    """Parse a finite, strictly positive numeric option."""

    if value is None:
        return default

    parsed = _parse_float(value, name=name)

    if parsed <= 0:
        raise ValueError(
            f"FlareSolverr option {name!r} must be greater than zero"
        )

    return parsed


def _optional_non_negative_float(
    value: Any,
    *,
    name: str,
) -> float | None:
    """Parse an optional finite number that may be zero."""

    if value is None:
        return None

    parsed = _parse_float(value, name=name)

    if parsed < 0:
        raise ValueError(
            f"FlareSolverr option {name!r} must be zero or greater"
        )

    return parsed


def _parse_float(
    value: Any,
    *,
    name: str,
) -> float:
    """Parse a finite numeric option without accepting booleans."""

    if isinstance(value, bool):
        raise ValueError(
            f"FlareSolverr option {name!r} must be numeric"
        )

    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"FlareSolverr option {name!r} must be numeric"
        ) from exc

    if not math.isfinite(parsed):
        raise ValueError(
            f"FlareSolverr option {name!r} must be finite"
        )

    return parsed


def _boolean(
    value: Any,
    *,
    default: bool,
    name: str,
) -> bool:
    """Parse a boolean option without treating arbitrary strings as true."""

    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, int) and value in {0, 1}:
        return bool(value)

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized in {"true", "1", "yes", "on"}:
            return True

        if normalized in {"false", "0", "no", "off"}:
            return False

    raise ValueError(
        f"FlareSolverr option {name!r} must be a boolean"
    )
