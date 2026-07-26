# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-27

### Added

- Initial `scrapy-flaresolverr` release.
- Scrapy downloader middleware integration for opt-in FlareSolverr requests.
- Support for one or multiple FlareSolverr backends.
- Thread-safe round-robin backend selection and request-level backend override.
- Stateless FlareSolverr `request.get` support.
- Configurable FlareSolverr and HTTP request timeouts.
- Bounded concurrency for FlareSolverr requests.
- Request-level wait time, media disabling, and optional screenshots.
- Optional Bearer authentication for FlareSolverr endpoints or reverse proxies.
- Reconstruction of complete Scrapy `HtmlResponse` objects.
- FlareSolverr response metadata exposed through `response.meta`.
- Scrapy stats for requests, responses, errors, unsupported requests, and concurrency timeouts.
- Explicit package-specific exceptions for configuration, transport, response, concurrency, and unsupported-request failures.
- Support for Python 3.10 through 3.14 and Scrapy 2.12+.
- Unit and branch test coverage.
- Docker Compose example with two FlareSolverr workers behind an authenticated Nginx reverse proxy.
- Basic Scrapy spider example.
- CI workflows for package builds, functional tests, pre-commit checks, and coverage reporting.
- Project documentation, contribution guidelines, security policy, and roadmap.

[0.1.0]: https://github.com/geeone/scrapy-flaresolverr/releases/tag/v0.1.0
