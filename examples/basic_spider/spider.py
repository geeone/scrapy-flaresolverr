import scrapy


class FlareSolverrExampleSpider(scrapy.Spider):
    name = "flaresolverr_example"

    def _start_request(self):
        return scrapy.Request(
            "https://example.com",
            meta={
                "flaresolverr": {
                    "disable_media": True,
                },
            },
        )

    async def start(self):
        yield self._start_request()

    def start_requests(self):
        yield self._start_request()

    def parse(self, response):
        yield {
            "url": response.url,
            "status": response.status,
            "title": response.css("title::text").get(),
            "backend": response.meta["flaresolverr_backend"],
        }
