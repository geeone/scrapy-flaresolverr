from unittest.mock import Mock

import pytest
from scrapy.settings import Settings
from scrapy_flaresolverr.exceptions import FlareSolverrConfigurationError
from scrapy_flaresolverr.settings import FlareSolverrSettings


def test_settings_defaults_and_urls_list():
    parsed = FlareSolverrSettings.from_scrapy_settings(
        Settings({"FLARESOLVERR_URLS": ["http://one:8191", "http://two:8191"]})
    )

    assert parsed.urls == ("http://one:8191", "http://two:8191")
    assert parsed.auth_token is None
    assert parsed.max_concurrent == 3
    assert parsed.concurrency_wait_timeout == 120.0
    assert parsed.max_timeout_ms == 60_000
    assert parsed.request_timeout_seconds == 75.0
    assert parsed.disable_media is False


def test_settings_support_single_url_and_custom_values():
    parsed = FlareSolverrSettings.from_scrapy_settings(
        Settings(
            {
                "FLARESOLVERR_URL": " http://one:8191 ",
                "FLARESOLVERR_AUTH_TOKEN": " secret ",
                "FLARESOLVERR_MAX_CONCURRENT": "5",
                "FLARESOLVERR_CONCURRENCY_WAIT_TIMEOUT": "2.5",
                "FLARESOLVERR_MAX_TIMEOUT": "10000",
                "FLARESOLVERR_REQUEST_TIMEOUT": "20",
                "FLARESOLVERR_DISABLE_MEDIA": "true",
            }
        )
    )

    assert parsed.urls == ("http://one:8191",)
    assert parsed.auth_token == "secret"
    assert parsed.max_concurrent == 5
    assert parsed.concurrency_wait_timeout == 2.5
    assert parsed.max_timeout_ms == 10_000
    assert parsed.request_timeout_seconds == 20.0
    assert parsed.disable_media is True


def test_urls_list_takes_precedence_over_single_url():
    parsed = FlareSolverrSettings.from_scrapy_settings(
        Settings(
            {
                "FLARESOLVERR_URLS": ["http://list:8191"],
                "FLARESOLVERR_URL": "http://single:8191",
            }
        )
    )

    assert parsed.urls == ("http://list:8191",)


def test_empty_auth_token_is_normalized_to_none():
    parsed = FlareSolverrSettings.from_scrapy_settings(
        Settings(
            {
                "FLARESOLVERR_URL": "http://one:8191",
                "FLARESOLVERR_AUTH_TOKEN": "   ",
            }
        )
    )

    assert parsed.auth_token is None


def test_missing_backend_configuration_is_rejected():
    with pytest.raises(
        FlareSolverrConfigurationError,
        match="at least one backend",
    ):
        FlareSolverrSettings.from_scrapy_settings(Settings())


@pytest.mark.parametrize("value", [123, None])
def test_non_string_backend_url_is_rejected(value):
    settings = Mock()
    settings.getlist.return_value = [value]

    with pytest.raises(
        FlareSolverrConfigurationError,
        match="backend URLs must be strings",
    ):
        FlareSolverrSettings.from_scrapy_settings(settings)


def test_empty_backend_url_is_rejected():
    settings = Mock()
    settings.getlist.return_value = ["   "]

    with pytest.raises(
        FlareSolverrConfigurationError,
        match="backend URLs cannot be empty",
    ):
        FlareSolverrSettings.from_scrapy_settings(settings)


def test_getlist_errors_are_wrapped():
    settings = Mock()
    settings.getlist.side_effect = ValueError("bad list")

    with pytest.raises(
        FlareSolverrConfigurationError,
        match="must be a list of backend URLs",
    ):
        FlareSolverrSettings.from_scrapy_settings(settings)


@pytest.mark.parametrize(
    ("name", "value", "match"),
    [
        ("FLARESOLVERR_MAX_CONCURRENT", "invalid", "must be an integer"),
        ("FLARESOLVERR_MAX_CONCURRENT", 0, "greater than zero"),
        ("FLARESOLVERR_MAX_TIMEOUT", -1, "greater than zero"),
        ("FLARESOLVERR_CONCURRENCY_WAIT_TIMEOUT", "invalid", "must be numeric"),
        ("FLARESOLVERR_CONCURRENCY_WAIT_TIMEOUT", 0, "greater than zero"),
        ("FLARESOLVERR_REQUEST_TIMEOUT", -1, "greater than zero"),
        ("FLARESOLVERR_REQUEST_TIMEOUT", "nan", "must be finite"),
        ("FLARESOLVERR_REQUEST_TIMEOUT", "inf", "must be finite"),
    ],
)
def test_invalid_numeric_settings_are_rejected(name, value, match):
    settings = Settings(
        {
            "FLARESOLVERR_URL": "http://one:8191",
            name: value,
        }
    )

    with pytest.raises(FlareSolverrConfigurationError, match=match):
        FlareSolverrSettings.from_scrapy_settings(settings)


@pytest.mark.parametrize(
    ("max_timeout", "request_timeout"),
    [(60_000, 60), (60_000, 59.9), (1_000, 1)],
)
def test_request_timeout_must_exceed_flaresolverr_timeout(
    max_timeout,
    request_timeout,
):
    settings = Settings(
        {
            "FLARESOLVERR_URL": "http://one:8191",
            "FLARESOLVERR_MAX_TIMEOUT": max_timeout,
            "FLARESOLVERR_REQUEST_TIMEOUT": request_timeout,
        }
    )

    with pytest.raises(
        FlareSolverrConfigurationError,
        match="must be greater than",
    ):
        FlareSolverrSettings.from_scrapy_settings(settings)


def test_auth_token_must_be_string():
    settings = Settings(
        {
            "FLARESOLVERR_URL": "http://one:8191",
            "FLARESOLVERR_AUTH_TOKEN": 123,
        }
    )

    with pytest.raises(
        FlareSolverrConfigurationError,
        match="FLARESOLVERR_AUTH_TOKEN must be a string",
    ):
        FlareSolverrSettings.from_scrapy_settings(settings)


def test_invalid_disable_media_is_wrapped():
    settings = Mock()
    settings.getlist.return_value = ["http://one:8191"]
    settings.getint.side_effect = lambda name, default: default
    settings.getfloat.side_effect = lambda name, default: default
    settings.get.return_value = None
    settings.getbool.side_effect = ValueError("bad bool")

    with pytest.raises(
        FlareSolverrConfigurationError,
        match="FLARESOLVERR_DISABLE_MEDIA must be a boolean",
    ):
        FlareSolverrSettings.from_scrapy_settings(settings)
