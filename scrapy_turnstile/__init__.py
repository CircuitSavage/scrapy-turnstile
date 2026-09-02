"""scrapy-turnstile: solve Cloudflare Turnstile in Scrapy via the Peak API."""

from .detect import extract_sitekey, is_turnstile_challenge
from .middleware import TurnstileMiddleware
from .peak import (
    DEFAULT_API_URL,
    TASK_CLOUDFLARE_5S,
    TASK_TURNSTILE,
    PeakClient,
    PeakError,
    build_solve_payload,
)

__all__ = [
    "TurnstileMiddleware",
    "PeakClient",
    "PeakError",
    "build_solve_payload",
    "extract_sitekey",
    "is_turnstile_challenge",
    "DEFAULT_API_URL",
    "TASK_TURNSTILE",
    "TASK_CLOUDFLARE_5S",
]

__version__ = "0.1.0"
