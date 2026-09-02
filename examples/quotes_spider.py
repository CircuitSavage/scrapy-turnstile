"""Example Scrapy spider using scrapy-turnstile.

Run it:

    export PEAK_API_KEY=pk_your_api_key      # Windows: set PEAK_API_KEY=...
    scrapy runspider examples/quotes_spider.py

The middleware sits in the download path. When a target page returns a
Cloudflare Turnstile challenge instead of content, the middleware detects it,
solves it through Peak, and re-issues the request with the token so parse()
receives the real page.
"""

import os

import scrapy


class ProtectedSpider(scrapy.Spider):
    name = "protected"

    # Point this at a Turnstile-protected page you are authorised to scrape.
    start_urls = ["https://protected.example.com/"]

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            # Run late in the chain, after retry/redirect handling.
            "scrapy_turnstile.TurnstileMiddleware": 585,
        },
        # Read the key from the environment; never hardcode a real key.
        "PEAK_API_KEY": os.environ.get("PEAK_API_KEY", "pk_your_api_key"),
        # Optional: route the solve through the same proxy as your crawl.
        # "PEAK_PROXY": "http://user:pass@ip:port",
    }

    def parse(self, response):
        # If a challenge was hit, it has already been solved upstream and the
        # token is available here if a custom submit is needed.
        token = response.request.meta.get("cf_turnstile_response")
        if token:
            self.logger.info("Got through Turnstile with a Peak token.")

        for quote in response.css("div.quote"):
            yield {
                "text": quote.css("span.text::text").get(),
                "author": quote.css("small.author::text").get(),
            }
