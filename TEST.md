# Testing

The suite uses only the Python standard library (`unittest` + `unittest.mock`).
It requires **no live Peak key, no network, and no Scrapy install**: the Peak
HTTP layer (`PeakClient._post`) is monkeypatched to return
`{"success": true, "data": {"token": "XXXX.TEST"}}`, and Scrapy's
`Request`/`Response` are replaced with minimal fakes.

## What is asserted

`tests/test_middleware.py` covers the core logic end to end:

- **(a) Detection** — `is_turnstile_challenge()` flags a Cloudflare
  "Just a moment" / `cf-turnstile` page and ignores a normal page;
  `extract_sitekey()` pulls the `data-sitekey`.
- **(b) Correct Peak call** — the middleware POSTs a body with
  `task_type == "turnstiletask"`, the extracted `sitekey`, and the request
  `url`. Proxy is omitted unless configured.
- **(c) Token injection** — a retry `Request` is produced for the same URL,
  method `POST`, with the token both on `request.meta["cf_turnstile_response"]`
  and as the `cf-turnstile-response` form field.
- Pass-through: a real 200 page is returned untouched and Peak is not called;
  an already-solved request is not re-processed (no loops).

## Run

```bash
cd scrapy-turnstile
python -m unittest discover -s tests -v
```

Python used: 3.12.0

## Observed output (PASS)

```
test_detects_challenge (test_middleware.DetectionTests.test_detects_challenge) ... ok
test_extracts_sitekey (test_middleware.DetectionTests.test_extracts_sitekey) ... ok
test_ignores_real_page (test_middleware.DetectionTests.test_ignores_real_page) ... ok
test_no_sitekey_on_real_page (test_middleware.DetectionTests.test_no_sitekey_on_real_page) ... ok
test_full_solve_flow (test_middleware.MiddlewareFlowTests.test_full_solve_flow)
Detect -> POST correct body to Peak -> retry Request with token. ... ok
test_real_page_passes_through (test_middleware.MiddlewareFlowTests.test_real_page_passes_through) ... ok
test_solve_returns_token_from_client (test_middleware.MiddlewareFlowTests.test_solve_returns_token_from_client)
PeakClient.solve unwraps data.token from the mocked response. ... ok
test_solved_request_not_reprocessed (test_middleware.MiddlewareFlowTests.test_solved_request_not_reprocessed)
A response for an already-solved request is passed through. ... ok
test_body_shape (test_middleware.PayloadTests.test_body_shape) ... ok
test_proxy_included_when_set (test_middleware.PayloadTests.test_proxy_included_when_set) ... ok

----------------------------------------------------------------------
Ran 10 tests in 0.001s

OK
```
