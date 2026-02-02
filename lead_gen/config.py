"""Configuration for the lead-gen bot (override via environment or edit here)."""

import logging
import os
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# HTTP & scraping
# ---------------------------------------------------------------------------
USER_AGENT = "RestaurantResearchBot/1.0"
SCRAPE_DELAY_SECONDS = 2
REQUEST_TIMEOUT = 15
MAX_RETRIES = 2
RETRY_BACKOFF = 2
OUTPUT_CSV = "restaurant_leads.csv"
# Resolve failure log to project root so it's always the same file regardless of cwd
_FAILURE_LOG_NAME = "lead_gen_failures.log"
FAILURE_LOG = str(Path(__file__).resolve().parent.parent / _FAILURE_LOG_NAME)
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Free-tier limits
GOOGLE_MAX_RESULTS = 20
GOOGLE_REQUEST_DELAY = 0.5
# Optional: Self-hosted SearXNG fallback (free, no API key). Run SearXNG (e.g. Docker) and set base URL.
# Example: SEARXNG_URL=http://localhost:8080  (enable JSON in settings: search.formats = [html, json])
SEARXNG_URL = os.environ.get("SEARXNG_URL", "").strip().rstrip("/") or None
SEARXNG_LOOKUP_DELAY = 0.5  # Seconds between SearXNG lookups
# Domains to skip when picking a search result (aggregators, not the restaurant's own site)
SEARCH_SKIP_DOMAINS = frozenset({
    "yelp.com", "tripadvisor.com", "facebook.com", "instagram.com", "twitter.com",
    "google.com", "maps.google.com", "opentable.com", "zagat.com", "grubhub.com",
    "ubereats.com", "doordash.com", "postmates.com", "foursquare.com", "zomato.com",
    "groupon.com", "yellowpages.com", "superpages.com", "manta.com",
    "hotels.com", "expedia.com", "booking.com", "wikipedia.org", "wikidata.org",
})
# Max restaurants to fetch from Geoapify per run. Per Geoapify docs: Geocoding 1 credit; Places = 1 credit per 20 (max 500/request); Place Details 1 credit each.
# With GEOAPIFY_DAILY_CREDIT_CAP=3000, one run can use the full cap → ~2850 places (1 + 6×25 + 2849). Set to 3000 to "use all 3000 credits per run".
GEOAPIFY_MAX_RESULTS = 3000
# Batch size: fetch this many places from Geoapify per batch before processing (website checks, CSV). Google yields one page (~20) per batch.
API_BATCH_SIZE = 100
# Seconds between each Geoapify API call (geocode, places, place-details).
# Higher = spread out usage, stay under rate limits and daily cap.
GEOAPIFY_REQUEST_DELAY = 2.0
# Geoapify daily credit cap (free tier = 3000/day). We stop making API calls once we hit this. Set to 0 to disable.
GEOAPIFY_DAILY_CREDIT_CAP = 3000
# File to persist daily usage (next to project root, or use absolute path)
USAGE_FILE = "lead_gen_usage.json"

# Pages to check for contact/about info
CONTACT_PATHS = ["/contact", "/contact-us", "/contactus", "/about", "/about-us", "/get-in-touch"]

# Email local-part quality (higher = prefer when deduping)
EMAIL_QUALITY = {"info": 3, "contact": 2, "support": 2, "hello": 2, "admin": 1}

# Chain/franchise blocklist
SKIP_DOMAINS: set = {
    "mcdonalds.com", "chipotle.com", "subway.com", "starbucks.com", "dominos.com",
    "pizzahut.com", "tacobell.com", "wendys.com", "burgerking.com", "dunkindonuts.com",
    "panera.com", "olivegarden.com", "applebees.com", "outback.com", "redlobster.com",
    "chilis.com", "buffalowildwings.com", "ihop.com", "dennys.com", "jackinthebox.com",
    "sonicdrivein.com", "arbys.com", "popeyes.com", "kfc.com", "pandaexpress.com",
    "fiveguys.com", "in-n-out.com", "whataburger.com", "culvers.com", "wingstop.com",
    "jimmyjohns.com", "littlecaesars.com",
}

# Ollama (self-hosted): chain filter and optional website picker
USE_OLLAMA_CHAIN_FILTER = True
USE_OLLAMA_WEBSITE_PICKER = True  # When filling websites via search, ask Ollama to pick best URL from results
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"
OLLAMA_CHAIN_TIMEOUT = 15
OLLAMA_WEBSITE_PICKER_TIMEOUT = 15

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("LeadGenBot")
failure_logger = logging.getLogger("LeadGenBot.failures")
failure_logger.setLevel(logging.WARNING)
failure_logger.propagate = False  # Only write to our file, don't rely on root
failure_handler = logging.FileHandler(FAILURE_LOG, encoding="utf-8")
failure_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
failure_handler.setLevel(logging.WARNING)
failure_logger.addHandler(failure_handler)
