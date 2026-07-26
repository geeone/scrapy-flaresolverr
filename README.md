# scrapy-flaresolverr

Production-oriented Scrapy downloader middleware for routing opt-in requests through one or more [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) backends.

> **Project status:** early development (`0.1.0a0`). The public API may change before the first stable release.

## Why

FlareSolverr exposes a browser-backed HTTP API, but Scrapy projects still need to handle middleware integration, backend selection, blocking I/O, concurrency limits, response conversion, and error propagation. `scrapy-flaresolverr` provides those Scrapy-native building blocks.

## v0.1 scope

- Opt-in downloader middleware
- One or multiple FlareSolverr backends
- Thread-safe round-robin backend selection
- Stateless `request.get` calls
- Blocking API calls executed outside the Twisted reactor thread
- Configurable concurrency limit
- Complete `HtmlResponse` conversion, including status and safe response headers
- Explicit package-specific exceptions
- Basic Scrapy stats
- Authenticated reverse-proxy deployment example

Sessions and proxies are intentionally deferred to later releases. See [the roadmap](docs/roadmap.md).

## Installation

PyPI publishing is planned for the first `v0.1.0` release. During early development, install the package from a local checkout:

```bash
git clone https://github.com/crawlerland/scrapy-flaresolverr.git
cd scrapy-flaresolverr
python -m pip install -e ".[dev]"
```

## Configuration

Enable the middleware in Scrapy settings:

```python
DOWNLOADER_MIDDLEWARES = {
    "scrapy_flaresolverr.middleware.FlareSolverrMiddleware": 100,
}

FLARESOLVERR_URLS = [
    "http://127.0.0.1:8191/fs1/",
    "http://127.0.0.1:8191/fs2/",
]

# Optional when FlareSolverr is protected by an authenticated reverse proxy.
FLARESOLVERR_AUTH_TOKEN = "change-me"

FLARESOLVERR_MAX_CONCURRENT = 3
FLARESOLVERR_MAX_TIMEOUT = 60_000
FLARESOLVERR_REQUEST_TIMEOUT = 75
FLARESOLVERR_DISABLE_MEDIA = False
```

A URL may point either to a backend base path or directly to `/v1`; the middleware normalizes it to the FlareSolverr API endpoint.

## Usage

Legacy boolean opt-in:

```python
import scrapy


yield scrapy.Request(
    "https://example.com",
    meta={"use_flaresolverr": True},
)
```

Namespaced request options:

```python
yield scrapy.Request(
    "https://example.com",
    meta={
        "flaresolverr": {
            "max_timeout": 45_000,
            "request_timeout": 60,
            "wait_in_seconds": 2,
            "disable_media": True,
            "return_screenshot": False,
        }
    },
)
```

A specific configured backend may be selected per request:

```python
yield scrapy.Request(
    "https://example.com",
    meta={
        "flaresolverr": {
            "backend": "http://127.0.0.1:8191/fs2/",
        }
    },
)
```

Successful responses include:

```python
response.flags                 # contains "flaresolverr"
response.meta["flaresolverr_backend"]
response.meta["flaresolverr_response"]["cookies"]
response.meta["flaresolverr_response"]["user_agent"]
```

## Failure behavior

The middleware raises explicit exceptions when FlareSolverr cannot process a request. It does **not** silently fall back to Scrapy's normal downloader, because that could use a different IP address or user agent and return a challenge page.

Retries and backend failover are planned for `v0.4.0`.

## Example deployment

The [`examples/docker-compose`](examples/docker-compose) directory runs two FlareSolverr workers behind an authenticated Nginx reverse proxy:

```bash
cd examples/docker-compose
cp .env.example .env
docker compose up -d
```

The proxy binds to `127.0.0.1` by default. Do not expose an unauthenticated FlareSolverr API to the public internet.

## Development

```bash
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy src
pytest
python -m build
```

## Responsible use

Use this software only where you are authorized to collect data. Respect applicable laws, website terms, access controls, rate limits, privacy obligations, and robots directives where applicable.

## License

MIT
