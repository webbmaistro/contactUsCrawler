"""Finds contact pages on websites."""

import time
from typing import Optional
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

import config

from crawler.logger import Logger


class ContactPageFinder:
    """Finds contact pages on websites."""

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
        """Try common contact page URL patterns."""
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
        """Check if current page looks like a contact page."""
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
        """Find contact page link on current page."""
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
