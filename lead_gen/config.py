"""Configuration for the lead-gen bot (override via environment or edit here)."""

import logging
import re

# ---------------------------------------------------------------------------
# HTTP & scraping
# ---------------------------------------------------------------------------
USER_AGENT = "RestaurantResearchBot/1.0"
SCRAPE_DELAY_SECONDS = 2
REQUEST_TIMEOUT = 15
MAX_RETRIES = 2
RETRY_BACKOFF = 2
OUTPUT_CSV = "restaurant_leads.csv"
FAILURE_LOG = "lead_gen_failures.log"
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Free-tier limits
GOOGLE_MAX_RESULTS = 20
GOOGLE_REQUEST_DELAY = 0.5
GEOAPIFY_MAX_RESULTS = 20
GEOAPIFY_REQUEST_DELAY = 0.25

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

# Ollama chain filter
USE_OLLAMA_CHAIN_FILTER = True
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"
OLLAMA_CHAIN_TIMEOUT = 15

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("LeadGenBot")
failure_handler = logging.FileHandler(FAILURE_LOG, encoding="utf-8")
failure_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
failure_logger = logging.getLogger("LeadGenBot.failures")
failure_logger.addHandler(failure_handler)
failure_logger.setLevel(logging.WARNING)
