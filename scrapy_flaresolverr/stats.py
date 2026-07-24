"""Small Scrapy stats adapter used by the v0.1 middleware."""

from __future__ import annotations

from typing import Protocol


class StatsCollectorLike(Protocol):
    """Minimal interface required from a Scrapy stats collector."""

    def inc_value(
        self,
        key: str,
        count: int = 1,
        start: int = 0,
    ) -> None: ...


class FlareSolverrStats:
    """Record stable FlareSolverr metric names through Scrapy stats."""

    PREFIX = "flaresolverr"

    def __init__(self, collector: StatsCollectorLike | None) -> None:
        self._collector = collector

    def increment(self, name: str, count: int = 1) -> None:
        """Increment a FlareSolverr metric when a collector is available."""

        if self._collector is not None:
            self._collector.inc_value(
                f"{self.PREFIX}/{name}",
                count=count,
            )
