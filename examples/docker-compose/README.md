# Two-backend FlareSolverr example

This example starts two FlareSolverr workers behind an authenticated Nginx reverse proxy.

```bash
cp .env.example .env
# Replace FLARESOLVERR_AUTH_TOKEN with a strong random value.
docker compose up -d
```

Endpoints:

- `http://127.0.0.1:8191/fs1/v1`
- `http://127.0.0.1:8191/fs2/v1`

Both require:

```text
Authorization: Bearer <FLARESOLVERR_AUTH_TOKEN>
```

When using this setup with the basic spider example, configure:

```python
FLARESOLVERR_URLS = [
    "http://127.0.0.1:8191/fs1/",
    "http://127.0.0.1:8191/fs2/",
]

FLARESOLVERR_AUTH_TOKEN = "your-token"
```

Use the same authentication token as configured in `.env`.

`scrapy-flaresolverr` automatically normalizes the configured backend URLs to the FlareSolverr `/v1` API endpoints.

The service is intentionally bound to localhost. Keep FlareSolverr private or behind authenticated infrastructure.
