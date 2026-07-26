# Architecture

`FlareSolverrMiddleware` is the Scrapy-facing entry point. It delegates backend
selection, API communication, and response conversion to smaller components.

```text
Scrapy Request
    |
    v
FlareSolverrMiddleware
    |-- BackendPool
    |-- concurrency semaphore
    |-- FlareSolverrClient
    `-- build_html_response
            |
            v
      Scrapy HtmlResponse
```

## Threading model

The FlareSolverr API call uses the synchronous `requests` library. The
middleware sends that blocking work through Twisted's `deferToThread`, keeping
it outside the reactor thread.

A bounded semaphore limits concurrent FlareSolverr requests independently from
Scrapy's normal downloader concurrency.

## Backend selection

Configured backend URLs are normalized to `/v1` and deduplicated. Requests use
round-robin selection unless they explicitly select one of the configured
backends.

Backend health tracking and failover are outside the current implementation.
See the [roadmap](roadmap.md) for planned reliability features.

## Failure behavior

Package-specific failures are raised rather than converted to `None`. In a
downloader middleware, returning `None` would continue the normal download chain
and could cause an unintended direct request.

## Response conversion

FlareSolverr returns rendered text, status, headers, cookies, and browser
metadata. The middleware returns an `HtmlResponse` and drops transport headers
such as `Content-Encoding` and `Content-Length`, because FlareSolverr has already
decoded the body.
