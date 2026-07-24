"""Conversion of FlareSolverr solutions into Scrapy responses."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any

from scrapy.http import Headers, HtmlResponse, Request

from scrapy_flaresolverr.client import FlareSolverrSolution


# FlareSolverr returns decoded HTML. Transport headers describing the original
# encoded payload must therefore not be copied to the new Scrapy response.
_DROPPED_HEADERS = {
    "content-encoding",
    "content-length",
    "status",
    "transfer-encoding",
}

_CHARSET_PATTERN = re.compile(
    r";\s*charset\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^;\s]*)",
    flags=re.IGNORECASE,
)


def build_html_response(
    *,
    request: Request,
    solution: FlareSolverrSolution,
) -> HtmlResponse:
    """Build a complete :class:`HtmlResponse` from a FlareSolverr solution."""

    request.meta["flaresolverr_response"] = {
        "cookies": solution.cookies,
        "user_agent": solution.user_agent,
        "screenshot": solution.screenshot,
        "start_timestamp": solution.start_timestamp,
        "end_timestamp": solution.end_timestamp,
        "version": solution.version,
    }

    return HtmlResponse(
        url=solution.url,
        status=solution.status,
        headers=_normalize_headers(solution.headers),
        body=solution.response.encode("utf-8"),
        encoding="utf-8",
        request=request,
        flags=["flaresolverr"],
    )


def _normalize_headers(values: Mapping[str, Any]) -> Headers:
    """Normalize FlareSolverr headers for a UTF-8 Scrapy response."""

    normalized: dict[str, str | list[str]] = {}

    for name, value in values.items():
        header_name = _normalize_header_name(name)
        lower_name = header_name.lower()

        if lower_name in _DROPPED_HEADERS or value is None:
            continue

        header_values = _normalize_header_values(
            value,
            header_name=header_name,
        )

        if lower_name == "content-type":
            header_values = [
                _normalize_content_type(item)
                for item in header_values
            ]

        normalized[header_name] = (
            header_values[0]
            if len(header_values) == 1
            else header_values
        )

    return Headers(normalized)


def _normalize_header_name(value: Any) -> str:
    """Return a valid textual header name."""

    if isinstance(value, bytes):
        try:
            name = value.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "FlareSolverr response contains an invalid header name"
            ) from exc
    elif isinstance(value, str):
        name = value
    else:
        raise ValueError(
            "FlareSolverr response header names must be strings"
        )

    name = name.strip()
    if not name:
        raise ValueError(
            "FlareSolverr response contains an empty header name"
        )

    return name


def _normalize_header_values(
    value: Any,
    *,
    header_name: str,
) -> list[str]:
    """Return one or more textual values for a response header."""

    if isinstance(value, (str, bytes)):
        values: Sequence[Any] = [value]
    elif isinstance(value, (list, tuple)):
        values = value
    else:
        raise ValueError(
            f"FlareSolverr response header {header_name!r} "
            "must contain a string or a list of strings"
        )

    normalized: list[str] = []

    for item in values:
        if isinstance(item, bytes):
            normalized.append(item.decode("latin-1"))
        elif isinstance(item, str):
            normalized.append(item)
        else:
            raise ValueError(
                f"FlareSolverr response header {header_name!r} "
                "contains a non-string value"
            )

    if not normalized:
        raise ValueError(
            f"FlareSolverr response header {header_name!r} "
            "contains no values"
        )

    return normalized


def _normalize_content_type(value: str) -> str:
    """Align a Content-Type header with the UTF-8 encoded response body."""

    without_charset = _CHARSET_PATTERN.sub("", value).strip()

    if not without_charset:
        return "text/html; charset=utf-8"

    return f"{without_charset}; charset=utf-8"
