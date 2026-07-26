DOWNLOADER_MIDDLEWARES = {
    "scrapy_flaresolverr.middleware.FlareSolverrMiddleware": 100,
}

FLARESOLVERR_URLS = [
    "http://127.0.0.1:8191/fs1/",
    "http://127.0.0.1:8191/fs2/",
]

# Required when using the Docker Compose example; must match the value in .env.
FLARESOLVERR_AUTH_TOKEN = "your-token"

FLARESOLVERR_MAX_CONCURRENT = 3
