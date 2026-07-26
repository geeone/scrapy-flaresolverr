# Roadmap

This roadmap describes the current direction of the project. Scope and release
boundaries may change as the implementation evolves.

## v0.1.0 — Stateless middleware foundation

- Repository and package foundation
- `DOWNLOADER_MIDDLEWARES` integration
- One or multiple FlareSolverr backends
- Stateless `GET` requests
- Round-robin backend selection
- Request-level backend override
- Concurrency limiting
- Explicit error propagation
- Complete `HtmlResponse` conversion
- Scrapy stats and response metadata
- Unit and branch test coverage
- Docker Compose deployment example

## v0.2.0 — Sessions

- Optional FlareSolverr sessions
- Session scopes such as spider, domain, and cookiejar
- Backend/session affinity
- Cookie and user-agent context
- Session lifecycle and cleanup

## v0.3.0 — Proxies

- Optional global and named proxies
- Proxy URL parsing and validation
- Proxy/session affinity
- Request-level proxy selection

## v0.4.0 — Reliability and observability

- Request retries
- Backend failover
- Session recreation during failover
- Backend health state and circuit-breaker foundations
- Extended Scrapy stats and diagnostics

## Later — Extended integration

- Optional Scrapy add-on for automatic middleware configuration
- More flexible request routing
- Deployment and observability tooling
