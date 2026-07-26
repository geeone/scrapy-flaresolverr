"""Minimal stateless client for the FlareSolverr v1 API."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import requests
from requests import Response

from scrapy_flaresolverr.exceptions import (
    FlareSolverrRequestError,
    FlareSolverrResponseError,
)

PostCallable = Callable[..., Response]


@dataclass(frozen=True, slots=True)
class FlareSolverrSolution:
    """Validated subset of a successful FlareSolverr solution."""

    url: str
    status: int
    headers: Mapping[str, Any]
    response: str
    cookies: list[dict[str, Any]]
    user_agent: str
    screenshot: str | None
    start_timestamp: int | None
    end_timestamp: int | None
    version: str | None


class FlareSolverrClient:
    """Send stateless requests to FlareSolverr."""

    def __init__(
        self,
        auth_token: str | None = None,
        post: PostCallable = requests.post,
    ) -> None:
        self._auth_token = auth_token
        self._post = post

    def request_get(
        self,
        *,
        endpoint: str,
        url: str,
        max_timeout_ms: int,
        request_timeout_seconds: float,
        wait_in_seconds: float | None = None,
        disable_media: bool = False,
        return_screenshot: bool = False,
    ) -> FlareSolverrSolution:
        """Execute a stateless ``request.get`` command."""

        payload: dict[str, Any] = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": max_timeout_ms,
        }

        if wait_in_seconds is not None:
            payload["waitInSeconds"] = wait_in_seconds

        if disable_media:
            payload["disableMedia"] = True

        if return_screenshot:
            payload["returnScreenshot"] = True

        try:
            response = self._post(
                endpoint,
                json=payload,
                headers=self._headers(),
                timeout=request_timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise FlareSolverrRequestError(
                f"FlareSolverr request failed via {endpoint}: {exc}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise FlareSolverrResponseError(
                f"FlareSolverr returned invalid JSON via {endpoint}"
            ) from exc

        if not isinstance(data, dict):
            raise FlareSolverrResponseError(
                f"FlareSolverr returned an unexpected payload via {endpoint}"
            )

        if data.get("status") != "ok":
            message = data.get("message")
            if not isinstance(message, str) or not message.strip():
                message = "unknown FlareSolverr error"

            raise FlareSolverrResponseError(
                f"FlareSolverr failed via {endpoint}: {message}"
            )

        solution = data.get("solution")
        if not isinstance(solution, dict):
            raise FlareSolverrResponseError(
                f"FlareSolverr response has no valid solution via {endpoint}"
            )

        solution_url = _required_string(
            solution,
            "url",
            endpoint=endpoint,
        )
        solution_status = _required_status(
            solution,
            endpoint=endpoint,
        )
        solution_response = _required_string(
            solution,
            "response",
            endpoint=endpoint,
        )

        headers = _headers_mapping(
            solution.get("headers"),
            endpoint=endpoint,
        )
        cookies = _cookies_list(
            solution.get("cookies"),
            endpoint=endpoint,
        )

        return FlareSolverrSolution(
            url=solution_url,
            status=solution_status,
            headers=headers,
            response=solution_response,
            cookies=cookies,
            user_agent=_optional_string(
                solution.get("userAgent"),
                field="userAgent",
                endpoint=endpoint,
                default="",
            ),
            screenshot=_optional_string(
                solution.get("screenshot"),
                field="screenshot",
                endpoint=endpoint,
            ),
            start_timestamp=_optional_int(
                data.get("startTimestamp"),
                field="startTimestamp",
                endpoint=endpoint,
            ),
            end_timestamp=_optional_int(
                data.get("endTimestamp"),
                field="endTimestamp",
                endpoint=endpoint,
            ),
            version=_optional_string(
                data.get("version"),
                field="version",
                endpoint=endpoint,
            ),
        )

    def _headers(self) -> dict[str, str]:
        """Build HTTP headers for the FlareSolverr API request."""

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"

        return headers


def _required_string(
    mapping: Mapping[str, Any],
    field: str,
    *,
    endpoint: str,
) -> str:
    """Return a required non-empty string field."""

    value = mapping.get(field)

    if not isinstance(value, str) or not value:
        raise FlareSolverrResponseError(
            f"FlareSolverr solution field {field!r} must be a non-empty string "
            f"via {endpoint}"
        )

    return value


def _required_status(
    solution: Mapping[str, Any],
    *,
    endpoint: str,
) -> int:
    """Return a valid HTTP response status from a FlareSolverr solution."""

    value = solution.get("status")

    if isinstance(value, bool):
        raise FlareSolverrResponseError(
            f"FlareSolverr solution status is invalid via {endpoint}"
        )

    try:
        status = int(value)
    except (TypeError, ValueError) as exc:
        raise FlareSolverrResponseError(
            f"FlareSolverr solution status is invalid via {endpoint}"
        ) from exc

    if status < 100 or status > 599:
        raise FlareSolverrResponseError(
            f"FlareSolverr solution status is outside the HTTP range "
            f"via {endpoint}: {status}"
        )

    return status


def _headers_mapping(
    value: Any,
    *,
    endpoint: str,
) -> Mapping[str, Any]:
    """Return validated response headers."""

    if value is None:
        return {}

    if not isinstance(value, dict):
        raise FlareSolverrResponseError(
            f"FlareSolverr solution headers are invalid via {endpoint}"
        )

    return value


def _cookies_list(
    value: Any,
    *,
    endpoint: str,
) -> list[dict[str, Any]]:
    """Return validated FlareSolverr cookies."""

    if value is None:
        return []

    if not isinstance(value, list):
        raise FlareSolverrResponseError(
            f"FlareSolverr solution cookies are invalid via {endpoint}"
        )

    cookies: list[dict[str, Any]] = []

    for index, cookie in enumerate(value):
        if not isinstance(cookie, dict):
            raise FlareSolverrResponseError(
                f"FlareSolverr solution cookie at index {index} is invalid "
                f"via {endpoint}"
            )

        cookies.append(cookie)

    return cookies


def _optional_string(
    value: Any,
    *,
    field: str,
    endpoint: str,
    default: str | None = None,
) -> str | None:
    """Return an optional string without coercing arbitrary values."""

    if value is None:
        return default

    if not isinstance(value, str):
        raise FlareSolverrResponseError(
            f"FlareSolverr field {field!r} must be a string via {endpoint}"
        )

    return value


def _optional_int(
    value: Any,
    *,
    field: str,
    endpoint: str,
) -> int | None:
    """Return an optional integer without silently ignoring invalid values."""

    if value is None:
        return None

    if isinstance(value, bool):
        raise FlareSolverrResponseError(
            f"FlareSolverr field {field!r} must be an integer via {endpoint}"
        )

    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise FlareSolverrResponseError(
            f"FlareSolverr field {field!r} must be an integer via {endpoint}"
        ) from exc
