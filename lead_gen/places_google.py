"""Google Places API: text search + place details for website."""

import time

from lead_gen import config
from lead_gen.http_utils import request_with_retry


def get_restaurants_google(query: str, api_key: str) -> list:
    """
    Call Google Places Text Search API, then Place Details for website.
    Returns list of {"name": str, "website": str | None, "source": "google"}.
    """
    base_text = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    base_details = "https://maps.googleapis.com/maps/api/place/details/json"
    results = []
    params = {"query": query, "key": api_key}
    page_count = 0
    max_pages = 5

    while len(results) < config.GOOGLE_MAX_RESULTS:
        if page_count == 0:
            resp = request_with_retry(base_text, params)
        else:
            resp = request_with_retry(base_text, {"pagetoken": next_token, "key": api_key})

        if resp is None:
            break
        data = resp.json()
        status = data.get("status")
        if status != "OK" and status != "ZERO_RESULTS":
            if status == "OVER_QUERY_LIMIT":
                config.logger.warning("Google Places over query limit")
            elif status == "REQUEST_DENIED":
                config.logger.warning(
                    "Check your Google API key. Request was denied (invalid key, expired, or API not enabled)."
                )
            break

        for pred in data.get("results", []):
            if len(results) >= config.GOOGLE_MAX_RESULTS:
                break
            name = pred.get("name") or ""
            place_id = pred.get("place_id")
            if not place_id:
                continue
            time.sleep(config.GOOGLE_REQUEST_DELAY)
            detail_resp = request_with_retry(
                base_details,
                {"place_id": place_id, "fields": "website", "key": api_key},
            )
            website = None
            if detail_resp:
                detail_data = detail_resp.json()
                if detail_data.get("status") == "OK":
                    result = detail_data.get("result", {})
                    website = result.get("website") or result.get("url")
            results.append({"name": name, "website": website or None, "source": "google"})

        next_token = data.get("next_page_token")
        page_count += 1
        if not next_token or page_count >= max_pages:
            break
        time.sleep(1)
    return results
