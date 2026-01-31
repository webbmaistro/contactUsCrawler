"""Website email scraper: fetch contact/about pages, extract emails and phone numbers."""

import re
import time
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from lead_gen import config

# Phone: 10–15 digits, optional + and separators (space, dash, dot, parens)
PHONE_REGEX = re.compile(
    r"\+?[\d\s\-\.\(\)]{10,24}"
)


def get_public_emails(website_url: str) -> tuple:
    """
    Visit restaurant website and likely contact/about pages.
    Extract mailto links and visible emails via regex; extract tel: links and phone-like text.
    Filter emails: same-domain only, no image filenames, no obvious spam traps.
    Returns (emails, phones, homepage_reachable, contact_page_url).
    contact_page_url = URL of the first contact-path (/contact, /about, etc.) that returned content, or "" if none.
    """
    seen_emails = set()
    emails = []
    seen_phones = set()
    phones = []
    parsed_base = urlparse(website_url)
    base_domain = (parsed_base.netloc or "").lower().replace("www.", "")
    if not base_domain:
        return [], [], False, ""

    base = f"{parsed_base.scheme}://{parsed_base.netloc}"
    urls_to_fetch = [website_url]
    for path in config.CONTACT_PATHS:
        urls_to_fetch.append(urljoin(base, path))

    homepage_ok = False
    contact_page_url = ""
    for i, page_url in enumerate(urls_to_fetch):
        # Don't log 404s/failures for contact-path variations—only for the main page
        html = _fetch_page(page_url, silent_fail=(i > 0))
        if not html:
            continue
        if i == 0:
            homepage_ok = True
        else:
            if not contact_page_url:
                contact_page_url = page_url  # First contact path that returned content
        for addr in _extract_mailto(html):
            if _is_valid_same_domain_email(addr, base_domain) and addr not in seen_emails:
                seen_emails.add(addr)
                emails.append(addr)
        for addr in _extract_regex_emails(html):
            if _is_valid_same_domain_email(addr, base_domain) and addr not in seen_emails:
                seen_emails.add(addr)
                emails.append(addr)
        for num in _extract_tel(html):
            key = _phone_digits(num)
            if key and key not in seen_phones and _is_valid_phone(key):
                seen_phones.add(key)
                phones.append(_normalize_phone_display(num))
        for num in _extract_regex_phones(html):
            key = _phone_digits(num)
            if key and key not in seen_phones and _is_valid_phone(key):
                seen_phones.add(key)
                phones.append(_normalize_phone_display(num))
        time.sleep(0.5)

    emails.sort(key=lambda e: (-_email_quality_score(e), e))
    return emails, phones, homepage_ok, contact_page_url


def resolve_final_url(url: str) -> Optional[str]:
    """
    Follow redirects and return the final URL, or None if unreachable.
    If url has no scheme (e.g. joyluck1.com), prepends https:// so requests can resolve it.
    """
    url = (url or "").strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    for attempt in range(config.MAX_RETRIES + 1):
        try:
            r = requests.get(
                url,
                headers={"User-Agent": config.USER_AGENT},
                timeout=config.REQUEST_TIMEOUT,
                verify=True,
                allow_redirects=True,
                stream=True,
            )
            r.close()
            return r.url
        except requests.exceptions.SSLError as e:
            config.failure_logger.warning("SSL error resolving %s: %s", url, e)
            return None
        except requests.RequestException as e:
            if attempt < config.MAX_RETRIES:
                time.sleep(config.RETRY_BACKOFF * (attempt + 1))
                continue
            config.failure_logger.warning("Could not resolve redirects for %s: %s", url, e)
            return None
    return None


def _fetch_page(url: str, *, silent_fail: bool = False) -> Optional[str]:
    """Fetch page with User-Agent and timeout. Retries on transient errors. If silent_fail, don't log failures (e.g. 404 on contact paths)."""
    for attempt in range(config.MAX_RETRIES + 1):
        try:
            r = requests.get(
                url,
                headers={"User-Agent": config.USER_AGENT},
                timeout=config.REQUEST_TIMEOUT,
                verify=True,
            )
            r.raise_for_status()
            return r.text
        except requests.exceptions.SSLError as e:
            if not silent_fail:
                config.failure_logger.warning("SSL error for %s: %s", url, e)
            return None
        except requests.RequestException as e:
            if attempt < config.MAX_RETRIES:
                time.sleep(config.RETRY_BACKOFF * (attempt + 1))
                continue
            if not silent_fail:
                config.failure_logger.warning("Request failed after %s retries for %s: %s", config.MAX_RETRIES, url, e)
            return None
    return None


def _extract_mailto(html: str) -> list:
    """Extract email addresses from mailto: links."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("mailto:"):
            part = href[7:].split("?")[0].strip()
            if part and config.EMAIL_REGEX.fullmatch(part):
                out.append(part)
    return out


def _extract_regex_emails(html: str) -> list:
    """Extract emails using regex from text (avoid script/style)."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text()
    return config.EMAIL_REGEX.findall(text)


def _extract_tel(html: str) -> list:
    """Extract phone numbers from tel: links."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("tel:"):
            part = href[4:].split("?")[0].strip().replace(" ", "")
            if part and any(c.isdigit() for c in part):
                out.append(part)
    return out


def _extract_regex_phones(html: str) -> list:
    """Extract phone-like sequences from text (avoid script/style)."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text()
    return PHONE_REGEX.findall(text)


def _phone_digits(s: str) -> str:
    """Digits only from a phone string (for dedupe)."""
    return "".join(c for c in s if c.isdigit())


def _is_valid_phone(digits: str) -> bool:
    """Filter: 10–15 digits, not all same digit, not a year."""
    if len(digits) < 10 or len(digits) > 15:
        return False
    if len(set(digits)) < 2:
        return False
    if len(digits) == 4 and digits.startswith(("19", "20")):
        return False
    if digits.startswith("0"):
        return False
    return True


def _normalize_phone_display(s: str) -> str:
    """Clean for display: strip, keep digits and common separators, limit length."""
    s = "".join(c for c in s.strip() if c.isdigit() or c in "+.-() ").strip()
    return s[:25] if s else ""


def _is_valid_same_domain_email(email: str, base_domain: str) -> bool:
    """Filter: same domain, not image filename, not obvious spam trap."""
    email = email.lower()
    if any(email.endswith(s) for s in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
        return False
    if re.search(r"\.(png|jpg|jpeg|gif|webp|svg)$", email):
        return False
    if any(x in email for x in ("example.com", "email.com", "test.com", "yoursite.com", "domain.com")):
        return False
    if "noreply" in email or "no-reply" in email or "donotreply" in email:
        return False
    try:
        domain = email.split("@")[1]
    except IndexError:
        return False
    domain = domain.replace("www.", "")
    return domain == base_domain or domain.endswith("." + base_domain) or base_domain.endswith("." + domain)


def _email_quality_score(email: str) -> int:
    """Higher = better (info@ > support@ > random)."""
    local = email.lower().split("@")[0]
    for key, score in config.EMAIL_QUALITY.items():
        if key in local:
            return score
    return 0
