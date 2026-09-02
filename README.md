<a href="https://peak.fo/?utm_source=github&utm_medium=readme&utm_campaign=packages&utm_content=scrapy-turnstile">
  <img src="https://raw.githubusercontent.com/CircuitSavage/scrapy-turnstile/main/assets/peak-banner.png" alt="Peak — solve Cloudflare Turnstile & the 5s challenge in ~1s" width="100%">
</a>

# scrapy-turnstile

**scrapy-turnstile** is a Scrapy downloader middleware that solves Cloudflare Turnstile automatically. When a request hits a Turnstile-protected page, it detects the challenge, solves it through [Peak](https://peak.fo/?utm_source=github&utm_medium=readme&utm_campaign=packages&utm_content=scrapy-turnstile), and re-issues the request with the token so your spider gets the real page.

## Why

Scrapy makes plain HTTP requests. It has no JS engine, so a Turnstile-protected site returns a `403` or the "Just a moment..." interstitial instead of the content you asked for. The old `scrapy-cloudflare-middleware` only handled the legacy IUAM (I'm Under Attack Mode) JS challenge and is unmaintained; it does nothing for Turnstile, which is what Cloudflare now serves. cloudscraper has the same limitation: it can't solve Turnstile.

This middleware routes the Turnstile challenge to Peak, which returns a valid token. When your setup gets blocked, drop in a Peak API key and it just works.

## Powered by Peak
This package uses [Peak](https://peak.fo/?utm_source=github&utm_medium=readme&utm_campaign=packages&utm_content=scrapy-turnstile) to solve Turnstile.
- Solve Cloudflare Turnstile & the 5s challenge in about a second
- Pay only for successful solves — from $1 / 1,000
- 1,000 free solves to start, no card.
→ [Get your free API key](https://peak.fo/?utm_source=github&utm_medium=readme&utm_campaign=packages&utm_content=scrapy-turnstile) · [Docs](https://peak.fo/docs/turnstile?utm_source=github&utm_medium=readme&utm_campaign=packages&utm_content=scrapy-turnstile) · [Pricing](https://peak.fo/pricing?utm_source=github&utm_medium=readme&utm_campaign=packages&utm_content=scrapy-turnstile)

## Install

```bash
pip install scrapy-turnstile
```

## Quickstart

Add the middleware to your project's `settings.py` and set your Peak key:

```python
# settings.py
DOWNLOADER_MIDDLEWARES = {
    "scrapy_turnstile.TurnstileMiddleware": 585,
}

PEAK_API_KEY = "pk_your_api_key"   # better: read from an env var
# PEAK_PROXY = "http://user:pass@ip:port"   # optional, routed to Peak
```

Or per-spider:

```python
import os
import scrapy


class ProtectedSpider(scrapy.Spider):
    name = "protected"
    start_urls = ["https://protected.example.com/"]

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_turnstile.TurnstileMiddleware": 585,
        },
        "PEAK_API_KEY": os.environ["PEAK_API_KEY"],
    }

    def parse(self, response):
        # The challenge, if any, was already solved upstream.
        yield {"title": response.css("title::text").get()}
```

```bash
export PEAK_API_KEY=pk_your_api_key
scrapy runspider examples/quotes_spider.py
```

A runnable spider is in [`examples/quotes_spider.py`](examples/quotes_spider.py).

## How it works

1. `process_response` inspects every response for Turnstile markers (`cf-turnstile`, the `challenges.cloudflare.com/turnstile` script, the "Just a moment" interstitial).
2. On a match it extracts the `data-sitekey` and the request URL.
3. It calls Peak: `POST https://api.peak.fo/solve` with `{"task_type": "turnstiletask", "sitekey": ..., "url": ...}` and header `X-API-Key`.
4. It re-issues the original request with the returned token injected as the `cf-turnstile-response` form field, and also on `request.meta["cf_turnstile_response"]` for custom submits.
5. A `meta` flag stops the retried request from being re-processed, so there are no loops.

Peak also supports the Cloudflare 5s interstitial via `task_type: "cloudflare5stask"`.

## Settings

| Setting | Default | Purpose |
| --- | --- | --- |
| `PEAK_API_KEY` | (required) | Your Peak key, format `pk_...`. |
| `PEAK_PROXY` | `None` | Proxy string forwarded to Peak so the solve matches your crawl IP. |
| `PEAK_API_URL` | `https://api.peak.fo/solve` | Override the solve endpoint. |
| `PEAK_TURNSTILE_FIELD` | `cf-turnstile-response` | Form field the token is injected into. |
| `PEAK_TURNSTILE_MAX_RETRIES` | `2` | Max solve attempts per request before giving up. |

## Legitimate use

For automation, QA, and scraping public data you are allowed to access. Respect each target's Terms of Service and `robots.txt`, and rate-limit yourself. Do not use this for credential stuffing or to access data you have no right to.

## License

MIT — see [LICENSE](LICENSE).
