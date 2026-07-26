"""FlareSolverr backend URL normalization and selection."""

from __future__ import annotations

import itertools
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from scrapy_flaresolverr.exceptions import FlareSolverrConfigurationError


@dataclass(frozen=True, slots=True)
class FlareSolverrBackend:
    """A normalized FlareSolverr API endpoint."""

    url: str


def normalize_backend_url(value: str) -> str:
    """Normalize a backend base URL to a FlareSolverr ``/v1`` endpoint."""

    if not isinstance(value, str):
        raise FlareSolverrConfigurationError(
            "FlareSolverr backend URL must be a string"
        )

    raw_url = value.strip()
    if not raw_url:
        raise FlareSolverrConfigurationError("FlareSolverr backend URL cannot be empty")

    parts = urlsplit(raw_url)

    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        raise FlareSolverrConfigurationError(
            f"Invalid FlareSolverr backend URL: {value!r}"
        )

    if parts.query:
        raise FlareSolverrConfigurationError(
            f"FlareSolverr backend URL must not contain a query string: {value!r}"
        )

    if parts.fragment:
        raise FlareSolverrConfigurationError(
            f"FlareSolverr backend URL must not contain a fragment: {value!r}"
        )

    path = parts.path.rstrip("/")
    if not path.endswith("/v1"):
        path = f"{path}/v1" if path else "/v1"

    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc,
            path,
            "",
            "",
        )
    )


class BackendPool:
    """Thread-safe round-robin pool of configured FlareSolverr backends."""

    def __init__(self, urls: Sequence[str]) -> None:
        if isinstance(urls, str) or not urls:
            raise FlareSolverrConfigurationError(
                "FLARESOLVERR_URLS must contain at least one backend"
            )

        normalized_urls = tuple(
            dict.fromkeys(normalize_backend_url(url) for url in urls)
        )

        self._backends = tuple(FlareSolverrBackend(url=url) for url in normalized_urls)
        self._cycle = itertools.cycle(self._backends)
        self._lock = threading.Lock()
        self._by_url = {backend.url: backend for backend in self._backends}

    @property
    def backends(self) -> tuple[FlareSolverrBackend, ...]:
        """Return the configured backends in stable order."""

        return self._backends

    def next(self) -> FlareSolverrBackend:
        """Return the next backend using round-robin selection."""

        with self._lock:
            return next(self._cycle)

    def resolve(self, value: str | None) -> FlareSolverrBackend:
        """Resolve an optional request-level backend override."""

        if value is None:
            return self.next()

        normalized_url = normalize_backend_url(value)

        try:
            return self._by_url[normalized_url]
        except KeyError as exc:
            raise FlareSolverrConfigurationError(
                f"Unknown FlareSolverr backend override: {value!r}"
            ) from exc
