from unittest.mock import Mock, call, patch

import pytest
from scrapy.http import Request
from scrapy_flaresolverr.backends import BackendPool
from scrapy_flaresolverr.client import FlareSolverrSolution
from scrapy_flaresolverr.exceptions import (
    FlareSolverrConcurrencyError,
    FlareSolverrUnsupportedRequestError,
)
from scrapy_flaresolverr.middleware import (
    FlareSolverrMiddleware,
    _boolean,
    _optional_non_negative_float,
    _optional_string,
    _positive_float,
    _positive_int,
)
from scrapy_flaresolverr.settings import FlareSolverrSettings
from scrapy_flaresolverr.stats import FlareSolverrStats
from twisted.python.failure import Failure


def _settings(**overrides):
    values = {
        "urls": ("http://first:8191", "http://second:8191"),
        "auth_token": None,
        "max_concurrent": 2,
        "concurrency_wait_timeout": 1.0,
        "max_timeout_ms": 60_000,
        "request_timeout_seconds": 75.0,
        "disable_media": False,
    }
    values.update(overrides)
    return FlareSolverrSettings(**values)


def _middleware(**setting_overrides):
    settings = _settings(**setting_overrides)
    return FlareSolverrMiddleware(
        settings=settings,
        backend_pool=BackendPool(settings.urls),
        client=Mock(),
        stats=Mock(spec=FlareSolverrStats),
    )


def _solution():
    return FlareSolverrSolution(
        url="https://example.com/",
        status=200,
        headers={},
        response="<html></html>",
        cookies=[],
        user_agent="",
        screenshot=None,
        start_timestamp=None,
        end_timestamp=None,
        version=None,
    )


def test_from_crawler_builds_components_and_connects_signal():
    crawler = Mock()
    parsed_settings = _settings(urls=("http://one:8191",))

    with (
        patch(
            "scrapy_flaresolverr.middleware.FlareSolverrSettings.from_scrapy_settings",
            return_value=parsed_settings,
        ) as parse_settings,
        patch("scrapy_flaresolverr.middleware.BackendPool") as backend_pool_cls,
        patch("scrapy_flaresolverr.middleware.FlareSolverrClient") as client_cls,
        patch("scrapy_flaresolverr.middleware.FlareSolverrStats") as stats_cls,
    ):
        middleware = FlareSolverrMiddleware.from_crawler(crawler)

    parse_settings.assert_called_once_with(crawler.settings)
    backend_pool_cls.assert_called_once_with(parsed_settings.urls)
    client_cls.assert_called_once_with(auth_token=None)
    stats_cls.assert_called_once_with(crawler.stats)
    crawler.signals.connect.assert_called_once()
    assert middleware.settings is parsed_settings


def test_spider_opened_logs_backend_configuration():
    middleware = _middleware()
    spider = Mock()
    spider.logger = Mock()

    middleware.spider_opened(spider)

    spider.logger.info.assert_called_once_with(
        "scrapy-flaresolverr enabled with %d backend(s): %s",
        2,
        "http://first:8191/v1, http://second:8191/v1",
    )


@pytest.mark.parametrize(
    ("meta", "expected"),
    [
        ({}, None),
        ({"flaresolverr": False}, None),
        ({"flaresolverr": "yes"}, None),
        ({"use_flaresolverr": False}, None),
        ({"flaresolverr": True}, {}),
        ({"use_flaresolverr": True}, {}),
        ({"flaresolverr": {"wait_in_seconds": 1}}, {"wait_in_seconds": 1}),
    ],
)
def test_request_options(meta, expected):
    request = Request("https://example.com", meta=meta)

    assert FlareSolverrMiddleware._request_options(request) == expected


def test_request_options_returns_copy():
    options = {"wait_in_seconds": 1}
    request = Request(
        "https://example.com",
        meta={"flaresolverr": options},
    )

    parsed = FlareSolverrMiddleware._request_options(request)
    parsed["wait_in_seconds"] = 2

    assert options["wait_in_seconds"] == 1


def test_process_request_ignores_opted_out_request():
    middleware = _middleware()

    assert middleware.process_request(Request("https://example.com"), Mock()) is None


def test_process_request_rejects_non_get_before_worker_thread():
    middleware = _middleware()
    request = Request(
        "https://example.com",
        method="POST",
        meta={"flaresolverr": True},
    )

    with pytest.raises(FlareSolverrUnsupportedRequestError, match="GET requests only"):
        middleware.process_request(request, Mock())

    middleware.stats.increment.assert_called_once_with("unsupported_request")


def test_process_request_prepares_metadata_and_deferred_callbacks():
    middleware = _middleware()
    request = Request(
        "https://example.com",
        meta={"flaresolverr": True},
    )
    deferred = Mock()

    with patch(
        "scrapy_flaresolverr.middleware.deferToThread",
        return_value=deferred,
    ) as defer_to_thread:
        result = middleware.process_request(request, Mock())

    assert result is deferred
    assert request.meta["flaresolverr_used"] is True
    assert request.meta["flaresolverr_backend"] == "http://first:8191/v1"
    middleware.stats.increment.assert_called_once_with("request_count")
    defer_to_thread.assert_called_once()
    args = defer_to_thread.call_args.args
    assert args[0] == middleware._execute_flaresolverr_request
    assert args[1] == "https://example.com"
    deferred.addCallbacks.assert_called_once()


def test_prepare_request_uses_defaults_and_derived_request_timeout():
    middleware = _middleware(
        max_timeout_ms=120_000,
        request_timeout_seconds=75.0,
        disable_media=True,
    )

    prepared = middleware._prepare_request({})

    assert prepared.backend.url == "http://first:8191/v1"
    assert prepared.max_timeout_ms == 120_000
    assert prepared.request_timeout_seconds == 135.0
    assert prepared.wait_in_seconds is None
    assert prepared.disable_media is True
    assert prepared.return_screenshot is False


def test_prepare_request_uses_explicit_overrides():
    middleware = _middleware()

    prepared = middleware._prepare_request(
        {
            "backend": " http://second:8191 ",
            "max_timeout": "10000",
            "request_timeout": "30.5",
            "wait_in_seconds": "0",
            "disable_media": "yes",
            "return_screenshot": 1,
        }
    )

    assert prepared.backend.url == "http://second:8191/v1"
    assert prepared.max_timeout_ms == 10_000
    assert prepared.request_timeout_seconds == 30.5
    assert prepared.wait_in_seconds == 0.0
    assert prepared.disable_media is True
    assert prepared.return_screenshot is True


def test_prepare_request_keeps_configured_request_timeout_when_it_is_larger():
    middleware = _middleware(
        max_timeout_ms=10_000,
        request_timeout_seconds=75.0,
    )

    assert middleware._prepare_request({}).request_timeout_seconds == 75.0


def test_execute_request_acquires_calls_client_and_releases():
    middleware = _middleware()
    prepared = middleware._prepare_request({})
    semaphore = Mock()
    semaphore.acquire.return_value = True
    middleware._semaphore = semaphore
    middleware.client.request_get.return_value = "solution"

    result = middleware._execute_flaresolverr_request(
        "https://example.com",
        prepared,
    )

    assert result == "solution"
    semaphore.acquire.assert_called_once_with(timeout=1.0)
    middleware.client.request_get.assert_called_once_with(
        endpoint=prepared.backend.url,
        url="https://example.com",
        max_timeout_ms=prepared.max_timeout_ms,
        request_timeout_seconds=prepared.request_timeout_seconds,
        wait_in_seconds=None,
        disable_media=False,
        return_screenshot=False,
    )
    semaphore.release.assert_called_once_with()


def test_execute_request_releases_semaphore_when_client_raises():
    middleware = _middleware()
    prepared = middleware._prepare_request({})
    semaphore = Mock()
    semaphore.acquire.return_value = True
    middleware._semaphore = semaphore
    middleware.client.request_get.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        middleware._execute_flaresolverr_request(
            "https://example.com",
            prepared,
        )

    semaphore.release.assert_called_once_with()


def test_execute_request_raises_when_concurrency_slot_times_out():
    middleware = _middleware()
    prepared = middleware._prepare_request({})
    semaphore = Mock()
    semaphore.acquire.return_value = False
    middleware._semaphore = semaphore

    with pytest.raises(FlareSolverrConcurrencyError):
        middleware._execute_flaresolverr_request(
            "https://example.com",
            prepared,
        )

    semaphore.release.assert_not_called()
    middleware.client.request_get.assert_not_called()


def test_handle_success_records_metric_and_builds_response():
    middleware = _middleware()
    request = Request("https://example.com")
    expected_response = Mock()

    with patch(
        "scrapy_flaresolverr.middleware.build_html_response",
        return_value=expected_response,
    ) as build:
        response = middleware._handle_success(
            request=request,
            solution=_solution(),
        )

    assert response is expected_response
    middleware.stats.increment.assert_called_once_with("response_count")
    build.assert_called_once()


def test_handle_error_records_generic_error_and_reraises():
    middleware = _middleware()
    failure = Failure(RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        middleware._handle_error(failure)

    middleware.stats.increment.assert_called_once_with("request_error")


def test_handle_error_records_concurrency_timeout_and_reraises():
    middleware = _middleware()
    failure = Failure(FlareSolverrConcurrencyError("busy"))

    with pytest.raises(FlareSolverrConcurrencyError, match="busy"):
        middleware._handle_error(failure)

    assert middleware.stats.increment.call_args_list == [
        call("request_error"),
        call("concurrency_timeout"),
    ]


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), (" backend ", "backend")],
)
def test_optional_string(value, expected):
    assert _optional_string(value, name="backend") == expected


@pytest.mark.parametrize("value", [123, [], True])
def test_optional_string_rejects_non_strings(value):
    with pytest.raises(ValueError, match="must be a string"):
        _optional_string(value, name="backend")


@pytest.mark.parametrize("value", ["", "   "])
def test_optional_string_rejects_empty_strings(value):
    with pytest.raises(ValueError, match="must not be empty"):
        _optional_string(value, name="backend")


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 10), (1, 1), (" 42 ", 42)],
)
def test_positive_int(value, expected):
    assert _positive_int(value, default=10, name="max_timeout") == expected


@pytest.mark.parametrize("value", [True, False, 1.5, [], "abc"])
def test_positive_int_rejects_non_integer_values(value):
    with pytest.raises(ValueError, match="must be an integer"):
        _positive_int(value, default=10, name="max_timeout")


@pytest.mark.parametrize("value", [0, -1, "-5"])
def test_positive_int_rejects_non_positive_values(value):
    with pytest.raises(ValueError, match="greater than zero"):
        _positive_int(value, default=10, name="max_timeout")


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 10.0), (1, 1.0), (1.5, 1.5), (" 2.5 ", 2.5)],
)
def test_positive_float(value, expected):
    assert _positive_float(value, default=10.0, name="timeout") == expected


@pytest.mark.parametrize("value", [0, -1, "-0.5"])
def test_positive_float_rejects_non_positive_values(value):
    with pytest.raises(ValueError, match="greater than zero"):
        _positive_float(value, default=10.0, name="timeout")


@pytest.mark.parametrize("value", [True, "abc", [], float("nan"), float("inf")])
def test_positive_float_rejects_invalid_numeric_values(value):
    with pytest.raises(ValueError):
        _positive_float(value, default=10.0, name="timeout")


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), (0, 0.0), ("0", 0.0), (1.5, 1.5)],
)
def test_optional_non_negative_float(value, expected):
    assert _optional_non_negative_float(value, name="wait") == expected


@pytest.mark.parametrize("value", [-1, "-0.1"])
def test_optional_non_negative_float_rejects_negative_values(value):
    with pytest.raises(ValueError, match="zero or greater"):
        _optional_non_negative_float(value, name="wait")


@pytest.mark.parametrize(
    ("value", "default", "expected"),
    [
        (None, True, True),
        (None, False, False),
        (True, False, True),
        (False, True, False),
        (1, False, True),
        (0, True, False),
        ("true", False, True),
        (" YES ", False, True),
        ("on", False, True),
        ("1", False, True),
        ("false", True, False),
        (" NO ", True, False),
        ("off", True, False),
        ("0", True, False),
    ],
)
def test_boolean(value, default, expected):
    assert _boolean(value, default=default, name="flag") is expected


@pytest.mark.parametrize("value", [2, -1, "maybe", "", [], object()])
def test_boolean_rejects_invalid_values(value):
    with pytest.raises(ValueError, match="must be a boolean"):
        _boolean(value, default=False, name="flag")
