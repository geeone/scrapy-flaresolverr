from unittest.mock import Mock

import pytest
import requests
from scrapy_flaresolverr.client import FlareSolverrClient
from scrapy_flaresolverr.exceptions import (
    FlareSolverrRequestError,
    FlareSolverrResponseError,
)

ENDPOINT = "http://flaresolverr:8191/v1"
TARGET_URL = "https://example.com/"


def _valid_payload():
    return {
        "status": "ok",
        "message": "",
        "solution": {
            "url": TARGET_URL,
            "status": 200,
            "headers": {"Content-Type": "text/html"},
            "response": "<html>ok</html>",
            "cookies": [{"name": "cf_clearance", "value": "abc"}],
            "userAgent": "test-agent",
            "screenshot": "base64",
        },
        "startTimestamp": 100,
        "endTimestamp": 200,
        "version": "3.5.0",
    }


def _response_for(payload):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


def _request(client):
    return client.request_get(
        endpoint=ENDPOINT,
        url=TARGET_URL,
        max_timeout_ms=60_000,
        request_timeout_seconds=75.0,
        wait_in_seconds=1.5,
        disable_media=True,
        return_screenshot=True,
    )


def test_request_get_builds_payload_headers_and_solution():
    response = _response_for(_valid_payload())
    post = Mock(return_value=response)
    client = FlareSolverrClient(auth_token="secret", post=post)

    solution = _request(client)

    post.assert_called_once_with(
        ENDPOINT,
        json={
            "cmd": "request.get",
            "url": TARGET_URL,
            "maxTimeout": 60_000,
            "waitInSeconds": 1.5,
            "disableMedia": True,
            "returnScreenshot": True,
        },
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Bearer secret",
        },
        timeout=75.0,
    )
    assert solution.url == TARGET_URL
    assert solution.status == 200
    assert solution.response == "<html>ok</html>"
    assert solution.cookies == [{"name": "cf_clearance", "value": "abc"}]
    assert solution.user_agent == "test-agent"
    assert solution.screenshot == "base64"
    assert solution.start_timestamp == 100
    assert solution.end_timestamp == 200
    assert solution.version == "3.5.0"


def test_request_get_omits_optional_payload_flags_and_uses_solution_defaults():
    payload = _valid_payload()
    payload["solution"].pop("headers")
    payload["solution"].pop("cookies")
    payload["solution"].pop("userAgent")
    payload["solution"].pop("screenshot")
    payload.pop("startTimestamp")
    payload.pop("endTimestamp")
    payload.pop("version")
    post = Mock(return_value=_response_for(payload))
    client = FlareSolverrClient(post=post)

    solution = client.request_get(
        endpoint=ENDPOINT,
        url=TARGET_URL,
        max_timeout_ms=10_000,
        request_timeout_seconds=20.0,
    )

    assert post.call_args.kwargs["json"] == {
        "cmd": "request.get",
        "url": TARGET_URL,
        "maxTimeout": 10_000,
    }
    assert post.call_args.kwargs["headers"] == {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    assert solution.headers == {}
    assert solution.cookies == []
    assert solution.user_agent == ""
    assert solution.screenshot is None
    assert solution.start_timestamp is None
    assert solution.end_timestamp is None
    assert solution.version is None


@pytest.mark.parametrize(
    "failure_factory",
    [
        lambda: requests.Timeout("timeout"),
        lambda: requests.ConnectionError("connection failed"),
    ],
)
def test_request_get_wraps_transport_errors(failure_factory):
    client = FlareSolverrClient(post=Mock(side_effect=failure_factory()))

    with pytest.raises(FlareSolverrRequestError, match=ENDPOINT):
        _request(client)


def test_request_get_wraps_http_status_errors():
    response = _response_for(_valid_payload())
    response.raise_for_status.side_effect = requests.HTTPError("503")
    client = FlareSolverrClient(post=Mock(return_value=response))

    with pytest.raises(FlareSolverrRequestError, match=ENDPOINT):
        _request(client)


def test_request_get_rejects_invalid_json():
    response = _response_for(_valid_payload())
    response.json.side_effect = ValueError("bad json")
    client = FlareSolverrClient(post=Mock(return_value=response))

    with pytest.raises(FlareSolverrResponseError, match="invalid JSON"):
        _request(client)


@pytest.mark.parametrize("payload", [[], "ok", 123, None])
def test_request_get_rejects_non_mapping_payload(payload):
    client = FlareSolverrClient(post=Mock(return_value=_response_for(payload)))

    with pytest.raises(
        FlareSolverrResponseError,
        match="unexpected payload",
    ):
        _request(client)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("challenge failed", "challenge failed"),
        ("", "unknown FlareSolverr error"),
        ("   ", "unknown FlareSolverr error"),
        (None, "unknown FlareSolverr error"),
        (123, "unknown FlareSolverr error"),
    ],
)
def test_request_get_rejects_unsuccessful_status(message, expected):
    payload = _valid_payload()
    payload["status"] = "error"
    payload["message"] = message
    client = FlareSolverrClient(post=Mock(return_value=_response_for(payload)))

    with pytest.raises(FlareSolverrResponseError, match=expected):
        _request(client)


@pytest.mark.parametrize("solution", [None, [], "invalid"])
def test_request_get_requires_solution_mapping(solution):
    payload = _valid_payload()
    payload["solution"] = solution
    client = FlareSolverrClient(post=Mock(return_value=_response_for(payload)))

    with pytest.raises(FlareSolverrResponseError, match="no valid solution"):
        _request(client)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("url", None),
        ("url", ""),
        ("url", 123),
        ("response", None),
        ("response", ""),
        ("response", []),
    ],
)
def test_request_get_validates_required_string_fields(field, value):
    payload = _valid_payload()
    payload["solution"][field] = value
    client = FlareSolverrClient(post=Mock(return_value=_response_for(payload)))

    with pytest.raises(
        FlareSolverrResponseError,
        match=f"field '{field}' must be a non-empty string",
    ):
        _request(client)


@pytest.mark.parametrize("status", [True, False, None, "invalid", 99, 600])
def test_request_get_validates_solution_status(status):
    payload = _valid_payload()
    payload["solution"]["status"] = status
    client = FlareSolverrClient(post=Mock(return_value=_response_for(payload)))

    with pytest.raises(FlareSolverrResponseError, match="status"):
        _request(client)


@pytest.mark.parametrize("status", ["200", 204.0])
def test_request_get_accepts_integer_coercible_status(status):
    payload = _valid_payload()
    payload["solution"]["status"] = status
    client = FlareSolverrClient(post=Mock(return_value=_response_for(payload)))

    assert _request(client).status == int(status)


@pytest.mark.parametrize("headers", ["invalid", [], 123])
def test_request_get_validates_headers(headers):
    payload = _valid_payload()
    payload["solution"]["headers"] = headers
    client = FlareSolverrClient(post=Mock(return_value=_response_for(payload)))

    with pytest.raises(FlareSolverrResponseError, match="headers are invalid"):
        _request(client)


@pytest.mark.parametrize("cookies", ["invalid", {}, 123])
def test_request_get_validates_cookie_container(cookies):
    payload = _valid_payload()
    payload["solution"]["cookies"] = cookies
    client = FlareSolverrClient(post=Mock(return_value=_response_for(payload)))

    with pytest.raises(FlareSolverrResponseError, match="cookies are invalid"):
        _request(client)


@pytest.mark.parametrize("cookie", ["invalid", 123, None])
def test_request_get_validates_each_cookie(cookie):
    payload = _valid_payload()
    payload["solution"]["cookies"] = [{"name": "ok"}, cookie]
    client = FlareSolverrClient(post=Mock(return_value=_response_for(payload)))

    with pytest.raises(
        FlareSolverrResponseError,
        match="cookie at index 1 is invalid",
    ):
        _request(client)


@pytest.mark.parametrize(
    ("container", "field", "value"),
    [
        ("solution", "userAgent", 123),
        ("solution", "screenshot", []),
        ("root", "version", {}),
    ],
)
def test_request_get_validates_optional_strings(container, field, value):
    payload = _valid_payload()
    target = payload["solution"] if container == "solution" else payload
    target[field] = value
    client = FlareSolverrClient(post=Mock(return_value=_response_for(payload)))

    with pytest.raises(
        FlareSolverrResponseError,
        match=f"field '{field}' must be a string",
    ):
        _request(client)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("startTimestamp", True),
        ("endTimestamp", False),
        ("startTimestamp", "invalid"),
        ("endTimestamp", []),
    ],
)
def test_request_get_validates_optional_timestamps(field, value):
    payload = _valid_payload()
    payload[field] = value
    client = FlareSolverrClient(post=Mock(return_value=_response_for(payload)))

    with pytest.raises(
        FlareSolverrResponseError,
        match=f"field '{field}' must be an integer",
    ):
        _request(client)


def test_request_get_accepts_integer_coercible_timestamps():
    payload = _valid_payload()
    payload["startTimestamp"] = "123"
    payload["endTimestamp"] = 456.0
    client = FlareSolverrClient(post=Mock(return_value=_response_for(payload)))

    solution = _request(client)

    assert solution.start_timestamp == 123
    assert solution.end_timestamp == 456
