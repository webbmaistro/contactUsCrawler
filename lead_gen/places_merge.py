"""Parallel fetch and merge: Google + Geoapify, dedupe by domain."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from urllib.parse import urlparse

from lead_gen import config
from lead_gen.places_google import get_restaurants_google_batch
from lead_gen.places_geoapify import get_restaurants_geoapify_batch
from lead_gen.website_lookup import fill_websites_fallback


def _normalize_name(name: str) -> str:
    """Normalize for dedupe: lower, collapse spaces."""
    return " ".join((name or "").lower().split())


def _get_name_str(r: dict) -> str:
    """Get name from record as a string; APIs sometimes return int or other types."""
    raw = r.get("name")
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    return str(raw).strip()


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
        name = _get_name_str(r)
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
    names_with_website = {_normalize_name(_get_name_str(by_domain[d])) for d in by_domain}
    deduped_no_web = [r for r in no_website if _normalize_name(_get_name_str(r)) not in names_with_website]
    return list(by_domain.values()) + deduped_no_web


def get_all_restaurants_parallel(
    query: str,
    google_key: Optional[str] = None,
    geoapify_key: Optional[str] = None,
):
    """
    Fetch restaurants in batches from Google and Geoapify in parallel. Each round fetches one
    batch from each API, merges and dedupes, then yields (batch, is_final) so the pipeline can
    check websites and append to CSV before the next API batch. Repeats until both sources
    report no more data or hit limits.
    """
    google_key = (google_key or "").strip() or None
    geoapify_key = (geoapify_key or "").strip() or None
    if not google_key and not geoapify_key:
        return

    batch_size = getattr(config, "API_BATCH_SIZE", 100)
    geoapify_offset: Optional[int] = 0
    geoapify_filter_val: Optional[str] = None
    google_page_token: Optional[str] = None
    geoapify_done = False
    google_done = False

    while True:
        def run_geoapify():
            try:
                return get_restaurants_geoapify_batch(
                    query, geoapify_key, geoapify_offset, batch_size, geoapify_filter_val
                )
            except Exception as e:
                config.logger.warning("Geoapify batch failed: %s", e)
                config.failure_logger.warning("Geoapify batch failed: %s", e)
                return [], None, geoapify_filter_val

        def run_google():
            try:
                return get_restaurants_google_batch(query, google_key, google_page_token)
            except Exception as e:
                config.logger.warning("Google batch failed: %s", e)
                config.failure_logger.warning("Google batch failed: %s", e)
                return [], None

        tasks = []
        if geoapify_key and not geoapify_done:
            tasks.append(("geoapify", run_geoapify))
        if google_key and not google_done:
            tasks.append(("google", run_google))

        if not tasks:
            break

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {executor.submit(fn): label for label, fn in tasks}
            results_by_label = {}
            for future in as_completed(futures):
                label = futures[future]
                results_by_label[label] = future.result()

        batch_geo: list = []
        next_offset_geo: Optional[int] = None
        filter_val_geo: Optional[str] = None
        if "geoapify" in results_by_label:
            batch_geo, next_offset_geo, filter_val_geo = results_by_label["geoapify"]
            if next_offset_geo is None:
                geoapify_done = True
        batch_google: list = []
        next_token_google: Optional[str] = None
        if "google" in results_by_label:
            batch_google, next_token_google = results_by_label["google"]
            if next_token_google is None:
                google_done = True

        geoapify_offset = next_offset_geo if next_offset_geo is not None else geoapify_offset
        geoapify_filter_val = filter_val_geo if filter_val_geo is not None else geoapify_filter_val
        google_page_token = next_token_google

        merged = merge_and_dedupe(batch_geo + batch_google)
        fill_websites_fallback(merged, query)

        no_more_geo = not geoapify_key or geoapify_done
        no_more_google = not google_key or google_done
        is_final = no_more_geo and no_more_google

        if merged:
            config.logger.info(
                "API batch: %s restaurants (Geoapify %s, Google %s) — starting pipeline",
                len(merged), len(batch_geo), len(batch_google),
            )
            yield (merged, is_final)

        if is_final:
            break
