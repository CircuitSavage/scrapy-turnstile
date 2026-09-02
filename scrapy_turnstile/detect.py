"""Cloudflare Turnstile detection and sitekey extraction.

Pure functions with no Scrapy dependency so they are cheap to test.
"""

from __future__ import annotations

import re
from typing import Optional

# Markers that a response is a Cloudflare Turnstile / managed challenge page
# rather than the real content.
_CHALLENGE_MARKERS = (
    "cf-turnstile",
    "challenges.cloudflare.com/turnstile",
    "turnstile.js",
    "just a moment",
    "cf_chl_opt",
    "__cf_chl",
    "window._cf_chl",
)

# data-sitekey="0x4AAAAA..."  (the widget div attribute)
_SITEKEY_ATTR = re.compile(
    r"""data-sitekey\s*=\s*["']([^"']+)["']""", re.IGNORECASE
)
# render: '0x4AAAAA...'  or  sitekey: "0x4AAAAA..."  (JS render config)
_SITEKEY_JS = re.compile(
    r"""(?:sitekey|render)\s*[:=]\s*["']([^"']+)["']""", re.IGNORECASE
)


def is_turnstile_challenge(body_text: str, status: Optional[int] = None) -> bool:
    """Return True if the response looks like a Turnstile challenge page.

    A 403 alone is not enough (many APIs 403); we require a Cloudflare
    challenge marker in the body. A 403/503 raises confidence but the
    marker is what decides it.
    """
    if not body_text:
        return False
    lowered = body_text.lower()
    return any(marker in lowered for marker in _CHALLENGE_MARKERS)


def extract_sitekey(body_text: str) -> Optional[str]:
    """Pull the Turnstile sitekey out of a challenge page, or None."""
    if not body_text:
        return None
    match = _SITEKEY_ATTR.search(body_text)
    if match:
        return match.group(1).strip()
    match = _SITEKEY_JS.search(body_text)
    if match:
        candidate = match.group(1).strip()
        # Turnstile sitekeys start with 0x; guard against matching unrelated
        # JS keys named "sitekey".
        if candidate.startswith("0x") or candidate.startswith("1x"):
            return candidate
    return None
