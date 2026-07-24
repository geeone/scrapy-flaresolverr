"""Middleware configuration parsing."""

from __future__ import annotations

from dataclasses import dataclass
import math

from scrapy.settings import BaseSettings

from scrapy_flaresolverr.exceptions import FlareSolverrConfigurationError


@dataclass(frozen=True, slots=True)
class FlareSolverrSettings:
    """Validated settings used by :class:`FlareSolverrMiddleware`."""

    urls: tuple[str, ...]
    auth_token: str | None
    max_concurrent: int
    concurrency_wait_timeout: float
    max_timeout_ms: int
    request_timeout_seconds: float
    disable_media: bool

    @classmethod
    def from_scrapy_settings(
        cls,
        settings: BaseSettings,
    ) -> FlareSolverrSettings:
        """Build and validate settings from Scrapy's settings object."""

        urls = _get_urls(settings)

        max_concurrent = _get_positive_int(
            settings,
            "FLARESOLVERR_MAX_CONCURRENT",
            default=3,
        )
        concurrency_wait_timeout = _get_positive_float(
            settings,
            "FLARESOLVERR_CONCURRENCY_WAIT_TIMEOUT",
            default=120.0,
        )
        max_timeout_ms = _get_positive_int(
            settings,
            "FLARESOLVERR_MAX_TIMEOUT",
            default=60_000,
        )
        request_timeout_seconds = _get_positive_float(
            settings,
            "FLARESOLVERR_REQUEST_TIMEOUT",
            default=75.0,
        )

        minimum_request_timeout = max_timeout_ms / 1000
        if request_timeout_seconds <= minimum_request_timeout:
            raise FlareSolverrConfigurationError(
                "FLARESOLVERR_REQUEST_TIMEOUT must be greater than "
                "FLARESOLVERR_MAX_TIMEOUT converted to seconds"
            )

        auth_token = _optional_string(
            settings.get("FLARESOLVERR_AUTH_TOKEN"),
            name="FLARESOLVERR_AUTH_TOKEN",
        )

        try:
            disable_media = settings.getbool(
                "FLARESOLVERR_DISABLE_MEDIA",
                False,
            )
        except (TypeError, ValueError) as exc:
            raise FlareSolverrConfigurationError(
                "FLARESOLVERR_DISABLE_MEDIA must be a boolean"
            ) from exc

        return cls(
            urls=urls,
            auth_token=auth_token,
            max_concurrent=max_concurrent,
            concurrency_wait_timeout=concurrency_wait_timeout,
            max_timeout_ms=max_timeout_ms,
            request_timeout_seconds=request_timeout_seconds,
            disable_media=disable_media,
        )


def _get_urls(settings: BaseSettings) -> tuple[str, ...]:
    """Return configured FlareSolverr backend URLs."""

    try:
        configured_urls = settings.getlist("FLARESOLVERR_URLS")
    except (TypeError, ValueError) as exc:
        raise FlareSolverrConfigurationError(
            "FLARESOLVERR_URLS must be a list of backend URLs"
        ) from exc

    if not configured_urls:
        single_url = settings.get("FLARESOLVERR_URL")
        if single_url is not None:
            configured_urls = [single_url]

    if not configured_urls:
        raise FlareSolverrConfigurationError(
            "FLARESOLVERR_URLS or FLARESOLVERR_URL must define "
            "at least one backend"
        )

    urls: list[str] = []

    for value in configured_urls:
        if not isinstance(value, str):
            raise FlareSolverrConfigurationError(
                "FlareSolverr backend URLs must be strings"
            )

        url = value.strip()
        if not url:
            raise FlareSolverrConfigurationError(
                "FlareSolverr backend URLs cannot be empty"
            )

        urls.append(url)

    return tuple(urls)


def _get_positive_int(
    settings: BaseSettings,
    name: str,
    *,
    default: int,
) -> int:
    """Read a strictly positive integer setting."""

    try:
        value = settings.getint(name, default)
    except (TypeError, ValueError) as exc:
        raise FlareSolverrConfigurationError(
            f"{name} must be an integer"
        ) from exc

    if value < 1:
        raise FlareSolverrConfigurationError(
            f"{name} must be greater than zero"
        )

    return value


def _get_positive_float(
    settings: BaseSettings,
    name: str,
    *,
    default: float,
) -> float:
    """Read a finite, strictly positive floating-point setting."""

    try:
        value = settings.getfloat(name, default)
    except (TypeError, ValueError) as exc:
        raise FlareSolverrConfigurationError(
            f"{name} must be numeric"
        ) from exc

    if not math.isfinite(value):
        raise FlareSolverrConfigurationError(
            f"{name} must be finite"
        )

    if value <= 0:
        raise FlareSolverrConfigurationError(
            f"{name} must be greater than zero"
        )

    return value


def _optional_string(
    value: object,
    *,
    name: str,
) -> str | None:
    """Return an optional non-empty string setting."""

    if value is None:
        return None

    if not isinstance(value, str):
        raise FlareSolverrConfigurationError(
            f"{name} must be a string"
        )

    parsed = value.strip()
    return parsed or None
