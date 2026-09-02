"""Scrapy downloader middleware that solves Cloudflare Turnstile via Peak.

Scrapy's HTTP client has no JS engine, so a Turnstile-protected page returns
a 403 / "Just a moment" interstitial instead of the content. This middleware
detects that page, extracts the sitekey, asks Peak for a token, and re-issues
the request with the token injected as ``cf-turnstile-response`` so the spider
transparently gets through.

The Scrapy import is deferred so the pure helpers and the Peak client stay
importable (and testable) without Scrapy installed.
"""

from __future__ import annotations

import logging
from typing import Optional

from .detect import extract_sitekey, is_turnstile_challenge
from .peak import PeakClient, PeakError

logger = logging.getLogger("scrapy_turnstile")

# request.meta keys.
META_SOLVED = "peak_turnstile_solved"       # set once we retried, stops loops
META_TOKEN = "cf_turnstile_response"        # token exposed to callbacks
META_ATTEMPTS = "peak_turnstile_attempts"


def _load_request_cls():
    """Import scrapy.Request lazily; raise a clear error if missing."""
    try:
        from scrapy import Request  # type: ignore

        return Request
    except ImportError as exc:  # pragma: no cover - env without scrapy
        raise ImportError(
            "scrapy is required to run TurnstileMiddleware. "
            "Install it with: pip install scrapy"
        ) from exc


class TurnstileMiddleware:
    """Downloader middleware. Wire it into DOWNLOADER_MIDDLEWARES.

    Settings:
      PEAK_API_KEY   required, format pk_...
      PEAK_PROXY     optional proxy string passed to Peak
      PEAK_API_URL   optional override of the solve endpoint
      PEAK_TURNSTILE_FIELD    form field name for the token
                              (default "cf-turnstile-response")
      PEAK_TURNSTILE_MAX_RETRIES  max solve attempts per request (default 2)
    """

    def __init__(
        self,
        api_key: str,
        proxy: Optional[str] = None,
        api_url: Optional[str] = None,
        token_field: str = "cf-turnstile-response",
        max_retries: int = 2,
        client: Optional[PeakClient] = None,
        request_cls=None,
    ) -> None:
        self.token_field = token_field
        self.max_retries = max_retries
        self.request_cls = request_cls
        if client is not None:
            self.client = client
        else:
            kwargs = {"api_key": api_key, "proxy": proxy}
            if api_url:
                kwargs["api_url"] = api_url
            self.client = PeakClient(**kwargs)

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        api_key = settings.get("PEAK_API_KEY")
        if not api_key:
            from scrapy.exceptions import NotConfigured  # type: ignore

            raise NotConfigured(
                "PEAK_API_KEY is not set. Get a free key at https://peak.fo "
                "."
            )
        return cls(
            api_key=api_key,
            proxy=settings.get("PEAK_PROXY"),
            api_url=settings.get("PEAK_API_URL"),
            token_field=settings.get(
                "PEAK_TURNSTILE_FIELD", "cf-turnstile-response"
            ),
            max_retries=settings.getint("PEAK_TURNSTILE_MAX_RETRIES", 2),
        )

    def _body_text(self, response) -> str:
        text = getattr(response, "text", None)
        if text is not None:
            return text
        body = getattr(response, "body", b"")
        if isinstance(body, bytes):
            return body.decode("utf-8", "replace")
        return body or ""

    def process_response(self, request, response, spider):
        # Already solved on a prior pass: let the real response through.
        if request.meta.get(META_SOLVED):
            return response

        body = self._body_text(response)
        status = getattr(response, "status", None)
        if not is_turnstile_challenge(body, status):
            return response

        attempts = request.meta.get(META_ATTEMPTS, 0)
        if attempts >= self.max_retries:
            logger.warning(
                "Turnstile still blocking %s after %d Peak attempt(s); "
                "passing challenge response through.",
                request.url,
                attempts,
            )
            return response

        sitekey = extract_sitekey(body)
        if not sitekey:
            logger.warning(
                "Turnstile challenge detected on %s but no sitekey found.",
                request.url,
            )
            return response

        logger.info(
            "Turnstile challenge on %s (sitekey %s); solving via Peak.",
            request.url,
            sitekey,
        )
        try:
            token = self.client.solve(sitekey, request.url)
        except PeakError as exc:
            logger.error("Peak failed to solve %s: %s", request.url, exc)
            return response

        return self._build_retry(request, token)

    def _build_retry(self, request, token: str):
        """Re-issue the original request carrying the solved token.

        The token is injected as the ``cf-turnstile-response`` form field and
        also exposed on request.meta so a custom callback can place it wherever
        the target page's Turnstile callback expects it.
        """
        request_cls = self.request_cls or _load_request_cls()

        meta = dict(request.meta)
        meta[META_SOLVED] = True
        meta[META_TOKEN] = token
        meta[META_ATTEMPTS] = request.meta.get(META_ATTEMPTS, 0) + 1

        # Inject the token into the form body so the submit carries it.
        from urllib.parse import urlencode

        new_body = urlencode({self.token_field: token}).encode("utf-8")
        headers = dict(request.headers or {})
        headers["Content-Type"] = b"application/x-www-form-urlencoded"

        return request_cls(
            url=request.url,
            method="POST",
            body=new_body,
            headers=headers,
            meta=meta,
            callback=request.callback,
            errback=request.errback,
            dont_filter=True,
        )
