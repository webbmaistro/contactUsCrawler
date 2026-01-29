"""Website email scraper: fetch contact/about pages, extract same-domain emails."""

import re
import time
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from lead_gen import config


def get_public_emails(website_url: str) -> tuple:
    """
    Visit restaurant website and likely contact/about pages.
    Extract mailto links and visible emails via regex.
    Filter: same-domain only, no image filenames, no obvious spam traps.
    Returns (emails, homepage_reachable).
    """
    seen = set()
    emails = []
    parsed_base = urlparse(website_url)
    base_domain = (parsed_base.netloc or "").lower().replace("www.", "")
    if not base_domain:
        return [], False

    base = f"{parsed_base.scheme}://{parsed_base.netloc}"
    urls_to_fetch = [website_url]
    for path in config.CONTACT_PATHS:
        urls_to_fetch.append(urljoin(base, path))

    homepage_ok = False
    for i, page_url in enumerate(urls_to_fetch):
        html = _fetch_page(page_url)
        if not html:
            continue
        if i == 0:
            homepage_ok = True
        for addr in _extract_mailto(html):
            if _is_valid_same_domain_email(addr, base_domain) and addr not in seen:
                seen.add(addr)
                emails.append(addr)
        for addr in _extract_regex_emails(html):
            if _is_valid_same_domain_email(addr, base_domain) and addr not in seen:
                seen.add(addr)
                emails.append(addr)
        time.sleep(0.5)

    emails.sort(key=lambda e: (-_email_quality_score(e), e))
    return emails, homepage_ok


def resolve_final_url(url: str) -> Optional[str]:
    """
    Follow redirects and return the final URL, or None if unreachable.
    """
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


def _fetch_page(url: str) -> Optional[str]:
    """Fetch page with User-Agent and timeout. Retries on transient errors."""
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
            config.failure_logger.warning("SSL error for %s: %s", url, e)
            return None
        except requests.RequestException as e:
            if attempt < config.MAX_RETRIES:
                time.sleep(config.RETRY_BACKOFF * (attempt + 1))
                continue
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
