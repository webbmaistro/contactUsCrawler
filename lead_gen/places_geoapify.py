"""Geoapify Places API: geocode + places + place details for website."""

import time

from lead_gen import config
from lead_gen.http_utils import request_with_retry


def get_restaurants_geoapify(query: str, api_key: str) -> list:
    """
    Geocode query (e.g. "Denver Colorado") then Places API (catering.restaurant),
    then Place Details for website. Returns list of {"name", "website", "source": "geoapify"}.
    """
    results = []
    geo_url = "https://api.geoapify.com/v1/geocode/search"
    geo_resp = request_with_retry(geo_url, {"text": query, "apiKey": api_key})
    if not geo_resp:
        config.logger.warning("Geoapify geocode failed for %s", query)
        return results
    geo_data = geo_resp.json()
    features = geo_data.get("features") or []
    if not features:
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

    time.sleep(config.GEOAPIFY_REQUEST_DELAY)
    places_url = "https://api.geoapify.com/v2/places"
    places_params = {
        "categories": "catering.restaurant",
        "filter": filter_val,
        "limit": min(20, config.GEOAPIFY_MAX_RESULTS),
        "apiKey": api_key,
    }
    places_resp = request_with_retry(places_url, places_params)
    if not places_resp:
        return results
    places_data = places_resp.json()
    features_places = places_data.get("features") or []
    for f in features_places[:config.GEOAPIFY_MAX_RESULTS]:
        props = f.get("properties", {})
        name = props.get("name") or ""
        place_id = props.get("place_id")
        if not place_id:
            continue
        time.sleep(config.GEOAPIFY_REQUEST_DELAY)
        details_url = "https://api.geoapify.com/v2/place-details"
        detail_resp = request_with_retry(details_url, {"id": place_id, "apiKey": api_key})
        website = None
        if detail_resp:
            detail_data = detail_resp.json()
            for feat in (detail_data.get("features") or []):
                if feat.get("properties", {}).get("feature_type") == "details":
                    website = feat.get("properties", {}).get("website")
                    break
        results.append({"name": name, "website": website or None, "source": "geoapify"})
    return results
