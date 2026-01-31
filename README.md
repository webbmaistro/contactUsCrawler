# Restaurant Contact Form Crawler

Reach out to restaurants at scale: **build a list** of restaurants with websites and public emails, then **optionally** automate contact form submissions with your message. Two tools, one workflow.

- **Lead-Gen Bot** – Uses Google Places and Geoapify (in parallel, free-tier friendly) to get restaurant name + website, then visits each site to extract public business emails. No scraping of Google/social; respects robots.txt.
- **Contact Form Crawler** – Takes a CSV of restaurant websites, finds contact pages, detects form fields (CSS + optional Ollama LLM), fills and submits with your message. Saves progress so you can stop and resume.

**Typical flow:** Run the lead-gen bot → get `restaurant_leads.csv` → rename columns to match crawler input → run the crawler to submit your message to each site.

---

## Prerequisites

- **Python 3.8+** (3.10+ recommended)
- **Lead-gen only:** `requests`, `beautifulsoup4` (no browser)
- **Crawler:** Playwright (Chromium). Optional: [Ollama](https://ollama.com) for better form detection (~85–95% success vs ~60–70% with selectors only); see [LLM_SETUP.md](LLM_SETUP.md).

**Run one bot without the other:** The two bots are independent (no cross-imports). To install only what you need:

- **Lead-gen only:** `pip install -r requirements-leadgen.txt` → `python lead_gen_bot.py` (no Playwright, no pandas).
- **Crawler only:** `pip install -r requirements-crawler.txt` → `playwright install chromium` → `python crawler.py`.

Use `pip install -r requirements.txt` if you want both.

---

## Project layout

Logic is split into packages so you can upgrade or extend one part without touching the rest.

- **`crawler/`** – Contact form crawler  
  - `logger.py` – Colored logging  
  - `llm.py` – Ollama form-field detection  
  - `contact_finder.py` – Finding contact pages  
  - `form_detector.py` – Detecting and filling form fields  
  - `runner.py` – Main flow (load CSV, process, save)  
  - Run via `python crawler.py` or `python -m crawler`

- **`lead_gen/`** – Lead-gen bot  
  - `config.py` – Constants and logging  
  - `chain_filter.py` – Ollama chain/franchise filter  
  - `places_google.py`, `places_geoapify.py`, `places_merge.py` – APIs and dedupe  
  - `http_utils.py` – Retry logic  
  - `robots.py` – robots.txt check  
  - `email_scraper.py` – Fetch pages, extract emails  
  - `csv_io.py` – Load/save CSV  
  - `pipeline.py` – Main flow  
  - Run via `python lead_gen_bot.py`; or `from lead_gen_bot import run_pipeline`

- **`config.py`** (root) – Crawler-only settings (sender, CSV paths, delays, LLM, etc.)

---

## Quick Start

### 1. Clone and install

```bash
git clone <your-repo-url>
cd contactUsCrawler
pip install -r requirements.txt
```

For the **crawler** you also need Playwright:

```bash
playwright install chromium
```

### 2. Lead-Gen Bot (get restaurants + emails)

- Get at least one API key: [Google Cloud Console](https://console.cloud.google.com/) (Places API) or [Geoapify](https://myprojects.geoapify.com/) (same key for Geocoding + Places + Place Details).
- Set env vars (Windows: `set`; macOS/Linux: `export`):

  ```bash
  set GOOGLE_PLACES_API_KEY=your_key
  set GEOAPIFY_API_KEY=your_key
  set LEAD_GEN_QUERY=restaurants in Austin Texas
  ```

- Run:

  ```bash
  python lead_gen_bot.py
  ```

- Output: `restaurant_leads.csv` with `restaurant_name`, `website`, `emails_found`. Failures logged to `lead_gen_failures.log`.

Full details and rate limits: [LEAD_GEN.md](LEAD_GEN.md).

### 3. Contact Form Crawler (submit your message)

- Edit `config.py`: set `SENDER_NAME`, `SENDER_EMAIL`, `MESSAGE_TEMPLATE`, and `INPUT_CSV` / `OUTPUT_CSV`.
- Create your input CSV with columns `website_url` and `restaurant_name`. **If you ran the lead-gen bot**, you can use its output directly: set `INPUT_CSV = "restaurant_leads.csv"` in `config.py`. The crawler accepts `website` as an alias for `website_url`, so no conversion step is needed.

- Run:

  ```bash
  python crawler.py
  ```

- Results in `restaurants_results.csv`; progress is saved every few sites. Re-run to resume.

---

## Lead-Gen Bot (details)

**What it does:** Calls Google Places and Geoapify Places in parallel (each only if you set its API key), merges and dedupes by domain, then for each restaurant with a website: checks robots.txt, fetches the site and common paths like `/contact` and `/about`, extracts public emails (mailto + regex, same-domain only), and appends a row to CSV.

**Setup:** At least one of `GOOGLE_PLACES_API_KEY`, `GEOAPIFY_API_KEY`; optionally `LEAD_GEN_QUERY` (default: `"restaurants in Denver Colorado"`).

**Output:** `restaurant_leads.csv` — columns: `restaurant_name`, `website`, `emails_found` (multiple emails separated by `|`). Only restaurants with a website are written; sites that disallow crawling are skipped. If the file already exists, the bot loads it and **skips any domain already present** (new rows appended only), so you can run multiple queries and accumulate into one CSV without duplicates.

**Error handling:** Website fetches retry on network errors; invalid SSL and dead sites are skipped (not written). **Redirects:** We use the final URL after redirects for domain checks, robots, scraping, and CSV (so you interact on the resulting domain). **Chain/franchise filter:** Known chains are skipped via a blocklist `SKIP_DOMAINS` in `lead_gen/config.py`. Optional **Ollama** filter: if Ollama is running (e.g. `ollama pull llama3.2`) and `USE_OLLAMA_CHAIN_FILTER = True` in `lead_gen/config.py`, the bot also asks the model “is this a chain?” and skips those. See [LEAD_GEN.md](LEAD_GEN.md) for details.

---

## Contact Form Crawler (details)

**What it does:** Loads rows from `INPUT_CSV`; for each, finds a contact page (common URLs + link text), detects form fields (name, email, message, phone, submit) via selectors and optionally Ollama, fills with your template, submits, and records status.

**Input CSV:** Must have `website_url` and `restaurant_name`. Add columns `contact_page_url` and `status` if you want the crawler to update them (it will).

**Key config** (`config.py`):

| Setting | Purpose |
|--------|---------|
| `SENDER_NAME`, `SENDER_EMAIL` | Used in the form |
| `MESSAGE_TEMPLATE` | Body text; use `{restaurant_name}` for personalization |
| `INPUT_CSV`, `OUTPUT_CSV` | Input list and results file |
| `MIN_DELAY`, `MAX_DELAY` | Seconds between submissions (e.g. 20–40 to avoid blocks) |
| `USE_LLM_FALLBACK`, `OLLAMA_MODEL` | Enable Ollama when selectors fail; which model |
| `HEADLESS_MODE` | `False` to watch the browser (useful for debugging) |

**Output CSV:** `restaurant_name`, `website_url`, `contact_page_url`, `status`. Status values:

| Status | Meaning |
|--------|---------|
| `sent` | Form submitted successfully |
| `no contact page found` | No contact page detected |
| `failed: required fields not found` | Contact page found but email/message fields not detected |
| `failed: submission error` | Submit failed or success not confirmed |
| `failed: ...` | Other errors (see log) |

**Resume:** Rows that already have a non-empty `status` are skipped. Run again to continue.

---

## Output Files Summary

| File | Source | Contents |
|------|--------|----------|
| `restaurant_leads.csv` | Lead-gen bot | `restaurant_name`, `website`, `emails_found` |
| `restaurants_results.csv` | Crawler | `website_url`, `restaurant_name`, `contact_page_url`, `status` |
| `lead_gen_failures.log` | Lead-gen bot | Request/SSL failures |
| `crawler.log` | Crawler | Detailed run log |

---

## Troubleshooting

- **Playwright:** `python -m playwright install chromium`. On Linux, `sudo playwright install-deps` if needed.
- **Ollama:** Crawler uses it only if `USE_LLM_FALLBACK` is True and Ollama is running. Check: `curl http://localhost:11434/api/tags`. See [LLM_SETUP.md](LLM_SETUP.md).
- **Low success rate (crawler):** Enable `USE_LLM_FALLBACK`; check `crawler.log`; set `SCREENSHOT_ON_FAILURE` or `SAVE_HTML_ON_FAILURE` to inspect failures; run with `HEADLESS_MODE = False` to watch.
- **“No contact page found”** but the site has one: Some contact links are in menus or use unusual URLs. You can add patterns to `CONTACT_URL_PATTERNS` or `CONTACT_LINK_TEXT` in `config.py`, or manually add the contact URL to your CSV if you know it.
- **Rate limits / blocks:** Increase `MIN_DELAY` and `MAX_DELAY` in `config.py`. Lead-gen bot already throttles; see [LEAD_GEN.md](LEAD_GEN.md) for API limits.

---

## Limitations

- **Crawler:** Cannot handle CAPTCHAs, forms behind login, or many heavily JavaScript-driven flows. Custom or non-standard forms may need manual selector tweaks. Success rates are typical (~60–70% selectors only, ~85–95% with Ollama).
- **Lead-gen:** Only collects public emails from restaurant-owned sites; skips sites that disallow crawling via robots.txt.

---

## Legal / Ethics

For legitimate business outreach only. Don’t spam; respect opt-outs and website terms of service; comply with CAN-SPAM and similar regulations. You are responsible for how you use these tools.

---

## License

MIT – see [LICENSE](LICENSE).
