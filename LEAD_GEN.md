# Restaurant Lead-Gen Bot

Collects **Restaurant Name → Website → Public Email** from restaurant websites.

- **Low cost** – Google Places + Geoapify Places in parallel (free-tier limits)
- **Respectful** – robots.txt, no headless browsers, no platform scraping
- **Reliable** – retries, timeouts, failure logging, domain deduping

## Pipeline

1. **Google Places** (Text Search + Place Details) and **Geoapify Places** (Geocode → Places → Place Details) run in parallel → name + website
2. **Merge and dedupe** by domain
3. Visit each **restaurant website** (+ `/contact`, `/about`); extract **public emails** (mailto + regex, same-domain only)
4. Save to CSV: `restaurant_name`, `website`, `emails_found`

## Free-tier limits

| API             | Free limit                    | Bot behavior                          |
|-----------------|-------------------------------|---------------------------------------|
| **Google Places** | Billing per use (caps vary)   | 0.5s between calls, cap 20 per run   |
| **Geoapify**      | 3,000 credits/day, 5 req/sec  | 0.25s between calls, cap 20 per run   |

Use at least one API; set only the keys you have.

## Setup

1. **API keys** (at least one):
   - **Google**: [Cloud Console](https://console.cloud.google.com/) → enable Places API → create key
   - **Geoapify**: [MyProjects](https://myprojects.geoapify.com/) → create project → API key

2. **Install**: `pip install -r requirements-leadgen.txt`

3. **Configure** (choose one method):

   **Option A: .env file (Recommended)**
   ```bash
   # Copy the example file
   cp .env.example .env

   # Edit .env and add your API keys and query
   # GEOAPIFY_API_KEY=your_key_here
   # LEAD_GEN_QUERY=restaurants in Austin Texas
   ```

   **Option B: Environment variables**
   - Windows PowerShell:
     ```powershell
     $env:GEOAPIFY_API_KEY = "your_key"
     $env:LEAD_GEN_QUERY = "restaurants in Austin Texas"
     ```
   - Windows CMD:
     ```bat
     set GEOAPIFY_API_KEY=your_key
     set LEAD_GEN_QUERY=restaurants in Austin Texas
     ```
   - macOS/Linux:
     ```bash
     export GEOAPIFY_API_KEY=your_key
     export LEAD_GEN_QUERY="restaurants in Austin Texas"
     ```

## Usage

```bash
python lead_gen_bot.py
```

- Uses `LEAD_GEN_QUERY` (default: "restaurants in Denver Colorado") and whichever of `GOOGLE_PLACES_API_KEY`, `GEOAPIFY_API_KEY` is set
- Output: `restaurant_leads.csv` | Failures: `lead_gen_failures.log`

**Query Format:**
- **For Geoapify:** Use location-only queries (e.g., `"Maryland"`, `"Baltimore, Maryland"`, `"Austin, Texas"`). The script automatically searches for restaurants in that location.
- **For Google Places:** Can use business type + location (e.g., `"restaurants in Austin Texas"`, `"Family Restaurant Maryland"`).

If using Geoapify only, avoid including "restaurant" or "family restaurant" in the query - just specify the location.

**CSV:** `restaurant_name`, `website`, `emails_found` (multiple emails joined with `|`)

**No duplicates:** If `restaurant_leads.csv` already exists, the bot loads it and skips any domain that’s already in the file. New results are appended. You can run multiple queries (e.g. different cities) and accumulate into one CSV without duplicate sites.

## Error handling & skips

- **Redirects:** We follow redirects and use the **resulting (final) URL** for domain checks, robots.txt, email scraping, and the stored `website` in CSV. So if a place redirects to another domain, we use that final domain everywhere—including when you later interact with the site.
- **Retry logic:** Website fetches retry on transient network errors (configurable `MAX_RETRIES`, `RETRY_BACKOFF` in `lead_gen/config.py`). API calls use the same retry pattern.
- **Invalid SSL:** Sites with invalid or expired certificates are logged to `lead_gen_failures.log` and skipped (no retry; we do not bypass SSL).
- **Dead sites:** If the homepage fails after retries (timeout, connection refused, etc.), the restaurant is skipped and not written to CSV. Logged as "site unreachable or invalid SSL".
- **Catering businesses:** Businesses with "catering", "caterer", "food truck", "meal prep", or similar keywords in their name are automatically filtered out. Only sit-down restaurants are included. Keywords are configurable in `SKIP_NAME_KEYWORDS` in `lead_gen/config.py`.
- **Chain/franchise domains:** A blocklist `SKIP_DOMAINS` in `lead_gen/config.py` skips known chains (McDonald's, Chipotle, Subway, etc.). Subdomains are skipped too. **Ollama chain filter:** If [Ollama](https://ollama.com) is running and `USE_OLLAMA_CHAIN_FILTER` is True in `lead_gen/config.py`, the bot also asks Ollama (e.g. `llama3.2`) "is this a chain/franchise?" using the restaurant name and domain; if yes, the restaurant is skipped. Enable/disable via env `LEAD_GEN_USE_OLLAMA_CHAIN=1` (on) or `LEAD_GEN_USE_OLLAMA_CHAIN=0` (off). If unset, the default in `lead_gen/config.py` is used. To use only the blocklist, set `LEAD_GEN_USE_OLLAMA_CHAIN=0` or `USE_OLLAMA_CHAIN_FILTER = False`. Install a model: `ollama pull llama3.2`.

## In code

```python
from lead_gen_bot import run_pipeline

run_pipeline(
    "restaurants in Seattle Washington",
    output_csv="seattle_leads.csv",
    google_key="...",
    geoapify_key="...",
)
```

## Cost

- **Google**: Per request; bot caps results and rate to limit cost  
- **Geoapify**: 3,000 credits/day free; ~1 credit per 20 places + 1 per Place Details

## Ollama: chain filter

The lead-gen bot can use **Ollama** to filter out chain/franchise restaurants. If Ollama is running (e.g. `ollama serve`) and a small model is installed (e.g. `ollama pull llama3.2`), enable the filter (default in code is True, or set env `LEAD_GEN_USE_OLLAMA_CHAIN=1`). The bot will ask the model “is this a chain or franchise?” for each restaurant (name + domain); if the model says yes, the restaurant is skipped. The static `SKIP_DOMAINS` blocklist is still applied first (no LLM call for known chains). To disable: set env `LEAD_GEN_USE_OLLAMA_CHAIN=0` or `USE_OLLAMA_CHAIN_FILTER = False` in `lead_gen/config.py`.
