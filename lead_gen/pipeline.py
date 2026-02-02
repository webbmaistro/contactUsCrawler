"""
Main pipeline: get restaurants from Google + Geoapify, merge, scrape emails, save to CSV.
"""

import csv
import os
import time
from pathlib import Path
from typing import Optional

# Load environment variables from .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, will use system env vars only

from lead_gen import config
from lead_gen.chain_filter import ollama_available, is_chain_restaurant_ollama, use_ollama_chain_filter
from lead_gen.places_merge import get_all_restaurants_parallel, extract_domain
from lead_gen.robots import is_scraping_allowed
from lead_gen.email_scraper import get_public_emails, resolve_final_url
from lead_gen.csv_io import save_row, load_existing_csv


def run_pipeline(
    query: str,
    output_csv: str = config.OUTPUT_CSV,
    google_key: Optional[str] = None,
    geoapify_key: Optional[str] = None,
):
    """
    Main flow: get restaurants from Google + Geoapify in parallel,
    merge and dedupe → for each with website and robots allowed, scrape public emails → save to CSV.
    If output_csv already exists, loads it and skips any domain already present.
    """
    if not any((google_key and google_key.strip(), geoapify_key and geoapify_key.strip())):
        config.logger.error("Set at least one of GOOGLE_PLACES_API_KEY, GEOAPIFY_API_KEY")
        return

    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)

    existing_rows, seen_domains = load_existing_csv(output_csv)
    if existing_rows:
        config.logger.info("Loaded %s existing rows from %s (will skip those domains)", len(existing_rows), output_csv)

    config.logger.info("Fetching restaurants from API(s)... (processing starts as soon as first source returns)")
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["restaurant_name", "website", "emails_found", "phone_numbers_found", "contact_page_found", "query"])
        for row in existing_rows:
            w.writerow([
                row["name"],
                row["website"],
                row["emails_found"],
                row.get("phone_numbers_found", ""),
                row.get("contact_page_found", ""),
                row.get("query", ""),
            ])

    ollama_chain_enabled = use_ollama_chain_filter() and ollama_available()
    if ollama_chain_enabled:
        config.logger.info("Ollama chain filter enabled (skipping chains/franchises)")

    n_written = 0
    n_skip_no_website = 0
    n_skip_already = 0
    n_skip_chain_domain = 0
    n_skip_chain_ollama = 0
    n_skip_catering = 0
    n_skip_robots = 0
    n_skip_dead = 0

    for batch, is_final in get_all_restaurants_parallel(
        query,
        google_key=google_key,
        geoapify_key=geoapify_key,
    ):
        config.logger.info("Processing batch of %s restaurants (API batch)", len(batch))
        for r in batch:
            name = (r.get("name") or "").strip()
            name_lower = name.lower()
            website = (r.get("website") or "").strip()

            # Skip catering businesses
            if any(keyword in name_lower for keyword in config.SKIP_NAME_KEYWORDS):
                n_skip_catering += 1
                config.logger.info("Skipping %s (catering/food service business)", name)
                continue

            if not website:
                n_skip_no_website += 1
                config.logger.info("Skipping %s (no website)", name)
                continue
            final_url = resolve_final_url(website)
            if not final_url:
                n_skip_dead += 1
                config.logger.info("Skipping %s (unreachable or invalid SSL when resolving redirects)", name)
                continue
            domain = extract_domain(final_url) or ""
            if not domain:
                continue
            if domain in seen_domains:
                n_skip_already += 1
                config.logger.info("Skipping %s (domain %s already in CSV)", name, domain)
                continue
            if domain in config.SKIP_DOMAINS or any(domain.endswith("." + d) for d in config.SKIP_DOMAINS):
                n_skip_chain_domain += 1
                config.logger.info("Skipping %s (chain/franchise domain %s)", name, domain)
                continue
            if ollama_chain_enabled and is_chain_restaurant_ollama(name, domain):
                n_skip_chain_ollama += 1
                config.logger.info("Skipping %s (Ollama: chain/franchise)", name)
                continue
            seen_domains.add(domain)

            if not is_scraping_allowed(final_url):
                n_skip_robots += 1
                save_row(
                    output_csv,
                    name,
                    final_url,
                    [],
                    [],
                    contact_page_found="",
                    query=query,
                    write_header=False,
                )
                config.logger.info("Skipping %s (robots.txt disallows) — logged to CSV", name)
                continue

            emails, phones, homepage_ok, contact_page_found = get_public_emails(final_url)
            if not homepage_ok:
                n_skip_dead += 1
                config.logger.info("Skipping %s (site unreachable or invalid SSL)", name)
                continue
            save_row(
                output_csv,
                name,
                final_url,
                emails,
                phones,
                contact_page_found=contact_page_found,
                query=query,
                write_header=False,
            )
            n_written += 1
            config.logger.info(
                "Saved %s | %s | emails: %s | phones: %s",
                name,
                final_url,
                "|".join(emails) if emails else "(none)",
                "|".join(phones) if phones else "(none)",
            )
            time.sleep(config.SCRAPE_DELAY_SECONDS)

    config.logger.info(
        "Done. Written: %s | Skipped: already=%s, chain(domain)=%s, chain(Ollama)=%s, catering=%s, robots=%s, dead/SSL=%s, no_website=%s",
        n_written, n_skip_already, n_skip_chain_domain, n_skip_chain_ollama, n_skip_catering, n_skip_robots, n_skip_dead, n_skip_no_website,
    )
    config.logger.info("Output: %s | Failures: %s", output_csv, config.FAILURE_LOG)


def main():
    """Entry point: read env and run pipeline."""
    query = os.environ.get("LEAD_GEN_QUERY", "restaurants in Denver Colorado")
    google_key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip() or None
    geoapify_key = os.environ.get("GEOAPIFY_API_KEY", "").strip() or None
    run_pipeline(
        query,
        google_key=google_key,
        geoapify_key=geoapify_key,
    )
