"""
Fallback: look up a restaurant website when Places/Geoapify return none.

- Self-hosted (free): SearXNG — set SEARXNG_URL (e.g. http://localhost:8080).
  Run SearXNG (Docker or native), enable JSON in settings: search.formats = [html, json].
- Optional: use Ollama to pick the best URL from search results (USE_OLLAMA_WEBSITE_PICKER).
"""

import time
from typing import List, Optional
from urllib.parse import urlparse

import requests

from lead_gen import config


def _domain_of(url: str) -> str:
    """Extract lowercase domain from URL (no www)."""
    try:
        parsed = urlparse(url)
        netloc = (parsed.netloc or "").lower().replace("www.", "")
        return netloc or ""
    except Exception:
        return ""


def _is_aggregator(url: str) -> bool:
    """True if URL is an aggregator we want to skip (Yelp, TripAdvisor, etc.)."""
    domain = _domain_of(url)
    if not domain:
        return True
    for skip in config.SEARCH_SKIP_DOMAINS:
        if domain == skip or domain.endswith("." + skip):
            return True
    if "google." in domain or "facebook." in domain or "tripadvisor." in domain:
        return True
    return False


def lookup_website_searxng(
    base_url: str,
    restaurant_name: str,
    location_query: str,
) -> Optional[str]:
    """
    Search via self-hosted SearXNG and return the first result URL that looks like
    the restaurant's own site. base_url e.g. http://localhost:8080 (no trailing slash).
    Requires SearXNG to have format=json enabled in settings.
    """
    query = f"{restaurant_name} {location_query} restaurant".strip()
    search_url = f"{base_url.rstrip('/')}/search"
    params = {"q": query, "format": "json"}
    try:
        resp = requests.get(
            search_url,
            params=params,
            timeout=config.REQUEST_TIMEOUT,
            headers={"User-Agent": config.USER_AGENT},
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception:
        return None
    # SearXNG JSON: results array, each item has "url"
    for item in (data.get("results") or []):
        link = (item.get("url") or "").strip()
        if not link:
            continue
        if _is_aggregator(link):
            continue
        if not link.startswith(("http://", "https://")):
            link = "https://" + link
        return link
    return None


def _get_candidates_searxng(
    base_url: str,
    restaurant_name: str,
    location_query: str,
    max_candidates: int = 5,
) -> List[str]:
    """Return up to max_candidates non-aggregator URLs from SearXNG (for Ollama picker)."""
    query = f"{restaurant_name} {location_query} restaurant".strip()
    search_url = f"{base_url.rstrip('/')}/search"
    params = {"q": query, "format": "json"}
    try:
        resp = requests.get(
            search_url,
            params=params,
            timeout=config.REQUEST_TIMEOUT,
            headers={"User-Agent": config.USER_AGENT},
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:
        return []
    candidates = []
    for item in (data.get("results") or []):
        link = (item.get("url") or "").strip()
        if not link or _is_aggregator(link):
            continue
        if not link.startswith(("http://", "https://")):
            link = "https://" + link
        candidates.append(link)
        if len(candidates) >= max_candidates:
            break
    return candidates


def _ollama_pick_best_url(restaurant_name: str, urls: List[str]) -> Optional[str]:
    """Ask self-hosted Ollama which URL is most likely the official restaurant site. Returns one URL or None."""
    if not urls:
        return None
    if len(urls) == 1:
        return urls[0]
    try:
        from lead_gen.chain_filter import ollama_available
        if not ollama_available():
            return urls[0]
    except Exception:
        return urls[0]
    url_list = "\n".join(f"- {u}" for u in urls[:5])
    prompt = (
        f"Which of these URLs is most likely the official website for the restaurant \"{restaurant_name}\"? "
        f"Reply with only that URL, or the word 'none' if none look like the restaurant's own site.\n\n{url_list}"
    )
    try:
        r = requests.post(
            config.OLLAMA_API_URL,
            json={
                "model": config.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0, "num_predict": 200},
            },
            timeout=getattr(config, "OLLAMA_WEBSITE_PICKER_TIMEOUT", 15),
        )
        if r.status_code != 200:
            return urls[0]
        reply = (r.json().get("response") or "").strip().lower()
        if "none" in reply or not reply:
            return urls[0]
        # Try to find a URL in the reply
        for u in urls:
            if u in reply or u.replace("https://", "").replace("http://", "") in reply:
                return u
        # Fallback: first URL
        return urls[0]
    except Exception:
        return urls[0]


def fill_websites_fallback(restaurants: list, location_query: str) -> None:
    """
    For each restaurant with no website, try to find one via SearXNG (self-hosted, free).
    Optional: use Ollama to pick the best URL from search results (USE_OLLAMA_WEBSITE_PICKER).
    Mutates restaurants in place. No-op if SEARXNG_URL is not set.
    """
    base_url = getattr(config, "SEARXNG_URL", None) and str(config.SEARXNG_URL).strip()
    if not base_url:
        return
    use_ollama = getattr(config, "USE_OLLAMA_WEBSITE_PICKER", False)
    delay = getattr(config, "SEARXNG_LOOKUP_DELAY", 0.5)
    filled = 0
    for r in restaurants:
        if r.get("website"):
            continue
        name = (r.get("name") or "").strip()
        if not name:
            continue
        time.sleep(delay)
        if use_ollama:
            candidates = _get_candidates_searxng(base_url, name, location_query, max_candidates=5)
            url = _ollama_pick_best_url(name, candidates) if candidates else None
        else:
            url = lookup_website_searxng(base_url, name, location_query)
        if url:
            r["website"] = url
            filled += 1
            config.logger.info("Search found website for %s: %s", name, url)
    if filled:
        config.logger.info("Website lookup filled %s missing websites", filled)
