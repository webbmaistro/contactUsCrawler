"""Parallel fetch and merge: Google + Geoapify, dedupe by domain."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from urllib.parse import urlparse

from lead_gen import config
from lead_gen.places_google import get_restaurants_google
from lead_gen.places_geoapify import get_restaurants_geoapify


def _normalize_name(name: str) -> str:
    """Normalize for dedupe: lower, collapse spaces."""
    return " ".join((name or "").lower().split())


def extract_domain(website: Optional[str]) -> Optional[str]:
    """Extract domain from website URL."""
    if not website:
        return None
    p = urlparse(website)
    d = (p.netloc or "").lower().replace("www.", "")
    return d or None


def merge_and_dedupe(combined: list) -> list:
    """
    Dedupe by domain (one row per website); prefer entry with website when same domain.
    """
    by_domain = {}
    no_website = []
    for r in combined:
        name = (r.get("name") or "").strip()
        website = r.get("website")
        domain = extract_domain(website)
        nname = _normalize_name(name)
        if not nname:
            continue
        if domain:
            if domain not in by_domain or (website and not by_domain[domain].get("website")):
                by_domain[domain] = r
        else:
            no_website.append(r)
    names_with_website = {_normalize_name(by_domain[d].get("name")) for d in by_domain}
    deduped_no_web = [r for r in no_website if _normalize_name(r.get("name")) not in names_with_website]
    return list(by_domain.values()) + deduped_no_web


def get_all_restaurants_parallel(
    query: str,
    google_key: Optional[str] = None,
    geoapify_key: Optional[str] = None,
) -> list:
    """
    Run Google and Geoapify in parallel (each only if key provided).
    Merge and dedupe results.
    """
    combined = []
    tasks = []

    if google_key and google_key.strip():
        tasks.append(("google", get_restaurants_google, (query, google_key.strip())))
    if geoapify_key and geoapify_key.strip():
        tasks.append(("geoapify", get_restaurants_geoapify, (query, geoapify_key.strip())))

    if not tasks:
        return combined

    def run_one(label: str, fn, args):
        try:
            out = fn(*args)
            config.logger.info("%s returned %s results", label, len(out))
            return out
        except Exception as e:
            config.logger.warning("%s failed: %s", label, e)
            config.failure_logger.warning("%s failed: %s", label, e)
            return []

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(run_one, label, fn, args): label for label, fn, args in tasks}
        for future in as_completed(futures):
            combined.extend(future.result())

    merged = merge_and_dedupe(combined)
    config.logger.info("Merged and deduped to %s restaurants", len(merged))
    return merged
