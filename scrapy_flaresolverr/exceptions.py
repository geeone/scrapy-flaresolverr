"""Exceptions raised by scrapy-flaresolverr."""


class FlareSolverrError(Exception):
    """Base exception for all package-specific failures."""


class FlareSolverrConfigurationError(FlareSolverrError):
    """Raised when middleware settings or request options are invalid."""


class FlareSolverrConcurrencyError(FlareSolverrError):
    """Raised when the middleware cannot acquire a concurrency slot."""


class FlareSolverrRequestError(FlareSolverrError):
    """Raised when a request to the FlareSolverr API fails."""


class FlareSolverrResponseError(FlareSolverrError):
    """Raised when FlareSolverr returns an invalid or unsuccessful response."""


class FlareSolverrUnsupportedRequestError(FlareSolverrError):
    """Raised when a Scrapy request is unsupported by the current release."""
