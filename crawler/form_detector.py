"""Detects and interacts with form fields."""

import time
from typing import Dict, List, Optional

from playwright.sync_api import Page

import config

from crawler.logger import Logger
from crawler.llm import OllamaLLM


class FormFieldDetector:
    """Detects and interacts with form fields."""

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
        """Find a form field using pattern matching."""
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
        """Find the submit button."""
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
        """Use LLM to detect form fields."""
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
        """Fill out and submit the contact form."""
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
        """Check if form submission was successful."""
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
