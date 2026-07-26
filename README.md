# scrapy-flaresolverr

[![PyPI](https://img.shields.io/pypi/v/scrapy-flaresolverr)](https://pypi.org/project/scrapy-flaresolverr/)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://www.python.org/)
[![Scrapy](https://img.shields.io/badge/Scrapy-2.12%2B-60A839)](https://scrapy.org/)
[![License](https://img.shields.io/github/license/geeone/scrapy-flaresolverr)](LICENSE)
[![Build Status](https://github.com/geeone/scrapy-flaresolverr/actions/workflows/build.yml/badge.svg)](https://github.com/geeone/scrapy-flaresolverr/actions/workflows/build.yml)
[![Functional Tests](https://github.com/geeone/scrapy-flaresolverr/actions/workflows/test.yml/badge.svg)](https://github.com/geeone/scrapy-flaresolverr/actions/workflows/test.yml)
[![Pre-commit Checks](https://github.com/geeone/scrapy-flaresolverr/actions/workflows/pre-commit.yml/badge.svg)](https://github.com/geeone/scrapy-flaresolverr/actions/workflows/pre-commit.yml)
[![Codecov](https://codecov.io/gh/geeone/scrapy-flaresolverr/branch/main/graph/badge.svg)](https://codecov.io/gh/geeone/scrapy-flaresolverr)

A Scrapy downloader middleware for routing opt-in requests through one or more
[FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) backends.

`scrapy-flaresolverr` provides a small integration layer between Scrapy and the
FlareSolverr v1 API, with support for multiple backends, round-robin selection,
request-level options, bounded concurrency, response reconstruction, and Scrapy
stats.

## Features

- Stateless FlareSolverr `request.get` integration
- Multiple FlareSolverr backends with thread-safe round-robin selection
- Request-level backend override
- Optional Bearer authentication
- Configurable request and FlareSolverr timeouts
- Configurable concurrency limits
- Request-level media disabling and wait time
- Optional screenshot return
- Reconstruction of complete Scrapy `HtmlResponse` objects
- FlareSolverr response metadata exposed through `response.meta`
- Scrapy stats for requests, responses, errors, and concurrency timeouts
- Explicit package-specific exceptions for configuration, transport, response,
  concurrency, and unsupported-request failures

## Requirements

- Python 3.10+
- Scrapy 2.12+
- requests 2.31+

The package supports Scrapy 2.x and currently declares:

```text
Python >=3.10
Scrapy >=2.12,<3
requests >=2.31,<3
```

### CI compatibility matrix

The build and functional test workflows cover the following compatibility
baseline:

| Python | Scrapy 2.12.x | Latest supported Scrapy 2.x |
| --- | :---: | :---: |
| 3.10 | ✓ | ✓ |
| 3.11 | ✓ | ✓ |
| 3.12 | ✓ | ✓ |
| 3.13 | — | ✓ |
| 3.14 | — | ✓ |

The minimum Scrapy line is tested on Python versions supported by that
combination, while current Scrapy 2.x is tested across all supported Python
versions.

## Installation

Install from PyPI:

```bash
pip install scrapy-flaresolverr
```

For local development:

```bash
git clone https://github.com/geeone/scrapy-flaresolverr.git
cd scrapy-flaresolverr
pip install -r requirements-dev.txt
```

## Quick start

Enable the downloader middleware in your Scrapy settings:

```python
DOWNLOADER_MIDDLEWARES = {
    "scrapy_flaresolverr.middleware.FlareSolverrMiddleware": 100,
}

FLARESOLVERR_URLS = [
    "http://127.0.0.1:8191",
]

FLARESOLVERR_MAX_CONCURRENT = 3
```

Then opt individual requests into FlareSolverr:

```python
yield scrapy.Request(
    "https://example.com",
    meta={"flaresolverr": True},
)
```

Request-specific options can be passed as a dictionary:

```python
yield scrapy.Request(
    "https://example.com",
    meta={
        "flaresolverr": {
            "disable_media": True,
            "wait_in_seconds": 2,
            "return_screenshot": True,
        },
    },
)
```

Requests without the `flaresolverr` opt-in continue through Scrapy's normal
downloader middleware chain.

## Configuration

### Backend URLs

Configure one or more FlareSolverr backends:

```python
FLARESOLVERR_URLS = [
    "http://127.0.0.1:8191",
    "http://127.0.0.1:8192",
]
```

Configured backend URLs are normalized to the FlareSolverr `/v1` endpoint.

For example:

```text
http://127.0.0.1:8191       -> http://127.0.0.1:8191/v1
http://127.0.0.1:8191/fs1/  -> http://127.0.0.1:8191/fs1/v1
```

A single backend can alternatively be configured with:

```python
FLARESOLVERR_URL = "http://127.0.0.1:8191"
```

When multiple backends are configured, requests are distributed using
round-robin selection.

### Authentication

If the FlareSolverr endpoint or an upstream reverse proxy requires Bearer
authentication:

```python
FLARESOLVERR_AUTH_TOKEN = "your-token"
```

The token is sent as:

```text
Authorization: Bearer <token>
```

### Settings reference

| Setting | Default | Description |
| --- | --- | --- |
| `FLARESOLVERR_URLS` | — | List of FlareSolverr backend URLs |
| `FLARESOLVERR_URL` | — | Single-backend fallback when `FLARESOLVERR_URLS` is not set |
| `FLARESOLVERR_AUTH_TOKEN` | `None` | Optional Bearer token |
| `FLARESOLVERR_MAX_CONCURRENT` | `3` | Maximum number of concurrent FlareSolverr calls |
| `FLARESOLVERR_CONCURRENCY_WAIT_TIMEOUT` | `120.0` | Maximum seconds to wait for a concurrency slot |
| `FLARESOLVERR_MAX_TIMEOUT` | `60000` | FlareSolverr `maxTimeout` in milliseconds |
| `FLARESOLVERR_REQUEST_TIMEOUT` | `75.0` | HTTP timeout in seconds for the call to FlareSolverr |
| `FLARESOLVERR_DISABLE_MEDIA` | `False` | Disable media by default for FlareSolverr requests |

`FLARESOLVERR_REQUEST_TIMEOUT` must be greater than
`FLARESOLVERR_MAX_TIMEOUT` converted to seconds.

## Request options

Per-request behavior is configured through `request.meta["flaresolverr"]`.

```python
yield scrapy.Request(
    "https://example.com",
    meta={
        "flaresolverr": {
            "backend": "http://127.0.0.1:8191",
            "max_timeout": 90_000,
            "request_timeout": 110,
            "wait_in_seconds": 2,
            "disable_media": True,
            "return_screenshot": False,
        },
    },
)
```

| Option | Type | Description |
| --- | --- | --- |
| `backend` | `str` | Use a specific configured backend for this request |
| `max_timeout` | `int` | Override FlareSolverr `maxTimeout` in milliseconds |
| `request_timeout` | `float` | Override the HTTP timeout for the FlareSolverr call |
| `wait_in_seconds` | `float` | Additional FlareSolverr wait time; may be zero |
| `disable_media` | `bool` | Override the global media-loading setting |
| `return_screenshot` | `bool` | Request a screenshot from FlareSolverr |

A backend override must resolve to one of the configured backends.

## Multiple backends

Multiple backends are selected in round-robin order:

```python
FLARESOLVERR_URLS = [
    "http://127.0.0.1:8191/fs1/",
    "http://127.0.0.1:8191/fs2/",
]
```

The backend selected for a request is exposed as:

```python
response.meta["flaresolverr_backend"]
```

A request can explicitly target one configured backend:

```python
yield scrapy.Request(
    "https://example.com",
    meta={
        "flaresolverr": {
            "backend": "http://127.0.0.1:8191/fs2/",
        },
    },
)
```

## Response metadata

Successful FlareSolverr requests are returned as Scrapy `HtmlResponse`
instances.

The middleware marks the request with:

```python
response.meta["flaresolverr_used"]
response.meta["flaresolverr_backend"]
```

Additional FlareSolverr response data is available under:

```python
response.meta["flaresolverr_response"]
```

The dictionary contains:

```python
{
    "cookies": ...,
    "user_agent": ...,
    "screenshot": ...,
    "start_timestamp": ...,
    "end_timestamp": ...,
    "version": ...,
}
```

The reconstructed response also includes the `flaresolverr` response flag.

Because FlareSolverr returns decoded HTML, transport-specific headers such as
`Content-Encoding`, `Content-Length`, and `Transfer-Encoding` are not copied to
the reconstructed Scrapy response. The response body is encoded as UTF-8 and
the `Content-Type` charset is normalized accordingly.

## Stats

The middleware records counters through Scrapy's stats collector:

```text
flaresolverr/request_count
flaresolverr/response_count
flaresolverr/request_error
flaresolverr/concurrency_timeout
flaresolverr/unsupported_request
```

They can be inspected together with the rest of the spider's Scrapy stats.

## Error handling

`scrapy-flaresolverr` does not silently fall back to Scrapy's normal downloader
after a FlareSolverr failure. Errors are propagated through package-specific
exceptions:

- `FlareSolverrConfigurationError`
- `FlareSolverrConcurrencyError`
- `FlareSolverrRequestError`
- `FlareSolverrResponseError`
- `FlareSolverrUnsupportedRequestError`

This keeps FlareSolverr failures explicit and observable by the calling spider
or Scrapy error handling.

## Current limitations

Version `0.1.0` supports stateless `GET` requests only.

Current limitations include:

- no FlareSolverr sessions or session affinity
- no proxy configuration or proxy affinity
- no automatic backend failover or health-based routing

See the [roadmap](docs/roadmap.md) for planned development.

## Examples

The repository includes runnable examples:

- [Basic spider](examples/basic_spider/) — middleware configuration, request
  options, and selected-backend metadata
- [Docker Compose](examples/docker-compose/) — two FlareSolverr workers behind
  an authenticated Nginx reverse proxy

The Docker Compose example can be used together with the basic spider to
exercise multiple-backend routing locally.

## Development

Install the development dependencies:

```bash
pip install -r requirements-dev.txt
```

Run the test suite:

```bash
pytest --cov=scrapy_flaresolverr --cov-report=term-missing tests/
```

Run the configured pre-commit checks:

```bash
pre-commit run --all-files
```

Or install the hooks locally:

```bash
pre-commit install
```

The project uses Ruff for linting and formatting, mypy for static type checking,
pytest for testing, and pytest-cov for coverage.

For an overview of the internal design, see the
[architecture documentation](docs/architecture.md).

## Contributing

Bug reports, feature requests, and pull requests are welcome.

Before contributing, please review:

- [Contributing guidelines](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)

Security-related issues should be reported according to the
[Security Policy](SECURITY.md), rather than through a public issue.

Release history is documented in the [Changelog](CHANGELOG.md).

## Support the project

If `scrapy-flaresolverr` is useful to you, consider giving the project a ⭐ on
GitHub.

## License

MIT. See [LICENSE](LICENSE) for details.
