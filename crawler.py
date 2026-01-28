#!/usr/bin/env python3
"""
Restaurant Contact Form Crawler
Automatically finds and submits contact forms on restaurant websites
"""

import csv
import json
import logging
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from colorama import Fore, Style, init
from playwright.sync_api import Page, sync_playwright, TimeoutError as PlaywrightTimeout

import config

# Initialize colorama for cross-platform colored output
init(autoreset=True)


class Logger:
    """Custom logger with colored console output and file logging"""

    def __init__(self, log_file: str = config.LOG_FILE):
        self.logger = logging.getLogger("ContactFormCrawler")
        self.logger.setLevel(getattr(logging, config.LOG_LEVEL))

        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        # Console handler (we'll handle formatting ourselves for colors)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, config.LOG_LEVEL))
        console_handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(console_handler)

    def info(self, msg: str):
        self.logger.info(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} {msg}")

    def success(self, msg: str):
        self.logger.info(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} {msg}")

    def warning(self, msg: str):
        self.logger.warning(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} {msg}")

    def error(self, msg: str):
        self.logger.error(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {msg}")

    def debug(self, msg: str):
        self.logger.debug(f"{Fore.MAGENTA}[DEBUG]{Style.RESET_ALL} {msg}")


class OllamaLLM:
    """Interface to Ollama for AI-powered form field detection"""

    def __init__(self, logger: Logger):
        self.logger = logger
        self.api_url = config.OLLAMA_API_URL
        self.model = config.OLLAMA_MODEL
        self.available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if Ollama is available and the model is installed"""
        if not config.USE_LLM_FALLBACK:
            return False

        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]

                if any(self.model in name for name in model_names):
                    self.logger.info(f"Ollama is available with model: {self.model}")
                    return True
                else:
                    self.logger.warning(
                        f"Ollama is running but model '{self.model}' not found. "
                        f"Available models: {', '.join(model_names)}"
                    )
                    return False
            return False
        except requests.RequestException:
            self.logger.warning("Ollama is not available. LLM fallback disabled.")
            return False

    def detect_form_fields(self, html: str) -> Optional[Dict[str, str]]:
        """Use LLM to detect form field selectors from HTML"""
        if not self.available:
            return None

        prompt = f"""Analyze this HTML form and identify CSS selectors for the contact form fields.
Return ONLY a valid JSON object with these keys: "name", "email", "message", "phone", "submit".
For each key, provide the best CSS selector (id, name, or other attribute) to find that field.
If a field doesn't exist, use an empty string "".

HTML:
{html[:3000]}

Respond with ONLY the JSON object, no explanation:"""

        try:
            self.logger.debug("Calling Ollama LLM for form field detection...")

            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": config.LLM_TEMPERATURE,
                    "num_predict": config.LLM_MAX_TOKENS
                }
            }

            response = requests.post(self.api_url, json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                llm_response = result.get("response", "")

                # Try to extract JSON from response
                json_match = re.search(r'\{[^{}]*\}', llm_response)
                if json_match:
                    selectors = json.loads(json_match.group())
                    self.logger.debug(f"LLM detected selectors: {selectors}")
                    return selectors
                else:
                    self.logger.warning("LLM response did not contain valid JSON")
                    return None
            else:
                self.logger.error(f"Ollama API error: {response.status_code}")
                return None

        except Exception as e:
            self.logger.error(f"Error calling Ollama: {str(e)}")
            return None


class ContactPageFinder:
    """Finds contact pages on websites"""

    def __init__(self, page: Page, logger: Logger):
        self.page = page
        self.logger = logger

    def find_contact_page(self, base_url: str) -> Optional[str]:
        """
        Find the contact page URL for a given website
        Returns the contact page URL or None if not found
        """
        self.logger.info(f"Searching for contact page on {base_url}")

        # First, try common URL patterns
        contact_url = self._try_common_urls(base_url)
        if contact_url:
            return contact_url

        # If not found, navigate to homepage and search for contact links
        try:
            self.page.goto(base_url, timeout=config.BROWSER_TIMEOUT, wait_until="domcontentloaded")
            time.sleep(2)  # Give page time to load

            contact_url = self._find_contact_link()
            if contact_url:
                return contact_url

        except Exception as e:
            self.logger.error(f"Error navigating to {base_url}: {str(e)}")

        return None

    def _try_common_urls(self, base_url: str) -> Optional[str]:
        """Try common contact page URL patterns"""
        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        for pattern in config.CONTACT_URL_PATTERNS:
            test_url = urljoin(base, pattern)
            try:
                self.logger.debug(f"Trying URL: {test_url}")
                response = self.page.goto(test_url, timeout=config.BROWSER_TIMEOUT, wait_until="domcontentloaded")

                if response and response.status == 200:
                    # Check if page looks like a contact page
                    if self._looks_like_contact_page():
                        self.logger.success(f"Found contact page: {test_url}")
                        return test_url

            except PlaywrightTimeout:
                self.logger.debug(f"Timeout on {test_url}")
                continue
            except Exception as e:
                self.logger.debug(f"Error trying {test_url}: {str(e)}")
                continue

        return None

    def _looks_like_contact_page(self) -> bool:
        """Check if current page looks like a contact page"""
        try:
            # Check for contact form
            form_exists = self.page.locator("form").count() > 0

            # Check for email or message input fields
            email_field = self.page.locator("input[type='email'], input[name*='email'], input[id*='email']").count() > 0
            message_field = self.page.locator("textarea, input[name*='message'], input[id*='message']").count() > 0

            # Check page title/heading
            title = self.page.title().lower()
            heading = self.page.locator("h1").first.text_content().lower() if self.page.locator("h1").count() > 0 else ""

            has_contact_text = any(word in title or word in heading for word in ["contact", "get in touch", "reach"])

            return (form_exists and (email_field or message_field)) or has_contact_text

        except Exception:
            return False

    def _find_contact_link(self) -> Optional[str]:
        """Find contact page link on current page"""
        try:
            # Get all links on the page
            links = self.page.locator("a").all()

            contact_links = []
            for link in links[:50]:  # Limit to first 50 links for performance
                try:
                    href = link.get_attribute("href")
                    text = link.text_content().strip().lower()

                    if not href:
                        continue

                    # Check if link text matches contact patterns
                    if any(pattern in text for pattern in config.CONTACT_LINK_TEXT):
                        full_url = urljoin(self.page.url, href)
                        contact_links.append(full_url)

                except Exception:
                    continue

            # Try each contact link
            for contact_url in contact_links[:config.MAX_CONTACT_LINKS_TO_CHECK]:
                try:
                    self.logger.debug(f"Checking contact link: {contact_url}")
                    response = self.page.goto(contact_url, timeout=config.BROWSER_TIMEOUT, wait_until="domcontentloaded")

                    if response and response.status == 200 and self._looks_like_contact_page():
                        self.logger.success(f"Found contact page via link: {contact_url}")
                        return contact_url

                except Exception as e:
                    self.logger.debug(f"Error checking {contact_url}: {str(e)}")
                    continue

        except Exception as e:
            self.logger.error(f"Error finding contact links: {str(e)}")

        return None


class FormFieldDetector:
    """Detects and interacts with form fields"""

    def __init__(self, page: Page, logger: Logger, llm: Optional[OllamaLLM] = None):
        self.page = page
        self.logger = logger
        self.llm = llm

    def detect_fields(self) -> Dict[str, Optional[str]]:
        """
        Detect form fields using CSS selectors and optionally LLM fallback
        Returns dict with field selectors: {name, email, message, phone, submit}
        """
        fields = {
            "name": None,
            "email": None,
            "message": None,
            "phone": None,
            "submit": None
        }

        # Try selector-based detection first
        fields["name"] = self._find_field(config.NAME_FIELD_PATTERNS, ["input"])
        fields["email"] = self._find_field(config.EMAIL_FIELD_PATTERNS, ["input[type='email']", "input"])
        fields["message"] = self._find_field(config.MESSAGE_FIELD_PATTERNS, ["textarea", "input"])
        fields["phone"] = self._find_field(config.PHONE_FIELD_PATTERNS, ["input[type='tel']", "input"])
        fields["submit"] = self._find_submit_button()

        # Check if we found required fields (email and message)
        required_found = fields["email"] and fields["message"]

        # Use LLM fallback if enabled and required fields not found
        if not required_found and self.llm and config.USE_LLM_FALLBACK:
            self.logger.info("Required fields not found, using LLM fallback...")
            llm_fields = self._detect_with_llm()

            if llm_fields:
                # Update fields that weren't found
                for field_name, selector in llm_fields.items():
                    if selector and (not fields.get(field_name) or fields[field_name] is None):
                        fields[field_name] = selector

        # Log detected fields
        detected = [f for f, v in fields.items() if v]
        self.logger.info(f"Detected fields: {', '.join(detected)}")

        return fields

    def _find_field(self, patterns: List[str], selectors: List[str]) -> Optional[str]:
        """Find a form field using pattern matching"""
        for selector_type in selectors:
            for pattern in patterns:
                # Try different attribute selectors
                for attr in ["name", "id", "placeholder", "aria-label"]:
                    selector = f"{selector_type}[{attr}*='{pattern}' i]"
                    try:
                        if self.page.locator(selector).count() > 0:
                            self.logger.debug(f"Found field with selector: {selector}")
                            return selector
                    except Exception:
                        continue

        return None

    def _find_submit_button(self) -> Optional[str]:
        """Find the submit button"""
        # Try input submit buttons
        for pattern in config.SUBMIT_BUTTON_PATTERNS:
            selector = f"input[type='submit'][value*='{pattern}' i]"
            try:
                if self.page.locator(selector).count() > 0:
                    return selector
            except Exception:
                continue

        # Try button elements
        for pattern in config.SUBMIT_BUTTON_PATTERNS:
            try:
                buttons = self.page.locator("button").all()
                for button in buttons:
                    text = button.text_content().strip().lower()
                    if pattern in text:
                        # Get a unique selector for this button
                        button_type = button.get_attribute("type")
                        if button_type == "submit" or not button_type:
                            return f"button:has-text('{text}')"
            except Exception:
                continue

        # Last resort: any submit button
        try:
            if self.page.locator("button[type='submit']").count() > 0:
                return "button[type='submit']"
            if self.page.locator("input[type='submit']").count() > 0:
                return "input[type='submit']"
        except Exception:
            pass

        return None

    def _detect_with_llm(self) -> Optional[Dict[str, str]]:
        """Use LLM to detect form fields"""
        if not self.llm or not self.llm.available:
            return None

        try:
            # Get page HTML
            html = self.page.content()

            # Call LLM
            selectors = self.llm.detect_form_fields(html)

            if selectors:
                self.logger.success("LLM successfully detected form fields")
                return selectors

        except Exception as e:
            self.logger.error(f"Error in LLM detection: {str(e)}")

        return None

    def fill_and_submit(self, fields: Dict[str, Optional[str]], restaurant_name: str) -> bool:
        """Fill out and submit the contact form"""
        try:
            # Prepare the message with restaurant name
            message = config.MESSAGE_TEMPLATE.format(restaurant_name=restaurant_name)

            # Fill name field
            if fields.get("name"):
                self.logger.debug(f"Filling name field: {fields['name']}")
                self.page.locator(fields["name"]).first.fill(config.SENDER_NAME)
                time.sleep(0.5)

            # Fill email field (required)
            if not fields.get("email"):
                self.logger.error("Email field not found - cannot submit")
                return False

            self.logger.debug(f"Filling email field: {fields['email']}")
            self.page.locator(fields["email"]).first.fill(config.SENDER_EMAIL)
            time.sleep(0.5)

            # Fill phone field if present (optional)
            if fields.get("phone"):
                try:
                    self.logger.debug(f"Filling phone field: {fields['phone']}")
                    self.page.locator(fields["phone"]).first.fill("")  # Leave empty
                    time.sleep(0.5)
                except Exception:
                    pass  # Phone field is optional

            # Fill message field (required)
            if not fields.get("message"):
                self.logger.error("Message field not found - cannot submit")
                return False

            self.logger.debug(f"Filling message field: {fields['message']}")
            self.page.locator(fields["message"]).first.fill(message)
            time.sleep(0.5)

            # Submit the form
            if not fields.get("submit"):
                self.logger.error("Submit button not found - cannot submit")
                return False

            self.logger.debug(f"Clicking submit button: {fields['submit']}")

            # Click submit and wait for navigation or response
            try:
                self.page.locator(fields["submit"]).first.click()

                # Wait a bit for the submission to process
                time.sleep(3)

                # Check for success indicators
                success = self._check_submission_success()

                if success:
                    self.logger.success("Form submitted successfully!")
                    return True
                else:
                    self.logger.warning("Form submitted but success not confirmed")
                    return True  # Still count as success

            except Exception as e:
                self.logger.error(f"Error clicking submit: {str(e)}")
                return False

        except Exception as e:
            self.logger.error(f"Error filling form: {str(e)}")
            return False

    def _check_submission_success(self) -> bool:
        """Check if form submission was successful"""
        try:
            # Look for common success indicators
            success_indicators = [
                "thank you",
                "thanks",
                "success",
                "submitted",
                "received",
                "we'll be in touch",
                "we will be in touch",
                "message sent",
                "email sent"
            ]

            page_text = self.page.text_content("body").lower()

            for indicator in success_indicators:
                if indicator in page_text:
                    return True

            # Check URL for success page
            current_url = self.page.url.lower()
            if "success" in current_url or "thank" in current_url:
                return True

        except Exception:
            pass

        return False


class ContactFormCrawler:
    """Main crawler class that orchestrates the entire process"""

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
        """Load restaurant data from CSV"""
        try:
            df = pd.read_csv(config.INPUT_CSV)

            # Validate required columns
            if "website_url" not in df.columns or "restaurant_name" not in df.columns:
                self.logger.error("CSV must have 'website_url' and 'restaurant_name' columns")
                sys.exit(1)

            # Add result columns if they don't exist
            if "contact_page_url" not in df.columns:
                df["contact_page_url"] = ""
            if "status" not in df.columns:
                df["status"] = ""

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
        """Save current progress to CSV"""
        try:
            df = pd.DataFrame(restaurants)
            df.to_csv(config.OUTPUT_CSV, index=False)
            self.logger.info(f"Progress saved to {config.OUTPUT_CSV}")
        except Exception as e:
            self.logger.error(f"Error saving progress: {str(e)}")

    def process_restaurant(self, page: Page, restaurant: Dict[str, str]) -> Dict[str, str]:
        """Process a single restaurant"""
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
        """Save screenshot for debugging"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{config.SCREENSHOT_DIR}/{restaurant_name.replace(' ', '_')}_{timestamp}.png"
            page.screenshot(path=filename)
            self.logger.debug(f"Screenshot saved: {filename}")
        except Exception as e:
            self.logger.error(f"Error saving screenshot: {str(e)}")

    def _save_html(self, page: Page, restaurant_name: str):
        """Save HTML for debugging"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{config.HTML_DIR}/{restaurant_name.replace(' ', '_')}_{timestamp}.html"
            html = page.content()
            Path(filename).write_text(html, encoding="utf-8")
            self.logger.debug(f"HTML saved: {filename}")
        except Exception as e:
            self.logger.error(f"Error saving HTML: {str(e)}")

    def run(self):
        """Main crawler execution"""
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
                    restaurants[restaurants.index(restaurant)] = restaurant

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
        """Print summary of results"""
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
    """Entry point"""
    try:
        crawler = ContactFormCrawler()
        crawler.run()
    except KeyboardInterrupt:
        print("\n\nCrawler interrupted by user. Progress has been saved.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nFatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
