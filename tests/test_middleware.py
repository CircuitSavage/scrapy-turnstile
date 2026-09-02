"""Tests for scrapy-turnstile.

No Scrapy and no network required: Peak's HTTP layer is monkeypatched and the
Scrapy Request/Response are minimal fakes. Run with:

    python -m unittest discover -s tests -v
"""

import os
import sys
import unittest
from unittest import mock
from urllib.parse import parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapy_turnstile.detect import extract_sitekey, is_turnstile_challenge
from scrapy_turnstile.middleware import (
    META_SOLVED,
    META_TOKEN,
    TurnstileMiddleware,
)
from scrapy_turnstile.peak import PeakClient, build_solve_payload

TARGET_URL = "https://shop.example.com/checkout"
SITEKEY = "0x4AAAAAAABkMYinukE8nzYS"
TEST_TOKEN = "XXXX.TEST"

CHALLENGE_HTML = f"""
<!doctype html><html><head><title>Just a moment...</title></head>
<body>
  <div class="cf-turnstile" data-sitekey="{SITEKEY}" data-callback="onSolve"></div>
  <script src="https://challenges.cloudflare.com/turnstile/v0/api.js"></script>
</body></html>
"""

REAL_HTML = "<html><body><h1>Welcome to the shop</h1></body></html>"


class FakeHeaders(dict):
    """Behaves enough like scrapy.http.Headers for the middleware."""


class FakeResponse:
    def __init__(self, url, status, text):
        self.url = url
        self.status = status
        self.text = text
        self.body = text.encode("utf-8")


class FakeRequest:
    """Minimal stand-in for scrapy.Request."""

    def __init__(
        self,
        url,
        method="GET",
        body=b"",
        headers=None,
        meta=None,
        callback=None,
        errback=None,
        dont_filter=False,
    ):
        self.url = url
        self.method = method
        self.body = body
        self.headers = headers or FakeHeaders()
        self.meta = meta or {}
        self.callback = callback
        self.errback = errback
        self.dont_filter = dont_filter


def _parse_captured(mock_post):
    """Return the payload dict passed to PeakClient._post."""
    args, _ = mock_post.call_args
    return args[0]


class DetectionTests(unittest.TestCase):
    def test_detects_challenge(self):
        self.assertTrue(is_turnstile_challenge(CHALLENGE_HTML, status=403))

    def test_ignores_real_page(self):
        self.assertFalse(is_turnstile_challenge(REAL_HTML, status=200))

    def test_extracts_sitekey(self):
        self.assertEqual(extract_sitekey(CHALLENGE_HTML), SITEKEY)

    def test_no_sitekey_on_real_page(self):
        self.assertIsNone(extract_sitekey(REAL_HTML))


class PayloadTests(unittest.TestCase):
    def test_body_shape(self):
        payload = build_solve_payload(SITEKEY, TARGET_URL)
        self.assertEqual(payload["task_type"], "turnstiletask")
        self.assertEqual(payload["sitekey"], SITEKEY)
        self.assertEqual(payload["url"], TARGET_URL)
        self.assertNotIn("proxy", payload)

    def test_proxy_included_when_set(self):
        payload = build_solve_payload(SITEKEY, TARGET_URL, proxy="http://p:1")
        self.assertEqual(payload["proxy"], "http://p:1")


class MiddlewareFlowTests(unittest.TestCase):
    def _middleware(self, client):
        return TurnstileMiddleware(
            api_key="pk_test",
            client=client,
            request_cls=FakeRequest,
        )

    def test_full_solve_flow(self):
        """Detect -> POST correct body to Peak -> retry Request with token."""
        client = PeakClient(api_key="pk_test")

        with mock.patch.object(
            PeakClient,
            "_post",
            return_value={"success": True, "data": {"token": TEST_TOKEN}},
        ) as mock_post:
            mw = self._middleware(client)
            request = FakeRequest(url=TARGET_URL)
            response = FakeResponse(TARGET_URL, 403, CHALLENGE_HTML)

            result = mw.process_response(request, response, spider=None)

            # (b) Peak was called with the correct body.
            self.assertTrue(mock_post.called)
            payload = _parse_captured(mock_post)
            self.assertEqual(payload["task_type"], "turnstiletask")
            self.assertEqual(payload["sitekey"], SITEKEY)
            self.assertEqual(payload["url"], TARGET_URL)

        # (c) A retry Request was produced carrying the token.
        self.assertIsInstance(result, FakeRequest)
        self.assertEqual(result.url, TARGET_URL)
        self.assertEqual(result.method, "POST")
        self.assertEqual(result.meta[META_TOKEN], TEST_TOKEN)
        self.assertTrue(result.meta[META_SOLVED])
        # Token is injected as the cf-turnstile-response form field.
        form = parse_qs(result.body.decode("utf-8"))
        self.assertEqual(form["cf-turnstile-response"], [TEST_TOKEN])

    def test_real_page_passes_through(self):
        client = PeakClient(api_key="pk_test")
        with mock.patch.object(PeakClient, "_post") as mock_post:
            mw = self._middleware(client)
            request = FakeRequest(url=TARGET_URL)
            response = FakeResponse(TARGET_URL, 200, REAL_HTML)
            result = mw.process_response(request, response, spider=None)
        self.assertIs(result, response)
        self.assertFalse(mock_post.called)

    def test_solved_request_not_reprocessed(self):
        """A response for an already-solved request is passed through."""
        client = PeakClient(api_key="pk_test")
        with mock.patch.object(PeakClient, "_post") as mock_post:
            mw = self._middleware(client)
            request = FakeRequest(url=TARGET_URL, meta={META_SOLVED: True})
            response = FakeResponse(TARGET_URL, 403, CHALLENGE_HTML)
            result = mw.process_response(request, response, spider=None)
        self.assertIs(result, response)
        self.assertFalse(mock_post.called)

    def test_solve_returns_token_from_client(self):
        """PeakClient.solve unwraps data.token from the mocked response."""
        client = PeakClient(api_key="pk_test")
        with mock.patch.object(
            PeakClient,
            "_post",
            return_value={"success": True, "data": {"token": TEST_TOKEN}},
        ):
            token = client.solve(SITEKEY, TARGET_URL)
        self.assertEqual(token, TEST_TOKEN)


if __name__ == "__main__":
    unittest.main(verbosity=2)
