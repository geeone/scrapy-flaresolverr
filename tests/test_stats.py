from unittest.mock import Mock

from scrapy_flaresolverr.stats import FlareSolverrStats


def test_increment_records_prefixed_metric_and_count():
    collector = Mock()
    stats = FlareSolverrStats(collector)

    stats.increment("request_count", count=3)

    collector.inc_value.assert_called_once_with(
        "flaresolverr/request_count",
        count=3,
    )


def test_increment_is_noop_without_collector():
    FlareSolverrStats(None).increment("request_count")
