from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import pytest
from scrapy_flaresolverr.backends import BackendPool, normalize_backend_url
from scrapy_flaresolverr.exceptions import FlareSolverrConfigurationError


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("http://localhost:8191", "http://localhost:8191/v1"),
        (" HTTP://Example.COM:8191/ ", "http://Example.COM:8191/v1"),
        ("https://example.com/api", "https://example.com/api/v1"),
        ("https://example.com/api/", "https://example.com/api/v1"),
        ("https://example.com/v1", "https://example.com/v1"),
        ("https://example.com/v1/", "https://example.com/v1"),
        ("https://example.com/api/v1/", "https://example.com/api/v1"),
    ],
)
def test_normalize_backend_url(value, expected):
    assert normalize_backend_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        123,
        "",
        "   ",
        "localhost:8191",
        "ftp://example.com",
        "http:///v1",
        "https://example.com?token=x",
        "https://example.com/#fragment",
    ],
)
def test_normalize_backend_url_rejects_invalid_values(value):
    with pytest.raises(FlareSolverrConfigurationError):
        normalize_backend_url(value)


@pytest.mark.parametrize("urls", [[], (), "http://localhost:8191"])
def test_backend_pool_requires_non_empty_sequence(urls):
    with pytest.raises(
        FlareSolverrConfigurationError,
        match="at least one backend",
    ):
        BackendPool(urls)


def test_backend_pool_deduplicates_and_round_robins():
    pool = BackendPool(
        [
            "http://first:8191",
            "http://second:8191/v1",
            "http://first:8191/",
        ]
    )

    assert [backend.url for backend in pool.backends] == [
        "http://first:8191/v1",
        "http://second:8191/v1",
    ]
    assert pool.next().url == "http://first:8191/v1"
    assert pool.next().url == "http://second:8191/v1"
    assert pool.next().url == "http://first:8191/v1"


def test_backend_pool_resolve_uses_round_robin_without_override():
    pool = BackendPool(["http://first:8191", "http://second:8191"])

    assert pool.resolve(None).url == "http://first:8191/v1"
    assert pool.resolve(None).url == "http://second:8191/v1"


def test_backend_pool_resolve_accepts_normalized_configured_override():
    pool = BackendPool(["https://example.com/api"])

    backend = pool.resolve(" https://example.com/api/ ")

    assert backend is pool.backends[0]


def test_backend_pool_resolve_rejects_unknown_override():
    pool = BackendPool(["http://first:8191"])

    with pytest.raises(
        FlareSolverrConfigurationError,
        match="Unknown FlareSolverr backend override",
    ):
        pool.resolve("http://second:8191")


def test_backend_pool_round_robin_is_thread_safe():
    pool = BackendPool(["http://first:8191", "http://second:8191"])

    with ThreadPoolExecutor(max_workers=8) as executor:
        urls = list(executor.map(lambda _: pool.next().url, range(400)))

    assert Counter(urls) == {
        "http://first:8191/v1": 200,
        "http://second:8191/v1": 200,
    }
