"""HTTP helpers: retry logic and API provider naming."""

import time
from typing import Optional

import requests

from lead_gen import config


def _api_provider_from_url(url: str) -> str:
    """Return a friendly provider name for API key error messages."""
    if "googleapis.com" in url or "maps.googleapis.com" in url:
        return "Google"
    if "geoapify.com" in url:
        return "Geoapify"
    return "API"


def request_with_retry(url: str, params: dict) -> Optional[requests.Response]:
    """Retry logic for network errors. 401/403 are treated as API key issues (no retry)."""
    for attempt in range(config.MAX_RETRIES + 1):
        try:
            r = requests.get(
                url,
                params=params,
                timeout=config.REQUEST_TIMEOUT,
                headers={"User-Agent": config.USER_AGENT},
            )
            if r.status_code in (401, 403):
                provider = _api_provider_from_url(url)
                config.logger.warning(
                    "Check your %s API key. (HTTP %s) If the key is invalid or expired, "
                    "update it and try again.",
                    provider,
                    r.status_code,
                )
                config.failure_logger.warning(
                    "API key error: %s (HTTP %s) url=%s",
                    provider,
                    r.status_code,
                    url,
                )
                return None
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if attempt < config.MAX_RETRIES:
                time.sleep(config.RETRY_BACKOFF * (attempt + 1))
                continue
            config.logger.warning("Request failed after retries: %s %s", url, e)
            config.failure_logger.warning("Request failed: %s params=%s error=%s", url, params, e)
    return None
