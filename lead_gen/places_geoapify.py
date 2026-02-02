"""
Geoapify Places API: geocode + places (paginated, max 500/request) + place details for website.

Per Geoapify docs:
- Geocoding: 1 credit/request
- Places: 1 credit per 20 places (limit ≤20 = 1 credit; limit 500 = 25 credits). Max limit = 500 per request; use offset for more.
- Place Details: 1 credit/request
So one run using 3000 credits: 1 + 25*6 + 2849 ≈ 3000 → up to ~2850 places per run with daily cap 3000.
"""

import math
import time
from typing import List, Optional, Tuple

from lead_gen import config
from lead_gen.http_utils import request_with_retry
from lead_gen.usage import can_use_geoapify_credits, record_geoapify_credits

PLACES_PAGE_SIZE = 500  # API max per request
PLACES_CREDITS_PER_PAGE = math.ceil(PLACES_PAGE_SIZE / 20)  # 25 for 500


def get_restaurants_geoapify_batch(
    query: str,
    api_key: str,
    offset: int,
    batch_size: int,
    filter_val: Optional[str] = None,
) -> Tuple[List[dict], Optional[int], Optional[str]]:
    """
    Fetch one batch of restaurants from Geoapify. Returns (results, next_offset, filter_val).
    If filter_val is None, runs geocode first and uses returned filter for Places. For subsequent
    batches pass the returned filter_val and next_offset.
    Stops when credit cap is reached; next_offset is None when no more data or cap hit.
    """
    results = []
    places_url = "https://api.geoapify.com/v2/places"
    limit = min(batch_size, PLACES_PAGE_SIZE)

    if filter_val is None:
        if not can_use_geoapify_credits(1):
            config.logger.warning(
                "Geoapify daily credit cap reached (%s/day). Skipping Geoapify for this batch.",
                getattr(config, "GEOAPIFY_DAILY_CREDIT_CAP", 0),
            )
            return [], None, None
        config.logger.info("Geoapify: geocoding query '%s'...", query)
        geo_url = "https://api.geoapify.com/v1/geocode/search"
        geo_resp = request_with_retry(geo_url, {"text": query, "apiKey": api_key})
        if not geo_resp:
            config.logger.warning("Geoapify geocode failed for %s", query)
            return [], None, None
        record_geoapify_credits(1)
        geo_data = geo_resp.json()
        features = geo_data.get("features") or []
        if not features:
            config.logger.warning("Geoapify: no results for query '%s'", query)
            return [], None, None
        props = features[0].get("properties", {})
        lon, lat = props.get("lon"), props.get("lat")
        bbox = props.get("bbox")
        if bbox:
            filter_val = f"rect:{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
        elif lon is not None and lat is not None:
            filter_val = f"circle:{lon},{lat},5000"
        else:
            return [], None, None
        offset = 0

    # When we have fewer credits than needed for a full batch, request a smaller limit so we still
    # get a partial payload and merge/dedupe can proceed (instead of skipping the request).
    credits_for_places = math.ceil(limit / 20)
    while limit >= 20 and not can_use_geoapify_credits(credits_for_places):
        limit -= 20
        credits_for_places = math.ceil(limit / 20)
    if limit < 20:
        config.logger.warning(
            "Geoapify daily credit cap reached. Not enough credits for a Places request (need at least 1)."
        )
        return results, None, filter_val

    time.sleep(config.GEOAPIFY_REQUEST_DELAY)
    places_params = {
        "categories": "catering.restaurant",
        "filter": filter_val,
        "limit": limit,
        "offset": offset,
        "apiKey": api_key,
    }
    places_resp = request_with_retry(places_url, places_params)
    if not places_resp:
        return results, None, filter_val
    record_geoapify_credits(credits_for_places)
    places_data = places_resp.json()
    features_places = places_data.get("features") or []
    if not features_places:
        return results, None, filter_val

    for f in features_places:
        if not can_use_geoapify_credits(1):
            config.logger.warning(
                "Geoapify daily credit cap reached. Stopping at %s places in this batch.",
                len(results),
            )
            return results, None, filter_val
        props = f.get("properties", {})
        name = props.get("name") or ""
        place_id = props.get("place_id")
        if not place_id:
            continue
        website = props.get("website") or None
        time.sleep(config.GEOAPIFY_REQUEST_DELAY)
        details_url = "https://api.geoapify.com/v2/place-details"
        detail_resp = request_with_retry(details_url, {"id": place_id, "apiKey": api_key})
        if detail_resp:
            record_geoapify_credits(1)
        if detail_resp:
            detail_data = detail_resp.json()
            for feat in (detail_data.get("features") or []):
                if feat.get("properties", {}).get("feature_type") != "details":
                    continue
                dprops = feat.get("properties", {})
                website = website or dprops.get("website")
                if not website and dprops.get("website_other"):
                    other = dprops["website_other"]
                    website = other[0] if isinstance(other, list) and other else (other if isinstance(other, str) else None)
                if not website:
                    bd = dprops.get("brand_details") or {}
                    website = bd.get("website")
                if not website:
                    od = dprops.get("operator_details") or {}
                    website = od.get("website")
                break
        results.append({"name": name, "website": website or None, "source": "geoapify"})

    next_offset = offset + len(features_places) if len(features_places) >= limit else None
    config.logger.info("Geoapify batch: %s places (offset %s, next_offset %s)", len(results), offset, next_offset)
    return results, next_offset, filter_val


def get_restaurants_geoapify(query: str, api_key: str) -> list:
    """
    Geocode query, then Places API (catering.restaurant) with pagination (500 per request),
    then Place Details for website. Stops at GEOAPIFY_DAILY_CREDIT_CAP or GEOAPIFY_MAX_RESULTS.
    Returns list of {"name", "website", "source": "geoapify"}.
    """
    results = []
    if not can_use_geoapify_credits(1):
        config.logger.warning(
            "Geoapify daily credit cap reached (%s/day). Skipping Geoapify for today.",
            getattr(config, "GEOAPIFY_DAILY_CREDIT_CAP", 0),
        )
        return results
    config.logger.info("Geoapify: geocoding query '%s'...", query)
    geo_url = "https://api.geoapify.com/v1/geocode/search"
    geo_resp = request_with_retry(geo_url, {"text": query, "apiKey": api_key})
    if not geo_resp:
        config.logger.warning("Geoapify geocode failed for %s", query)
        return results
    record_geoapify_credits(1)
    geo_data = geo_resp.json()
    features = geo_data.get("features") or []
    if not features:
        config.logger.warning("Geoapify: no results for query '%s'", query)
        return results
    props = features[0].get("properties", {})
    lon, lat = props.get("lon"), props.get("lat")
    bbox = props.get("bbox")
    if bbox:
        filter_val = f"rect:{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
    elif lon is not None and lat is not None:
        filter_val = f"circle:{lon},{lat},5000"
    else:
        return results

    places_url = "https://api.geoapify.com/v2/places"
    offset = 0
    max_results = getattr(config, "GEOAPIFY_MAX_RESULTS", 100)
    config.logger.info("Geoapify: fetching places (max %s)...", max_results)

    while len(results) < max_results:
        if not can_use_geoapify_credits(PLACES_CREDITS_PER_PAGE):
            config.logger.warning("Geoapify daily credit cap reached. Stopping Places pagination.")
            break
        time.sleep(config.GEOAPIFY_REQUEST_DELAY)
        places_params = {
            "categories": "catering.restaurant",
            "filter": filter_val,
            "limit": PLACES_PAGE_SIZE,
            "offset": offset,
            "apiKey": api_key,
        }
        places_resp = request_with_retry(places_url, places_params)
        if not places_resp:
            break
        record_geoapify_credits(PLACES_CREDITS_PER_PAGE)
        places_data = places_resp.json()
        features_places = places_data.get("features") or []
        if not features_places:
            break
        for f in features_places:
            if len(results) >= max_results:
                break
            if not can_use_geoapify_credits(1):
                config.logger.warning(
                    "Geoapify daily credit cap reached. Stopping at %s places (no more details).",
                    len(results),
                )
                break
            props = f.get("properties", {})
            name = props.get("name") or ""
            place_id = props.get("place_id")
            if not place_id:
                continue
            # Use website from Places list if present (some responses include it)
            website = props.get("website") or None
            time.sleep(config.GEOAPIFY_REQUEST_DELAY)
            details_url = "https://api.geoapify.com/v2/place-details"
            detail_resp = request_with_retry(details_url, {"id": place_id, "apiKey": api_key})
            if detail_resp:
                record_geoapify_credits(1)
            if detail_resp:
                detail_data = detail_resp.json()
                for feat in (detail_data.get("features") or []):
                    if feat.get("properties", {}).get("feature_type") != "details":
                        continue
                    dprops = feat.get("properties", {})
                    website = website or dprops.get("website")
                    if not website and dprops.get("website_other"):
                        other = dprops["website_other"]
                        website = other[0] if isinstance(other, list) and other else (other if isinstance(other, str) else None)
                    if not website:
                        bd = dprops.get("brand_details") or {}
                        website = bd.get("website")
                    if not website:
                        od = dprops.get("operator_details") or {}
                        website = od.get("website")
                    break
            results.append({"name": name, "website": website or None, "source": "geoapify"})
            if len(results) % 100 == 0 and len(results) > 0:
                config.logger.info("Geoapify: %s places fetched so far...", len(results))
        if len(features_places) < PLACES_PAGE_SIZE:
            break
        offset += PLACES_PAGE_SIZE
    config.logger.info("Geoapify: finished with %s places", len(results))
    return results
