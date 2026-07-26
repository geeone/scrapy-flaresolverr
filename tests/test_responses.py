import pytest
from scrapy.http import Request

from scrapy_flaresolverr.client import FlareSolverrSolution
from scrapy_flaresolverr.responses import build_html_response, _normalize_headers


def _solution(headers=None):
    return FlareSolverrSolution(
        url="https://example.com/final",
        status=201,
        headers=headers or {},
        response="<html>✓</html>",
        cookies=[{"name": "cookie", "value": "value"}],
        user_agent="agent",
        screenshot="image",
        start_timestamp=10,
        end_timestamp=20,
        version="3.5.0",
    )


def test_build_html_response_preserves_scrapy_context_and_metadata():
    request = Request("https://example.com/original")
    solution = _solution(
        {
            "Content-Type": "text/html; charset=iso-8859-1",
            "X-Test": "value",
        }
    )

    response = build_html_response(request=request, solution=solution)

    assert response.url == "https://example.com/final"
    assert response.status == 201
    assert response.text == "<html>✓</html>"
    assert response.encoding == "utf-8"
    assert response.request is request
    assert "flaresolverr" in response.flags
    assert response.headers.get("Content-Type") == b"text/html; charset=utf-8"
    assert response.headers.get("X-Test") == b"value"
    assert request.meta["flaresolverr_response"] == {
        "cookies": solution.cookies,
        "user_agent": "agent",
        "screenshot": "image",
        "start_timestamp": 10,
        "end_timestamp": 20,
        "version": "3.5.0",
    }


@pytest.mark.parametrize(
    "name",
    [
        "Content-Encoding",
        "content-length",
        "STATUS",
        "Transfer-Encoding",
    ],
)
def test_normalize_headers_drops_transport_headers(name):
    headers = _normalize_headers({name: "ignored", "X-Keep": "value"})

    assert name.encode() not in headers
    assert headers.get("X-Keep") == b"value"


def test_normalize_headers_skips_none_values():
    headers = _normalize_headers({"X-Skip": None, "X-Keep": "value"})

    assert b"X-Skip" not in headers
    assert headers.get("X-Keep") == b"value"


def test_normalize_headers_supports_bytes_and_multiple_values():
    headers = _normalize_headers(
        {
            b"X-Bytes": b"value",
            "Set-Cookie": ["a=1", b"b=2"],
            "X-Tuple": ("one", "two"),
        }
    )

    assert headers.get("X-Bytes") == b"value"
    assert headers.getlist("Set-Cookie") == [b"a=1", b"b=2"]
    assert headers.getlist("X-Tuple") == [b"one", b"two"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("text/html", b"text/html; charset=utf-8"),
        ("text/html; charset=latin-1", b"text/html; charset=utf-8"),
        ('text/html; charset="latin-1"', b"text/html; charset=utf-8"),
        ("text/html; CHARSET = 'latin-1'", b"text/html; charset=utf-8"),
        ("; charset=latin-1", b"text/html; charset=utf-8"),
    ],
)
def test_content_type_is_normalized_to_utf8(value, expected):
    headers = _normalize_headers({"Content-Type": value})

    assert headers.get("Content-Type") == expected


@pytest.mark.parametrize("name", [123, None, object()])
def test_header_name_must_be_text(name):
    with pytest.raises(ValueError, match="header names must be strings"):
        _normalize_headers({name: "value"})


@pytest.mark.parametrize("name", ["", "   ", b""])
def test_header_name_must_not_be_empty(name):
    with pytest.raises(ValueError, match="empty header name"):
        _normalize_headers({name: "value"})


@pytest.mark.parametrize("value", [123, {}, object()])
def test_header_value_container_must_be_text_or_sequence(value):
    with pytest.raises(
        ValueError,
        match="must contain a string or a list of strings",
    ):
        _normalize_headers({"X-Test": value})


@pytest.mark.parametrize("value", [[1], ["ok", None], (object(),)])
def test_each_header_value_must_be_text(value):
    with pytest.raises(ValueError, match="contains a non-string value"):
        _normalize_headers({"X-Test": value})


@pytest.mark.parametrize("value", [[], ()])
def test_header_value_sequence_must_not_be_empty(value):
    with pytest.raises(ValueError, match="contains no values"):
        _normalize_headers({"X-Test": value})
