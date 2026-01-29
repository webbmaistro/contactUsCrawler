"""Main crawler orchestration: load restaurants, process, save, run."""

import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd
from playwright.sync_api import Page, sync_playwright
from urllib.parse import urlparse

import config

from crawler.logger import Logger
from crawler.llm import OllamaLLM
from crawler.contact_finder import ContactPageFinder
from crawler.form_detector import FormFieldDetector


class ContactFormCrawler:
    """Main crawler class that orchestrates the entire process."""

    def __init__(self):
        self.logger = Logger()
        self.llm = OllamaLLM(self.logger)
        self.results = []
        self.processed_count = 0

        # Create output directories if needed
        if config.SCREENSHOT_ON_FAILURE:
            Path(config.SCREENSHOT_DIR).mkdir(exist_ok=True)
        if config.SAVE_HTML_ON_FAILURE:
            Path(config.HTML_DIR).mkdir(exist_ok=True)

    def load_restaurants(self) -> List[Dict[str, str]]:
        """Load restaurant data from CSV. Dedupes by website domain (first occurrence kept)."""
        try:
            df = pd.read_csv(config.INPUT_CSV)

            # Accept lead-gen output: "website" is the same as "website_url"
            if "website_url" not in df.columns and "website" in df.columns:
                df["website_url"] = df["website"]
            if "restaurant_name" not in df.columns and "name" in df.columns:
                df["restaurant_name"] = df["name"]

            # Validate required columns
            if "website_url" not in df.columns or "restaurant_name" not in df.columns:
                self.logger.error(
                    "CSV must have 'website_url' and 'restaurant_name' (or 'website' and 'restaurant_name')"
                )
                sys.exit(1)

            # Add result columns if they don't exist
            if "contact_page_url" not in df.columns:
                df["contact_page_url"] = ""
            if "status" not in df.columns:
                df["status"] = ""

            # Dedupe by domain so we only process each site once (first occurrence kept)
            def _domain(url: str) -> str:
                if pd.isna(url) or not url:
                    return ""
                parsed = urlparse(str(url).strip())
                netloc = (parsed.netloc or "").lower().replace("www.", "")
                return netloc

            df["_domain"] = df["website_url"].map(_domain)
            before = len(df)
            df = df[df["_domain"] != ""].drop_duplicates(subset=["_domain"], keep="first")
            df = df.drop(columns=["_domain"])
            if len(df) < before:
                self.logger.info(
                    f"Deduped input: {before} rows -> {len(df)} unique domains (duplicates skipped)"
                )

            # Convert to list of dicts
            restaurants = df.to_dict("records")

            self.logger.info(f"Loaded {len(restaurants)} restaurants from {config.INPUT_CSV}")
            return restaurants

        except FileNotFoundError:
            self.logger.error(f"Input file not found: {config.INPUT_CSV}")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"Error loading CSV: {str(e)}")
            sys.exit(1)

    def save_progress(self, restaurants: List[Dict[str, str]]):
        """Save current progress to CSV."""
        try:
            df = pd.DataFrame(restaurants)
            df.to_csv(config.OUTPUT_CSV, index=False)
            self.logger.info(f"Progress saved to {config.OUTPUT_CSV}")
        except Exception as e:
            self.logger.error(f"Error saving progress: {str(e)}")

    def process_restaurant(self, page: Page, restaurant: Dict[str, str]) -> Dict[str, str]:
        """Process a single restaurant."""
        website_url = restaurant["website_url"]
        restaurant_name = restaurant["restaurant_name"]

        # Skip if already processed
        if restaurant.get("status") and restaurant["status"] != "":
            self.logger.info(f"Skipping {restaurant_name} (already processed)")
            return restaurant

        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"Processing: {restaurant_name}")
        self.logger.info(f"URL: {website_url}")
        self.logger.info(f"{'='*60}")

        try:
            # Find contact page
            finder = ContactPageFinder(page, self.logger)
            contact_url = finder.find_contact_page(website_url)

            if not contact_url:
                restaurant["contact_page_url"] = ""
                restaurant["status"] = "no contact page found"
                self.logger.warning(f"No contact page found for {restaurant_name}")
                return restaurant

            restaurant["contact_page_url"] = contact_url

            # Detect and fill form
            detector = FormFieldDetector(page, self.logger, self.llm)
            fields = detector.detect_fields()

            # Check if we have minimum required fields
            if not fields.get("email") or not fields.get("message"):
                restaurant["status"] = "failed: required fields not found"
                self.logger.error("Could not find required form fields (email and message)")

                if config.SCREENSHOT_ON_FAILURE:
                    self._save_screenshot(page, restaurant_name)
                if config.SAVE_HTML_ON_FAILURE:
                    self._save_html(page, restaurant_name)

                return restaurant

            # Fill and submit form
            success = detector.fill_and_submit(fields, restaurant_name)

            if success:
                restaurant["status"] = "sent"
                self.logger.success(f"Successfully submitted form for {restaurant_name}")
            else:
                restaurant["status"] = "failed: submission error"
                self.logger.error(f"Failed to submit form for {restaurant_name}")

                if config.SCREENSHOT_ON_FAILURE:
                    self._save_screenshot(page, restaurant_name)

        except Exception as e:
            restaurant["status"] = f"failed: {str(e)[:100]}"
            self.logger.error(f"Error processing {restaurant_name}: {str(e)}")

            if config.SCREENSHOT_ON_FAILURE:
                self._save_screenshot(page, restaurant_name)

        return restaurant

    def _save_screenshot(self, page: Page, restaurant_name: str):
        """Save screenshot for debugging."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{config.SCREENSHOT_DIR}/{restaurant_name.replace(' ', '_')}_{timestamp}.png"
            page.screenshot(path=filename)
            self.logger.debug(f"Screenshot saved: {filename}")
        except Exception as e:
            self.logger.error(f"Error saving screenshot: {str(e)}")

    def _save_html(self, page: Page, restaurant_name: str):
        """Save HTML for debugging."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{config.HTML_DIR}/{restaurant_name.replace(' ', '_')}_{timestamp}.html"
            html = page.content()
            Path(filename).write_text(html, encoding="utf-8")
            self.logger.debug(f"HTML saved: {filename}")
        except Exception as e:
            self.logger.error(f"Error saving HTML: {str(e)}")

    def run(self):
        """Main crawler execution."""
        self.logger.info("="*60)
        self.logger.info("Restaurant Contact Form Crawler")
        self.logger.info("="*60)
        self.logger.info(f"Configuration:")
        self.logger.info(f"  - Input: {config.INPUT_CSV}")
        self.logger.info(f"  - Output: {config.OUTPUT_CSV}")
        self.logger.info(f"  - Headless: {config.HEADLESS_MODE}")
        self.logger.info(f"  - LLM Fallback: {config.USE_LLM_FALLBACK}")
        if config.USE_LLM_FALLBACK:
            self.logger.info(f"  - LLM Available: {self.llm.available}")
        self.logger.info(f"  - Delay: {config.MIN_DELAY}-{config.MAX_DELAY}s")
        self.logger.info("="*60)

        # Load restaurants
        restaurants = self.load_restaurants()
        total = len(restaurants)

        # Filter to only unprocessed
        unprocessed = [r for r in restaurants if not r.get("status") or r["status"] == ""]

        if not unprocessed:
            self.logger.success("All restaurants already processed!")
            return

        self.logger.info(f"Found {len(unprocessed)} unprocessed restaurants out of {total} total")

        # Start browser
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=config.HEADLESS_MODE)

            context = browser.new_context(
                viewport={"width": config.VIEWPORT_WIDTH, "height": config.VIEWPORT_HEIGHT},
                user_agent=config.USER_AGENT
            )

            page = context.new_page()
            page.set_default_timeout(config.BROWSER_TIMEOUT)

            try:
                for idx, restaurant in enumerate(restaurants):
                    # Skip if already processed
                    if restaurant.get("status") and restaurant["status"] != "":
                        continue

                    self.processed_count += 1

                    # Process restaurant
                    restaurant = self.process_restaurant(page, restaurant)

                    # Update the restaurant in the list
                    restaurants[idx] = restaurant

                    # Save progress periodically
                    if self.processed_count % config.SAVE_PROGRESS_INTERVAL == 0:
                        self.save_progress(restaurants)

                    # Add delay between submissions (except for last one)
                    if self.processed_count < len(unprocessed):
                        delay = random.randint(config.MIN_DELAY, config.MAX_DELAY)
                        self.logger.info(f"Waiting {delay} seconds before next submission...")
                        time.sleep(delay)

                # Final save
                self.save_progress(restaurants)

            finally:
                browser.close()

        # Print summary
        self._print_summary(restaurants)

    def _print_summary(self, restaurants: List[Dict[str, str]]):
        """Print summary of results."""
        self.logger.info("\n" + "="*60)
        self.logger.info("CRAWL SUMMARY")
        self.logger.info("="*60)

        total = len(restaurants)
        sent = len([r for r in restaurants if r.get("status") == "sent"])
        no_contact = len([r for r in restaurants if r.get("status") == "no contact page found"])
        failed = len([r for r in restaurants if r.get("status", "").startswith("failed")])
        pending = len([r for r in restaurants if not r.get("status") or r["status"] == ""])

        self.logger.info(f"Total restaurants: {total}")
        self.logger.success(f"Successfully sent: {sent} ({sent/total*100:.1f}%)")
        self.logger.warning(f"No contact page: {no_contact} ({no_contact/total*100:.1f}%)")
        self.logger.error(f"Failed: {failed} ({failed/total*100:.1f}%)")
        if pending > 0:
            self.logger.info(f"Pending: {pending}")

        self.logger.info("="*60)
        self.logger.success(f"Results saved to: {config.OUTPUT_CSV}")
        self.logger.info(f"Log file: {config.LOG_FILE}")


def main():
    """Entry point."""
    try:
        crawler = ContactFormCrawler()
        crawler.run()
    except KeyboardInterrupt:
        print("\n\nCrawler interrupted by user. Progress has been saved.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nFatal error: {str(e)}")
        sys.exit(1)
